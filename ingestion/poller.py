"""
Generic, config-driven sitemap poller (tech architecture doc, section 4).

Logic, per configured source:
1. Fetch the source's configured sitemap file(s), or fall back to a
   configured listing-page diff if the source has no sitemap.
2. Parse <loc>/<lastmod> pairs; compare against last-seen values stored
   per source.
3. Return the set of new/changed URLs for the caller to queue for fetching.

Nothing in this module is BPSC-specific — every BPSC detail comes from
source_config.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import get_source_config
from ingestion.state_store import connect, get_all_seen

logger = logging.getLogger(__name__)


@dataclass
class SitemapEntry:
    url: str
    lastmod: str


@dataclass
class ChangedEntry:
    url: str
    lastmod: str
    previous_lastmod: str | None
    is_new: bool


def _fetch(url: str, config: dict, rate_limiter: RateLimiter) -> str:
    rate_limiter.wait()
    headers = {"User-Agent": config["user_agent"]}
    resp = requests.get(url, headers=headers, timeout=config["request_timeout_seconds"])
    resp.raise_for_status()
    return resp.text


def parse_sitemap_xml(xml_text: str) -> list:
    """Parse a <urlset> sitemap file into SitemapEntry records."""
    soup = BeautifulSoup(xml_text, "xml")
    entries = []
    for url_tag in soup.find_all("url"):
        loc_tag = url_tag.find("loc")
        lastmod_tag = url_tag.find("lastmod")
        if loc_tag is None or lastmod_tag is None:
            continue
        entries.append(
            SitemapEntry(url=loc_tag.get_text(strip=True), lastmod=lastmod_tag.get_text(strip=True))
        )
    return entries


def fetch_all_sitemap_entries(source_id: str, rate_limiter: RateLimiter = None) -> list:
    """Fetch and parse every configured sitemap file for a source."""
    config = get_source_config(source_id)
    if rate_limiter is None:
        rate_limiter = RateLimiter(config["rate_limit_seconds"])

    if not config["has_sitemap"]:
        raise NotImplementedError(
            f"source_id={source_id!r} has has_sitemap=False; use the listing-page "
            "fallback path (listing_fallback_url) instead of fetch_all_sitemap_entries()."
        )

    all_entries = []
    for sitemap_url in config["sitemap_urls"]:
        logger.info("Fetching sitemap %s", sitemap_url)
        try:
            xml_text = _fetch(sitemap_url, config, rate_limiter)
        except requests.RequestException as exc:
            logger.warning("Failed to fetch sitemap %s: %s", sitemap_url, exc)
            continue
        entries = parse_sitemap_xml(xml_text)
        logger.info("  -> %d entries", len(entries))
        all_entries.extend(entries)
    return all_entries


def detect_changes(source_id: str, rate_limiter: RateLimiter = None) -> list:
    """
    Fetch current sitemap state for a source and diff it against last-seen
    lastmod values in the state store. Does NOT persist the new state —
    callers should only mark a URL seen (state_store.mark_seen) after it has
    been successfully fetched/processed downstream, so a failed fetch
    doesn't silently drop a change.
    """
    entries = fetch_all_sitemap_entries(source_id, rate_limiter)

    with connect() as conn:
        previously_seen = get_all_seen(conn, source_id)

    changed = []
    for entry in entries:
        previous_lastmod = previously_seen.get(entry.url)
        if previous_lastmod is None:
            changed.append(ChangedEntry(entry.url, entry.lastmod, None, is_new=True))
        elif previous_lastmod != entry.lastmod:
            changed.append(ChangedEntry(entry.url, entry.lastmod, previous_lastmod, is_new=False))

    return changed
