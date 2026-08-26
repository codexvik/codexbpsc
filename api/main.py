"""
Public API (tech architecture doc, section 12 / 10): exams, notices,
subscribe, eligibility check, result search. Every query scopes to a
source_id so a second source added later can never leak into another
source's citizen-facing view (section 11).

Not built here (Phase 1+, per PRD section 7): the government dashboard API
(gov_dashboard_api.py). Do not add it without an explicit go-ahead.

Run: uvicorn api.main:app --reload
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

# Must run before api.admin is imported: the admin panel's extraction/notify
# triggers (2026-08-25) call extraction.extractor and notifications.telegram_sender,
# both of which read ANTHROPIC_API_KEY / TELEGRAM_BOT_TOKEN from the process
# environment at call time. .env / .env.local are gitignored; load_dotenv()
# is a no-op if neither exists.
load_dotenv()
load_dotenv(".env.local")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg import errors as pg_errors

from api.admin import router as admin_router
from api.discovery import board_metadata, compute_next_key_date
from api.eligibility import evaluate_eligibility
from api.schemas import (
    AlertItem,
    CallbackRequest,
    CallbackRequestResponse,
    EligibilityCheckRequest,
    EligibilityCheckResponse,
    ExamDetail,
    ExamSummary,
    NoticeOut,
    ResultSearchResponse,
    SubscribeRequest,
    SubscribeResponse,
)
from db.connection import get_connection

app = FastAPI(title="Codex BPSC API", version="0.1.0")

# The frontend (frontend/, Vite dev server) calls this API directly from
# browser-side JS. Restricted to known dev origins, not "*".
_default_origins = "http://127.0.0.1:5173,http://localhost:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FRONTEND_ORIGIN", _default_origins).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Internal review admin (api/admin.py) -- server-rendered, no JS, so CORS
# above doesn't apply to it; a human navigates to it directly.
app.include_router(admin_router)


def _get_source_id_pk(conn, source_id: str) -> int:
    row = conn.execute("SELECT id FROM sources WHERE source_id = %s AND active", (source_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown or inactive source_id: {source_id!r}")
    return row["id"]


@app.get("/exams", response_model=list[ExamSummary])
def list_exams(source_id: str = Query(default="bpsc_bihar")):
    with get_connection() as conn:
        source_pk = _get_source_id_pk(conn, source_id)
        rows = conn.execute(
            """
            SELECT e.id, e.name, e.advt_no, e.category, e.vacancy_count, e.status,
                   e.key_dates_json, s.config_json,
                   (SELECT n.summary_plain_language FROM notices n
                    WHERE n.exam_id = e.id AND n.reviewed
                    ORDER BY n.detected_at DESC LIMIT 1) AS latest_change_snippet,
                   (SELECT count(*) FROM notices n WHERE n.exam_id = e.id AND n.reviewed) AS notice_count,
                   (SELECT count(*) FROM notices n WHERE n.exam_id = e.id AND n.reviewed AND n.archive_url IS NOT NULL) > 0 AS verified
            FROM exams e
            JOIN sources s ON s.id = e.source_id
            WHERE e.source_id = %s AND e.visible_on_b2c
            ORDER BY e.created_at DESC
            """,
            (source_pk,),
        ).fetchall()

        results = []
        for row in rows:
            meta = board_metadata(row.pop("config_json"))
            label, value = compute_next_key_date(row.pop("key_dates_json"))
            results.append(
                ExamSummary(
                    **row,
                    board_category=meta["board_category"],
                    board_monogram=meta["board_monogram"],
                    next_key_date_label=label,
                    next_key_date_value=value,
                )
            )
        return results


@app.get("/exams/{exam_id}", response_model=ExamDetail)
def get_exam_detail(exam_id: int, source_id: str = Query(default="bpsc_bihar")):
    with get_connection() as conn:
        source_pk = _get_source_id_pk(conn, source_id)
        exam = conn.execute(
            """
            SELECT e.*, s.config_json,
                   (SELECT count(*) FROM notices n WHERE n.exam_id = e.id AND n.reviewed AND n.archive_url IS NOT NULL) > 0 AS verified
            FROM exams e
            JOIN sources s ON s.id = e.source_id
            WHERE e.id = %s AND e.source_id = %s AND e.visible_on_b2c
            """,
            (exam_id, source_pk),
        ).fetchone()
        if exam is None:
            raise HTTPException(status_code=404, detail="Exam not found")

        notices = conn.execute(
            """
            SELECT * FROM notices
            WHERE exam_id = %s AND reviewed
            ORDER BY detected_at DESC
            """,
            (exam_id,),
        ).fetchall()

        meta = board_metadata(exam.pop("config_json"))
        label, value = compute_next_key_date(exam.get("key_dates_json"))

        return ExamDetail(
            **exam,
            **meta,
            next_key_date_label=label,
            next_key_date_value=value,
            notices=[NoticeOut(**n) for n in notices],
        )


@app.get("/notices", response_model=list[NoticeOut])
def list_notices(exam_id: int = Query(...)):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM notices
            WHERE exam_id = %s AND reviewed
            ORDER BY detected_at DESC
            """,
            (exam_id,),
        ).fetchall()
        return rows


