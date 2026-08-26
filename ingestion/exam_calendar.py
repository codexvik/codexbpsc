"""
Parses BPSC's Exam Calendar page (source_config's exam_calendar_url) into
the canonical master list of active exams. This is what actually answers
"which exams exist" -- the notification stream only reports changes to
exams that already exist somewhere; it can't discover an exam that hasn't
generated a notice yet (found 2026-08-25: TRE 4.0 has 32,388 vacancies
listed here with no advertisement issued yet, so it has never appeared in
a notice).

Table structure (verified against the live page): one <table> per exam
"phase type" section (3 Phase / 2 Phase / 1 Phase Interview-only / 1 Phase
Written-only), each with a different number of date/result columns, but
a consistent leading [SN, Adv No, Name of Post, No. of Vacancies] and a
trailing Remarks column. Section titles and column headers are always
<th> (often single-cell with colspan); data rows are always <td> with
>=7 cells -- that distinction is what separates them, not row position.

Middle date/result columns are kept as raw text, not forced into typed
dates: the source itself uses "TBD", "-----", relative phrasing
("November, 2025"), and multi-date ranges, so a strict date type would
either fail to parse or silently misrepresent what the page actually says.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import get_source_config

logger = logging.getLogger(__name__)

_BLANK_VALUES = {"", "-", "--", "---", "-----", "na", "n/a", "tbd"}


def _clean(text: str) -> Optional[str]:
    text = text.strip()
    if text.lower() in _BLANK_VALUES:
        return None
    return text or None


def _parse_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


@dataclass
class CalendarExamEntry:
    sn: Optional[str]
    advt_no: Optional[str]
    name: str
    vacancy_count: Optional[int]
    section: str  # e.g. "3 Phase Exams (PT + MAINS + INTERVIEW)"
    remarks: Optional[str]
    raw_columns: list = field(default_factory=list)  # middle date/result cells, raw text, positional


def parse_exam_calendar(html: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    entries = []

    for table in soup.find_all("table"):
        current_section = "Unknown section"

        for row in table.find_all("tr"):
            single_header = row.find_all("th")
            data_cells = row.find_all("td")

            if len(single_header) == 1 and not data_cells:
                current_section = single_header[0].get_text(" ", strip=True)
                continue

            if len(data_cells) < 5:
                continue  # column-header sub-rows ("Date"/"Result"...) or anything too short to be a real row

            texts = [c.get_text(" ", strip=True) for c in data_cells]
            name = texts[2].strip()
            if not name:
                continue

            entries.append(
                CalendarExamEntry(
                    sn=_clean(texts[0]),
                    advt_no=_clean(texts[1]),
                    name=name,
                    vacancy_count=_parse_int(texts[3]),
                    section=current_section,
                    remarks=_clean(texts[-1]),
                    raw_columns=texts[4:-1],
                )
            )

    return entries


def fetch_exam_calendar(source_id: str, rate_limiter: RateLimiter = None) -> list:
    config = get_source_config(source_id)
    if not config.get("exam_calendar_url"):
        raise ValueError(f"source_id={source_id!r} has no exam_calendar_url configured")
    if rate_limiter is None:
        rate_limiter = RateLimiter(config["rate_limit_seconds"])

    rate_limiter.wait()
    headers = {"User-Agent": config["user_agent"]}
    resp = requests.get(config["exam_calendar_url"], headers=headers, timeout=config["request_timeout_seconds"])
    resp.raise_for_status()

    return parse_exam_calendar(resp.text)
