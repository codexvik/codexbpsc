"""
Persists an already-extracted ExtractedNotice into Postgres -- the missing
link between extraction.run_extract (which only prints) and the database.
Needed so extraction can be triggered from the admin panel (api/admin.py),
not just the CLI, and have the result actually land where the review queue
and citizen-facing API can see it.

Exam matching follows the same rule as ingestion.exam_registry_sync: match
on (source_id, advt_no) when advt_no is present, else (source_id, name) --
verified 2026-08-25 that name-only matching creates duplicates across
sources that phrase the same exam differently.
"""

from __future__ import annotations

from extraction.extractor import needs_human_review
from extraction.schema import ExtractedNotice


def _get_source_pk(conn, source_id: str) -> int:
    row = conn.execute("SELECT id FROM sources WHERE source_id = %s", (source_id,)).fetchone()
    if row is None:
        raise ValueError(f"No sources row for source_id={source_id!r} -- run db.seed first")
    return row["id"]


def _find_or_create_exam(conn, source_pk: int, notice: ExtractedNotice) -> int:
    if notice.advt_no:
        existing = conn.execute(
            "SELECT id FROM exams WHERE source_id = %s AND advt_no = %s",
            (source_pk, notice.advt_no),
        ).fetchone()
    else:
        existing = conn.execute(
            "SELECT id FROM exams WHERE source_id = %s AND advt_no IS NULL AND name = %s",
            (source_pk, notice.exam_name),
        ).fetchone()
    if existing:
        return existing["id"]

    return conn.execute(
        """
        INSERT INTO exams (source_id, name, advt_no, category)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (source_pk, notice.exam_name, notice.advt_no, notice.category),
    ).fetchone()["id"]


def persist_notice(conn, notice: ExtractedNotice) -> tuple[int, bool]:
    """
    Upserts the exam and inserts the notice if it isn't already there.
    Returns (notice_id, created) -- created=False means this exact
    (exam, source_url) pair was already persisted and nothing changed,
    so a re-run of extraction on the same URL is a safe no-op.
    """
    source_pk = _get_source_pk(conn, notice.source_id)
    exam_pk = _find_or_create_exam(conn, source_pk, notice)

    existing = conn.execute(
        "SELECT id FROM notices WHERE exam_id = %s AND source_url = %s",
        (exam_pk, notice.source_url),
    ).fetchone()
    if existing:
        return existing["id"], False

    # reviewed=true here means the gate passed it through with no human
    # involved -- reviewed_at is still stamped in that case (CASE below) so
    # it reads as "the moment this notice's visibility was decided," not
    # only "the moment a human clicked a button." That's what lets it show
    # up in the admin's Review History with a Send-to-Subscribers button --
    # otherwise a gate-passed notice would go live but be untriggerable from
    # the admin panel at all.
    reviewed = not needs_human_review(notice)
    notice_pk = conn.execute(
        """
        INSERT INTO notices (
            exam_id, source_url, change_type, summary_plain_language,
            old_value, new_value, effective_date, confidence, reviewed, reviewed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s THEN now() ELSE NULL END)
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
            reviewed,
        ),
    ).fetchone()["id"]
    return notice_pk, True
