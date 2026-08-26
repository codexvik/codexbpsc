"""
Seeds the dev database with real, already-verified data only -- no
fabricated exams/notices. Every notice below was actually run through
extraction.run_extract against a live BPSC PDF and pasted here verbatim
from that output -- never regenerated or guessed.

Usage: python -m db.seed
"""

from __future__ import annotations

import json
from typing import Optional

from extraction.extractor import needs_human_review
from extraction.schema import ExtractedNotice
from ingestion.source_config import get_source_config

from db.connection import get_connection

# Verified 2026-08-23 against
# https://bpsc.bihar.gov.in/wp-content/uploads/BPSC_content/Notices/Important-Notice-382025-DSO-Interview-DV_BPSC-20260818-twf3aj.pdf
DSO_NOTICE = ExtractedNotice(
    source_id="bpsc_bihar",
    exam_name="District Statistical Officer / Assistant Director Main (Written) Competitive Examination",
    advt_no="38/2025",
    category="interview",
    change_type="new_notification",
    summary_plain_language=(
        "If you passed the DSO/Assistant Director main exam, your interview and "
        "document check will be held from 8 to 10 September 2026."
    ),
    old_value=None,
    new_value=None,
    effective_date="2026-09-08",
    source_url=(
        "https://bpsc.bihar.gov.in/wp-content/uploads/BPSC_content/Notices/"
        "Important-Notice-382025-DSO-Interview-DV_BPSC-20260818-twf3aj.pdf"
    ),
    confidence="high",
)

# Verified 2026-08-25, per the "re-scope to real BPSC CCE + TRE data" decision --
# BPSC's 72nd CCE is the current live CCE cycle; no TRE notice was live on the
# site as of this date (checked homepage ticker + site search, both empty).
CCE_POSTPONEMENT_NOTICE = ExtractedNotice(
    source_id="bpsc_bihar",
    exam_name="Integrated 72nd Combined (Preliminary) Competitive Examination",
    advt_no=None,
    category="notice",
    change_type="postponement",
    summary_plain_language="Your 72nd BPSC prelims exam on 26 July 2026 has been postponed; the new date will be announced later.",
    old_value="26 July 2026 (Sunday)",
    new_value="Postponed - new date to be announced later",
    effective_date=None,
    source_url=(
        "https://bpsc.bihar.gov.in/wp-content/uploads/BPSC_content/Notices/"
        "Regarding_postpone_72nd_BPSC_BPSC-20260720-u768lx.pdf"
    ),
    confidence="high",
)

CCE_CORRIGENDUM_NOTICE = ExtractedNotice(
    source_id="bpsc_bihar",
    exam_name="Integrated 72nd Combined (Preliminary) Competitive Examination",
    advt_no=None,
    category="corrigendum",
    change_type="vacancy_revision",
    summary_plain_language="The 44 Sugarcane Officer posts have been removed, so the total vacancies are now 1186 instead of 1230.",
    old_value="1230 total posts (including 44 Sugarcane Officer posts at Sl. No. 11)",
    new_value="1186 total posts (Sugarcane Officer posts deleted)",
    effective_date="2026-05-06",
    source_url=(
        "https://bpsc.bihar.gov.in/wp-content/uploads/BPSC_content/Notices/"
        "Corrigendum-Integrated-72nd-CCE-Pre-Advt.-44-vacancies-of-Sugarcane-Officer-"
        "deleted_BPSC-20260506-0jupsy.pdf"
    ),
    confidence="high",
)

# One row per exam: verified notices for that exam, plus honest exam-level
# fields we can actually state (status, vacancy_count) derived from those
# notices -- never invented. key_dates_json is left empty where the only
# known date was itself postponed with no replacement announced yet.
EXAM_SEEDS = [
    {
        "notices": [DSO_NOTICE],
        "status": "interview_scheduled",
        "vacancy_count": None,
        "key_dates_json": {"interview": DSO_NOTICE.effective_date},
    },
    {
        "notices": [CCE_POSTPONEMENT_NOTICE, CCE_CORRIGENDUM_NOTICE],
        "status": "postponed",
        "vacancy_count": 1186,
        "key_dates_json": None,
    },
]


def _upsert_source(conn) -> int:
    config = get_source_config("bpsc_bihar")
    conn.execute(
        """
        INSERT INTO sources (source_id, display_name, state, config_json, active)
        VALUES (%s, %s, %s, %s, true)
        ON CONFLICT (source_id) DO UPDATE SET config_json = EXCLUDED.config_json
        """,
        (config["source_id"], config["display_name"], config["state"], json.dumps(config)),
    )
    return conn.execute("SELECT id FROM sources WHERE source_id = %s", (config["source_id"],)).fetchone()["id"]


def _upsert_exam(conn, source_pk: int, first_notice: ExtractedNotice, status: str, vacancy_count: Optional[int], key_dates_json: Optional[dict]) -> int:
    existing = conn.execute(
        "SELECT id FROM exams WHERE source_id = %s AND name = %s",
        (source_pk, first_notice.exam_name),
    ).fetchone()
    if existing:
        print(f"Exam '{first_notice.exam_name}' already exists (id={existing['id']}), reusing.")
        return existing["id"]

    exam_pk = conn.execute(
        """
        INSERT INTO exams (source_id, name, advt_no, category, status, vacancy_count, key_dates_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            source_pk,
            first_notice.exam_name,
            first_notice.advt_no,
            first_notice.category,
            status,
            vacancy_count,
            json.dumps(key_dates_json) if key_dates_json else None,
        ),
    ).fetchone()["id"]
    print(f"Inserted exam id={exam_pk}: {first_notice.exam_name}")
    return exam_pk


def _upsert_notice(conn, exam_pk: int, notice: ExtractedNotice):
    existing = conn.execute(
        "SELECT id FROM notices WHERE exam_id = %s AND source_url = %s",
        (exam_pk, notice.source_url),
    ).fetchone()
    if existing:
        print(f"  Notice {notice.source_url} already exists (id={existing['id']}), skipping.")
        return

    reviewed = not needs_human_review(notice)
    notice_pk = conn.execute(
        """
        INSERT INTO notices (
            exam_id, source_url, change_type, summary_plain_language,
            old_value, new_value, effective_date, confidence, reviewed
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            exam_pk,
            notice.source_url,
            notice.change_type,
            notice.summary_plain_language,
            notice.old_value,
            notice.new_value,
            notice.effective_date,
            notice.confidence,
            reviewed,
        ),
    ).fetchone()["id"]
    print(f"  Inserted notice id={notice_pk} (change_type={notice.change_type}, reviewed={reviewed})")


def seed():
    with get_connection() as conn:
        source_pk = _upsert_source(conn)
        for exam_seed in EXAM_SEEDS:
            notices = exam_seed["notices"]
            exam_pk = _upsert_exam(conn, source_pk, notices[0], exam_seed["status"], exam_seed["vacancy_count"], exam_seed["key_dates_json"])
            for notice in notices:
                _upsert_notice(conn, exam_pk, notice)


if __name__ == "__main__":
    seed()