@app.get("/notices/recent", response_model=list[AlertItem])
def recent_notices(source_id: str = Query(default="bpsc_bihar"), limit: int = Query(default=10, le=50)):
    """Home page's notification strip -- real recent notices across every
    tracked exam, not the per-exam feed /notices serves."""
    with get_connection() as conn:
        source_pk = _get_source_id_pk(conn, source_id)
        rows = conn.execute(
            """
            SELECT n.id, n.exam_id, e.name AS exam_name, n.source_url, n.change_type,
                   n.summary_plain_language, n.effective_date, n.confidence,
                   n.archive_url, n.detected_at
            FROM notices n
            JOIN exams e ON e.id = n.exam_id
            WHERE e.source_id = %s AND n.reviewed
            ORDER BY n.detected_at DESC
            LIMIT %s
            """,
            (source_pk, limit),
        ).fetchall()
        return rows


@app.post("/subscribe", response_model=SubscribeResponse)
def subscribe(req: SubscribeRequest):
    with get_connection() as conn:
        exam = conn.execute("SELECT id FROM exams WHERE id = %s", (req.exam_id,)).fetchone()
        if exam is None:
            raise HTTPException(status_code=404, detail="Exam not found")

        try:
            conn.execute(
                """
                INSERT INTO subscriptions (phone_number, exam_id, active)
                VALUES (%s, %s, true)
                ON CONFLICT (phone_number, exam_id) DO UPDATE SET active = true
                """,
                (req.phone_number, req.exam_id),
            )
        except pg_errors.ForeignKeyViolation:
            raise HTTPException(status_code=404, detail="Exam not found")

        return SubscribeResponse(exam_id=req.exam_id, phone_number=req.phone_number, active=True)


@app.post("/unsubscribe", response_model=SubscribeResponse)
def unsubscribe(req: SubscribeRequest):
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE subscriptions SET active = false
            WHERE phone_number = %s AND exam_id = %s
            RETURNING phone_number, exam_id
            """,
            (req.phone_number, req.exam_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return SubscribeResponse(exam_id=req.exam_id, phone_number=req.phone_number, active=False)


@app.post("/eligibility-check", response_model=EligibilityCheckResponse)
def eligibility_check(req: EligibilityCheckRequest):
    with get_connection() as conn:
        exam = conn.execute(
            "SELECT eligibility_json FROM exams WHERE id = %s", (req.exam_id,)
        ).fetchone()
        if exam is None:
            raise HTTPException(status_code=404, detail="Exam not found")

        eligible, reason = evaluate_eligibility(
            exam["eligibility_json"], degree=req.degree, age=req.age, category=req.category
        )
        return EligibilityCheckResponse(exam_id=req.exam_id, eligible=eligible, reason=reason)


@app.get("/results", response_model=ResultSearchResponse)
def search_result(exam_id: int = Query(...), roll_number: str = Query(...)):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT r.roll_number, r.status, r.rank, n.source_url
            FROM results r
            LEFT JOIN notices n ON n.id = r.source_notice_id
            WHERE r.exam_id = %s AND r.roll_number = %s
            """,
            (exam_id, roll_number),
        ).fetchone()

        if row is None:
            return ResultSearchResponse(found=False, roll_number=roll_number)

        return ResultSearchResponse(
            found=True,
            roll_number=row["roll_number"],
            status=row["status"],
            rank=row["rank"],
            source_notice_url=row["source_url"],
        )


@app.get("/my-alerts", response_model=list[AlertItem])
def my_alerts(phone_number: str = Query(...)):
    """
    The 'My Alerts' page (design decision 2026-08-24): phone-number lookup,
    no login. A personal feed across every exam this number is actively
    subscribed to -- WhatsApp remains the push channel; this is the
    pull/on-demand equivalent for someone who wants to check the site
    directly instead.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT n.id, n.exam_id, e.name AS exam_name, n.source_url, n.change_type,
                   n.summary_plain_language, n.effective_date, n.confidence,
                   n.archive_url, n.detected_at
            FROM notices n
            JOIN exams e ON e.id = n.exam_id
            JOIN subscriptions s ON s.exam_id = n.exam_id
            WHERE s.phone_number = %s AND s.active AND n.reviewed
            ORDER BY n.detected_at DESC
            """,
            (phone_number,),
        ).fetchall()
        return rows


@app.post("/callback-request", response_model=CallbackRequestResponse)
def request_callback(req: CallbackRequest):
    with get_connection() as conn:
        if req.exam_id is not None:
            exam = conn.execute("SELECT id FROM exams WHERE id = %s", (req.exam_id,)).fetchone()
            if exam is None:
                raise HTTPException(status_code=404, detail="Exam not found")

        row = conn.execute(
            """
            INSERT INTO callback_requests (phone_number, exam_id)
            VALUES (%s, %s)
            RETURNING id, phone_number, exam_id
            """,
            (req.phone_number, req.exam_id),
        ).fetchone()

        return CallbackRequestResponse(**row)
