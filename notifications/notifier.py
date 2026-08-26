"""
Trigger logic (tech architecture doc, section 7): reviewed notice ->
subscriber lookup by exam_id -> send. Channel-agnostic on purpose --
Telegram is wired today; WhatsApp (parked, see docs/backlog.md) plugs in
as a second delivery branch here once Meta Business API access exists,
without touching the trigger logic itself.
"""

from __future__ import annotations

import logging

from db.connection import get_connection
from notifications.telegram_sender import send_message

logger = logging.getLogger(__name__)


def _format_message(exam_name: str, summary: str, source_url: str) -> str:
    return f"{exam_name}\n\n{summary}\n\nSource: {source_url}"


def notify_subscribers(notice_id: int) -> dict:
    """
    Sends the given notice to every active subscriber of its exam. Only
    call this for notices that have already passed the human-review gate
    (extraction.extractor.needs_human_review) -- this function does not
    check that itself, since by the time a notice_id exists to notify
    about, that decision should already be made.

    Returns {"telegram_sent": N, "telegram_failed": N, "no_channel": N} --
    "no_channel" counts subscribers with only a phone_number and no
    telegram_chat_id, since WhatsApp delivery isn't built yet (backlog).
    """
    with get_connection() as conn:
        notice = conn.execute(
            """
            SELECT n.summary_plain_language, n.source_url, e.name AS exam_name, n.exam_id
            FROM notices n JOIN exams e ON e.id = n.exam_id
            WHERE n.id = %s
            """,
            (notice_id,),
        ).fetchone()
        if notice is None:
            raise ValueError(f"No notice with id={notice_id}")

        subscribers = conn.execute(
            "SELECT telegram_chat_id, phone_number FROM subscriptions WHERE exam_id = %s AND active",
            (notice["exam_id"],),
        ).fetchall()

    message = _format_message(notice["exam_name"], notice["summary_plain_language"], notice["source_url"])

    counts = {"telegram_sent": 0, "telegram_failed": 0, "no_channel": 0}
    for sub in subscribers:
        if sub["telegram_chat_id"]:
            if send_message(sub["telegram_chat_id"], message):
                counts["telegram_sent"] += 1
            else:
                counts["telegram_failed"] += 1
        elif sub["phone_number"]:
            # WhatsApp not built yet -- parked in docs/backlog.md pending
            # Meta Business API access. Logged, not silently dropped.
            logger.info(
                "Subscriber %s has no Telegram link -- WhatsApp delivery not yet built, skipping.",
                sub["phone_number"],
            )
            counts["no_channel"] += 1

    with get_connection() as conn:
        conn.execute("UPDATE notices SET notified_at = now() WHERE id = %s", (notice_id,))

    logger.info("notify_subscribers(notice_id=%d): %s", notice_id, counts)
    return counts
