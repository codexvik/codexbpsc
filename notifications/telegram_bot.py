"""
Telegram bot command loop -- this is how a Telegram chat_id gets linked to
a subscription in the first place. Unlike the web subscribe form (which
just captures a typed phone number), Telegram requires the user to
actually message the bot at least once before we can send them anything,
so /start, /exams, /subscribe, /unsubscribe, /myalerts all live here
rather than behind the public API.

Uses long-polling (getUpdates), not a webhook -- no public HTTPS endpoint
needed, which keeps this runnable from a local dev machine.

Run: python -m notifications.telegram_bot
"""

from __future__ import annotations

import logging
import time

from dotenv import load_dotenv

from db.connection import get_connection
from notifications.telegram_sender import get_updates, send_message

# Loads TELEGRAM_BOT_TOKEN (and anything else) from a local .env file if
# one exists, so the token never has to be typed into a chat transcript or
# re-supplied on every command -- see .env.local.example for the format.
# .env / .env.local are gitignored; load_dotenv() is a no-op if neither exists.
load_dotenv()
load_dotenv(".env.local")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HELP_TEXT = (
    "Commands:\n"
    "/exams -- list exams you can track\n"
    "/subscribe <exam_id> -- get alerts for an exam\n"
    "/unsubscribe <exam_id> -- stop alerts for an exam\n"
    "/myalerts -- see recent notices for what you're subscribed to"
)


def _list_exams() -> str:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, status FROM exams ORDER BY created_at DESC"
        ).fetchall()
    if not rows:
        return "No exams tracked yet."
    lines = [f"#{r['id']} -- {r['name']} ({r['status'] or 'status unknown'})" for r in rows]
    return "\n".join(lines) + "\n\nSubscribe with: /subscribe <id>"


def _subscribe(chat_id: str, exam_id: int) -> str:
    with get_connection() as conn:
        exam = conn.execute("SELECT name FROM exams WHERE id = %s", (exam_id,)).fetchone()
        if exam is None:
            return f"No exam #{exam_id}. Try /exams to see what's available."

        conn.execute(
            """
            INSERT INTO subscriptions (telegram_chat_id, exam_id, active)
            VALUES (%s, %s, true)
            ON CONFLICT (telegram_chat_id, exam_id) WHERE telegram_chat_id IS NOT NULL
            DO UPDATE SET active = true
            """,
            (chat_id, exam_id),
        )
    return f"Subscribed to {exam['name']}. You'll get an alert here when there's a reviewed update."


def _unsubscribe(chat_id: str, exam_id: int) -> str:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE subscriptions SET active = false
            WHERE telegram_chat_id = %s AND exam_id = %s
            RETURNING id
            """,
            (chat_id, exam_id),
        ).fetchone()
    if row is None:
        return f"You weren't subscribed to #{exam_id}."
    return f"Unsubscribed from #{exam_id}."


def _my_alerts(chat_id: str) -> str:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.name AS exam_name, n.summary_plain_language, n.detected_at
            FROM notices n
            JOIN exams e ON e.id = n.exam_id
            JOIN subscriptions s ON s.exam_id = n.exam_id
            WHERE s.telegram_chat_id = %s AND s.active AND n.reviewed
            ORDER BY n.detected_at DESC
            LIMIT 10
            """,
            (chat_id,),
        ).fetchall()
    if not rows:
        return "No alerts yet for your subscriptions."
    lines = [f"[{r['exam_name']}] {r['summary_plain_language']}" for r in rows]
    return "\n\n".join(lines)


def handle_message(chat_id: str, text: str) -> str:
    text = (text or "").strip()
    parts = text.split()
    command = parts[0].lower() if parts else ""

    if command == "/start":
        return "Welcome. " + HELP_TEXT
    if command == "/exams":
        return _list_exams()
    if command == "/subscribe":
        if len(parts) < 2 or not parts[1].isdigit():
            return "Usage: /subscribe <exam_id> -- see /exams for ids."
        return _subscribe(chat_id, int(parts[1]))
    if command == "/unsubscribe":
        if len(parts) < 2 or not parts[1].isdigit():
            return "Usage: /unsubscribe <exam_id>"
        return _unsubscribe(chat_id, int(parts[1]))
    if command == "/myalerts":
        return _my_alerts(chat_id)

    return "Didn't recognize that. " + HELP_TEXT


def run_forever():
    logger.info("Telegram bot starting (long-polling)...")
    offset = None
    while True:
        try:
            updates = get_updates(offset=offset)
        except Exception as exc:
            logger.warning("getUpdates failed: %s -- retrying in 5s", exc)
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")
            if not message or "text" not in message:
                continue

            chat_id = str(message["chat"]["id"])
            reply = handle_message(chat_id, message["text"])
            send_message(chat_id, reply)


if __name__ == "__main__":
    run_forever()
