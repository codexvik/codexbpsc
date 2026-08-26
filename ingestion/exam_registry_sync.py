"""
Syncs the exam-calendar master list (ingestion/exam_calendar.py) into the
`exams` table -- this is what actually keeps the exam registry complete,
independent of whether any notice has ever mentioned a given exam.

Matches on (source_id, advt_no) when advt_no is present -- verified
2026-08-25 that matching on name instead creates duplicates, since the
calendar's post-name text doesn't always match the notice-extracted
exam_name verbatim for the same real exam (e.g. calendar's "District
Statistical Officer/ Assistant Director" vs. the notice's "...Main
(Written) Competitive Examination" -- same exam, same advt_no 38/2025,
different phrasing). advt_no is the actually stable cross-source key.
Falls back to (source_id, name) only when advt_no is genuinely absent
(TRE 4.0: "NA" in the source, normalized to None).

Deliberately conservative about overwriting: an exam that already exists
(e.g. created earlier from a notice) keeps whatever status/category the
notice pipeline gave it. vacancy_count is only ever FILLED IN when null --
never overwritten once set, even by a later sync -- because a
notice-derived count has a documented derivation (e.g. a corrigendum's
old/new value) that this page's own number doesn't always agree with
(verified 2026-08-25: this page said 1189 for 72nd CCE; our corrigendum
extraction said 1186 -- and a naive overwrite-every-cycle sync silently
clobbered the more-derived number back to the calendar's on the very next
run before this comment existed). A disagreement is recorded in
calendar_snapshot_json for a human to look at, never resolved by picking
one source automatically.
"""

from __future__ import annotations

import json
import logging

from db.connection import get_connection
from ingestion.exam_calendar import fetch_exam_calendar

logger = logging.getLogger(__name__)


def _get_source_pk(conn, source_id: str) -> int:
    row = conn.execute("SELECT id FROM sources WHERE source_id = %s", (source_id,)).fetchone()
    if row is None:
        raise ValueError(f"No sources row for source_id={source_id!r} -- run db.seed first")
    return row["id"]


def sync_exam_calendar(source_id: str) -> dict:
    """Fetches, parses, and upserts the exam calendar. Returns
    {"inserted": N, "updated": N, "unchanged": N} counts."""
    entries = fetch_exam_calendar(source_id)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}

    with get_connection() as conn:
        source_pk = _get_source_pk(conn, source_id)

        for entry in entries:
            if entry.advt_no:
                existing = conn.execute(
                    "SELECT id, vacancy_count FROM exams WHERE source_id = %s AND advt_no = %s",
                    (source_pk, entry.advt_no),
                ).fetchone()
            else:
                existing = conn.execute(
                    "SELECT id, vacancy_count FROM exams WHERE source_id = %s AND advt_no IS NULL AND name = %s",
                    (source_pk, entry.name),
                ).fetchone()

            if existing is None:
                snapshot = json.dumps(
                    {"section": entry.section, "raw_columns": entry.raw_columns, "remarks": entry.remarks, "advt_no_raw": entry.advt_no}
                )
                conn.execute(
                    """
                    INSERT INTO exams (source_id, name, advt_no, vacancy_count, calendar_snapshot_json)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (source_pk, entry.name, entry.advt_no, entry.vacancy_count, snapshot),
                )
                counts["inserted"] += 1
                logger.info("Inserted: %s (advt_no=%s, vacancies=%s)", entry.name, entry.advt_no, entry.vacancy_count)
            else:
                existing_count = existing["vacancy_count"]
                discrepancy = None
                if existing_count is None:
                    fill_vacancy_count = entry.vacancy_count
                elif entry.vacancy_count is not None and entry.vacancy_count != existing_count:
                    fill_vacancy_count = existing_count  # never overwrite a value we already had
                    discrepancy = f"Calendar states {entry.vacancy_count}; we already have {existing_count} (kept)."
                else:
                    fill_vacancy_count = existing_count

                snapshot = json.dumps(
                    {
                        "section": entry.section,
                        "raw_columns": entry.raw_columns,
                        "remarks": entry.remarks,
                        "advt_no_raw": entry.advt_no,
                        "vacancy_count_discrepancy": discrepancy,
                    }
                )
                conn.execute(
                    "UPDATE exams SET vacancy_count = %s, calendar_snapshot_json = %s WHERE id = %s",
                    (fill_vacancy_count, snapshot, existing["id"]),
                )
                if existing_count is None and fill_vacancy_count is not None:
                    counts["updated"] += 1
                    logger.info("Filled in vacancy_count for %s: -> %s", entry.name, fill_vacancy_count)
                elif discrepancy:
                    counts["updated"] += 1
                    logger.warning("Discrepancy for %s: %s", entry.name, discrepancy)
                else:
                    counts["unchanged"] += 1

    return counts
