"""
Discovery/browse computed fields (2026-08-24 redesign) -- board metadata
comes straight from source_config (never guessed per exam); next_key_date
picks the nearest date out of an exam's key_dates_json so the frontend
doesn't have to special-case which key means what.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


def board_metadata(config_json: Optional[dict]) -> dict:
    config_json = config_json or {}
    return {
        "board_category": config_json.get("board_category"),
        "board_monogram": config_json.get("monogram"),
        "board_name": config_json.get("display_name"),
        "board_name_hindi": config_json.get("display_name_hindi"),
        "official_website": config_json.get("official_website"),
    }


def compute_next_key_date(key_dates_json: Optional[dict]) -> tuple:
    """
    Returns (label, iso_date_string) for the soonest upcoming date in
    key_dates_json, or the most recent past date if everything's already
    passed, or (None, None) if there's nothing to show.
    """
    if not key_dates_json:
        return None, None

    today = date.today()
    parsed = []
    for label, value in key_dates_json.items():
        try:
            parsed.append((label, datetime.strptime(value, "%Y-%m-%d").date()))
        except (ValueError, TypeError):
            continue

    if not parsed:
        return None, None

    upcoming = sorted((p for p in parsed if p[1] >= today), key=lambda p: p[1])
    if upcoming:
        label, d = upcoming[0]
    else:
        label, d = max(parsed, key=lambda p: p[1])

    return label, d.isoformat()
