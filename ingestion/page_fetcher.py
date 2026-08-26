"""
Fetches full page content for queued URLs only (tech architecture doc,
section 4, step 4). Linked PDFs are identified here and handed off by
reference — actually downloading/parsing PDF content is the Extraction
Service's job (extraction/pdf_handler.py, per the section 12 repo layout),
not ingestion's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import get_source_config

logger = logging.getLogger(__name__)


@dataclass
class FetchedPage:
    url: str
    status_code: int
    html: str
    title: str | None
    text_content: str
    pdf_links: list = field(default_factory=list)


def fetch_page(url: str, source_id: str, rate_limiter: RateLimiter = None) -> FetchedPage:
    config = get_source_config(source_id)
    if rate_limiter is None:
        rate_limiter = RateLimiter(config["rate_limit_seconds"])

    rate_limiter.wait()
    headers = {"User-Agent": config["user_agent"]}
    resp = requests.get(url, headers=headers, timeout=config["request_timeout_seconds"])
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    body = soup.find("body")
    text_content = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

    pdf_links = sorted(
        {
            urljoin(url, a["href"])
            for a in soup.find_all("a", href=True)
            if a["href"].lower().split("?")[0].endswith(".pdf")
        }
    )

    return FetchedPage(
        url=url,
        status_code=resp.status_code,
        html=resp.text,
        title=title,
        text_content=text_content,
        pdf_links=pdf_links,
    )


def fetch_pages(urls: list, source_id: str, rate_limiter: RateLimiter = None) -> list:
    config = get_source_config(source_id)
    if rate_limiter is None:
        rate_limiter = RateLimiter(config["rate_limit_seconds"])

    pages = []
    for url in urls:
        try:
            pages.append(fetch_page(url, source_id, rate_limiter))
        except requests.RequestException as exc:
            logger.warning("Failed to fetch page %s: %s", url, exc)
    return pages
