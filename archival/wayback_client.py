"""
Wayback Machine archival (tech architecture doc, section 8): every notice
detection triggers a Save Page Now capture; the returned snapshot URL is
what notices.archive_url stores, and what the notice feed's "verified" link
points to (design doc, section 3.2) -- an independent, third-party record
that neither we nor BPSC can quietly alter afterward.

Requires an Internet Archive account's S3-like API keys (free) from
https://archive.org/account/s3.php, via IA_ACCESS_KEY / IA_SECRET_KEY env
vars. The unauthenticated /save/ endpoint exists but is aggressively
rate-limited -- especially from datacenter/cloud IPs -- so this always
authenticates rather than relying on it.

Request/response shape verified against palewire/savepagenow (a widely used
open-source SPN client), not guessed: GET https://web.archive.org/save/<url>
with an `Authorization: LOW {access_key}:{secret_key}` header; the resulting
snapshot path comes back in the Content-Location response header.
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

SAVE_URL = "https://web.archive.org/save/"
USER_AGENT = "CodexBPSC-Archival/0.1 (+contact: research/pilot bot; polite crawl)"


class ArchivalError(Exception):
    pass


def _get_credentials() -> tuple[str, str]:
    access_key = os.environ.get("IA_ACCESS_KEY")
    secret_key = os.environ.get("IA_SECRET_KEY")
    if not access_key or not secret_key:
        raise ArchivalError(
            "IA_ACCESS_KEY / IA_SECRET_KEY not set. Get free keys from "
            "https://archive.org/account/s3.php (requires a free archive.org account)."
        )
    return access_key, secret_key


def archive_url(target_url: str, timeout_seconds: int = 45) -> Optional[str]:
    """
    Requests a fresh Wayback Machine capture of target_url and returns the
    resulting snapshot URL, or None if archival failed. Never raises for
    ordinary failures -- archival is a trust-layer add-on, not a hard
    dependency; ingestion/extraction must keep working if archive.org is
    down, rate-limited, or credentials are missing.
    """
    try:
        access_key, secret_key = _get_credentials()
    except ArchivalError as exc:
        logger.warning(str(exc))
        return None

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Authorization": f"LOW {access_key}:{secret_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    request_url = SAVE_URL + target_url

    try:
        response = requests.get(request_url, headers=headers, timeout=timeout_seconds)
    except requests.RequestException as exc:
        logger.warning("Archival request failed for %s: %s", target_url, exc)
        return None

    if response.status_code == 429:
        logger.warning("Archival rate-limited for %s (HTTP 429)", target_url)
        return None

    if not response.ok:
        logger.warning("Archival failed for %s: HTTP %d", target_url, response.status_code)
        return None

    content_location = response.headers.get("Content-Location")
    if content_location:
        return urljoin("https://web.archive.org", content_location)

    link_header = response.headers.get("Link", "")
    for part in link_header.split(","):
        if 'rel="memento"' in part:
            start = part.find("<") + 1
            end = part.find(">")
            if start > 0 and end > start:
                return part[start:end]

    logger.warning("Archival response for %s had no Content-Location or memento Link header", target_url)
    return None
