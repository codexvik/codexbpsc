"""
Real notice discovery (2026-08-25 -- replaces the sitemap-based poller for
notice_poll). Verified live: BPSC's own notification sitemap
(bsc_notification-sitemap*.xml -> /notifications/{id}/ pages) points at
pages whose real text is injected by JavaScript after load -- every one
checked (5/5 sampled) has an empty <div class="entry-content"> when fetched
plainly, so nothing usable was ever extractable from that source. The
site's own "What's New" page (config's notice_feed_url) is server-rendered
with direct links straight to the real PDF notices and real descriptive
link text -- e.g. "Important Notice :- Regarding Postponement of 72nd CCE
(Preliminary) Competitive Examination." -- and needs no JS execution to
read. Confirmed the CCE postponement and corrigendum PDFs already verified
working (db/seed.py) are both linked from here.

This is a small, un-paginated feed (~10-20 items, whatever's currently
"new" on BPSC's site) rather than a deep archive -- correct for change
detection (spot something new -> act on it), not for browsing history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ingestion.source_config import get_source_config

logger = logging.getLogger(__name__)


@dataclass
class NoticeLink:
    url: str
    title: str


def fetch_notice_feed(source_id: str) -> list:
    """Fetches config['notice_feed_url'] and returns every distinct PDF
    link on it as a NoticeLink(url, title), title being the real link text
    BPSC itself wrote for that notice."""
    config = get_source_config(source_id)
    feed_url = config["notice_feed_url"]

    resp = requests.get(feed_url, headers={"User-Agent": config["user_agent"]}, timeout=config["request_timeout_seconds"])
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls = set()
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().split("?")[0].endswith(".pdf"):
            continue
        full_url = urljoin(feed_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        title = a.get_text(" ", strip=True) or full_url
        links.append(NoticeLink(url=full_url, title=title))

    return links
