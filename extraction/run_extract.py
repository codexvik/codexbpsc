"""
Demo/CLI entry point for step 2: run the extraction service against real,
currently-changed BPSC notices and show the structured output + the
human-review gate's decision.

Usage (from repo root, with the venv active and ANTHROPIC_API_KEY set):
    python -m extraction.run_extract [source_id] [--limit N]
    python -m extraction.run_extract [source_id] --url URL [--url URL ...]

Behavior:
- Default mode: reuses the ingestion service (poller + page_fetcher) to grab
  the same "changed" URLs step 1 detects -- this proves steps 1 and 2 work
  together against live data, per the build order.
- --url mode: skips the sitemap diff and fetches/extracts exactly the URLs
  given, for spot-checking a specific known notification (e.g. a current
  one found by browsing the site) rather than whatever the sitemap diff
  happens to return first.
- Runs each fetched page through the extractor.
- Prints the structured record and whether the human-review gate flags it.
- Does NOT persist anything or send notifications -- that's step 4.
"""

from __future__ import annotations

import argparse
import logging
import sys

from extraction.extractor import (
    DEFAULT_MODEL,
    HUMAN_REVIEW_GATE_ENABLED,
    extract_notice,
    extract_notice_from_pdf,
    needs_human_review,
)
from extraction.pdf_handler import fetch_pdf_bytes
from ingestion.page_fetcher import fetch_page
from ingestion.poller import detect_changes
from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import get_source_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _is_pdf_url(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf")


def extract_and_print(url: str, source_id: str, config: dict, rate_limiter: RateLimiter):
    if _is_pdf_url(url):
        rate_limiter.wait()
        try:
            pdf_bytes = fetch_pdf_bytes(
                url, user_agent=config["user_agent"], timeout_seconds=config["request_timeout_seconds"]
            )
        except Exception as exc:
            logger.warning("PDF fetch failed for %s: %s", url, exc)
            return

        detail_line = f"pdf_bytes: {len(pdf_bytes)} (sent to Claude as a document input -- reads scanned PDFs via vision)"
        try:
            notice = extract_notice_from_pdf(pdf_bytes=pdf_bytes, source_url=url, source_id=source_id)
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", url, exc)
            return
    else:
        try:
            page = fetch_page(url, source_id, rate_limiter)
        except Exception as exc:
            logger.warning("Fetch failed for %s: %s", url, exc)
            return

        detail_line = f"page_title: {page.title} | page_text_chars: {len(page.text_content)}"
        try:
            notice = extract_notice(
                page_text=f"{page.title}\n\n{page.text_content}",
                source_url=url,
                source_id=source_id,
            )
        except Exception as exc:
            logger.error("Extraction failed for %s: %s", url, exc)
            return

    flagged = needs_human_review(notice)

    print(f"\n--- {notice.source_url} ---")
    print(detail_line)
    print(notice.model_dump_json(indent=2))
    print(
        f"needs_human_review: {flagged}"
        + (" (BLOCKS notification until reviewed)" if flagged else " (can proceed to notification)")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id", nargs="?", default="bpsc_bihar")
    parser.add_argument("--limit", type=int, default=3, help="How many changed pages to extract (default mode)")
    parser.add_argument("--url", action="append", help="Extract this exact URL instead of using the sitemap diff. Repeatable. Handles .pdf URLs directly.")
    args = parser.parse_args()

    config = get_source_config(args.source_id)
    rate_limiter = RateLimiter(config["rate_limit_seconds"])

    logger.info(
        "Human review gate: %s (model=%s)",
        "ON" if HUMAN_REVIEW_GATE_ENABLED else "OFF",
        DEFAULT_MODEL,
    )

    if args.url:
        logger.info("Extracting %d explicitly-given URL(s)...", len(args.url))
        for url in args.url:
            extract_and_print(url, args.source_id, config, rate_limiter)
        return

    logger.info("Detecting changed URLs for source_id=%s...", args.source_id)
    changed = detect_changes(args.source_id, rate_limiter)
    if not changed:
        logger.info(
            "No changed URLs detected. Run `python -m ingestion.run_poll --dry-run` first, "
            "or delete ingestion/ingestion_state.db to reset state."
        )
        return

    to_process = changed[: args.limit]
    logger.info("Extracting %d of %d changed pages...", len(to_process), len(changed))

    for c in to_process:
        extract_and_print(c.url, args.source_id, config, rate_limiter)


if __name__ == "__main__":
    sys.exit(main())
