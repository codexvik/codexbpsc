"""
Telegram delivery (tech architecture doc section 7's mechanics, adapted --
Telegram chosen first per 2026-08-24 decision: no business verification, no
message-template approval lead time, unlike WhatsApp -- see docs/backlog.md
for the WhatsApp channel, parked pending Meta Business API access).

Requires TELEGRAM_BOT_TOKEN in the environment. Get one free from
@BotFather in Telegram: /newbot, follow the prompts, it hands you a token.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    pass


def _get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramError(
            "TELEGRAM_BOT_TOKEN not set. Create a bot via @BotFather in Telegram "
            "(/newbot) and export the token it gives you."
        )
    return token


def send_message(chat_id: str, text: str, timeout_seconds: int = 15) -> bool:
    """
    Sends a message to a chat_id. Returns True on success, False on any
    failure (never raises for ordinary delivery failures -- one
    subscriber's blocked/invalid chat shouldn't break sending to everyone
    else in the same fan-out).
    """
    try:
        token = _get_token()
    except TelegramError as exc:
        logger.warning(str(exc))
        return False

    try:
        resp = requests.post(
            f"{API_BASE}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        logger.warning("Telegram send failed for chat_id=%s: %s", chat_id, exc)
        return False

    if not resp.ok:
        logger.warning("Telegram send failed for chat_id=%s: HTTP %d %s", chat_id, resp.status_code, resp.text[:200])
        return False

    return True


def get_updates(offset: Optional[int] = None, timeout_seconds: int = 30) -> list:
    """Long-poll for new messages sent to the bot. Returns the raw `result` list."""
    token = _get_token()
    params = {"timeout": timeout_seconds}
    if offset is not None:
        params["offset"] = offset

    resp = requests.get(
        f"{API_BASE}/bot{token}/getUpdates", params=params, timeout=timeout_seconds + 10
    )
    resp.raise_for_status()
    return resp.json().get("result", [])
