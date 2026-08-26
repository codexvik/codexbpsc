"""
Demo/CLI entry point for step 1: run the ingestion service end-to-end
against live BPSC sitemap data and show what it detected.

Usage (from repo root, with the venv active):
    python -m ingestion.run_poll [source_id] [--fetch-limit N] [--dry-run]

Behavior:
- Fetches every configured sitemap for the source and diffs against
  last-seen state (SQLite, ingestion/ingestion_state.db).
- On the very first run, every URL is "new" (nothing seen before) --
  that's expected, not a bug.
- Fetches full page content for up to --fetch-limit of the changed URLs
  (default 5) to prove the fetch step works, tagged with source_id.
- Unless --dry-run, marks fetched URLs as seen so the next run only
  reports genuinely new/changed entries.
"""

from __future__ import annotations

import argparse
import logging
import sys

from ingestion.page_fetcher import fetch_page
from ingestion.poller import detect_changes
from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import get_source_config
from ingestion.state_store import connect, mark_seen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_id", nargs="?", default="bpsc_bihar")
    parser.add_argument("--fetch-limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="Don't persist last-seen state")
    args = parser.parse_args()

    config = get_source_config(args.source_id)
    rate_limiter = RateLimiter(config["rate_limit_seconds"])

    logger.info("Polling source_id=%s (%s)", config["source_id"], config["display_name"])
    changed = detect_changes(args.source_id, rate_limiter)

    new_count = sum(1 for c in changed if c.is_new)
    updated_count = len(changed) - new_count
    logger.info(
        "Detected %d changed URLs (%d new, %d updated lastmod) out of the full sitemap set",
        len(changed), new_count, updated_count,
    )

    if not changed:
        logger.info("Nothing new since last run. Delete ingestion/ingestion_state.db to reset state.")
        return

    print("\nChanged / new URLs:")
    for c in changed:
        status = "NEW" if c.is_new else f"UPDATED (was {c.previous_lastmod})"
        print(f"  [{status}] {c.url}  lastmod={c.lastmod}")

    to_fetch = changed[: args.fetch_limit]
    print(f"\nFetching {len(to_fetch)} of {len(changed)} changed pages (--fetch-limit={args.fetch_limit})...\n")

    with connect() as conn:
        for c in to_fetch:
            try:
                page = fetch_page(c.url, args.source_id, rate_limiter)
            except Exception as exc:
                logger.warning("Fetch failed for %s: %s", c.url, exc)
                continue

            print(f"--- {page.url} ---")
            print(f"  status: {page.status_code}")
            print(f"  title: {page.title}")
            print(f"  text_content: {len(page.text_content)} chars")
            print(f"  pdf_links: {page.pdf_links[:3]}{' ...' if len(page.pdf_links) > 3 else ''}")
            preview = " ".join(page.text_content.split())[:200]
            print(f"  preview: {preview}...\n")

            if not args.dry_run:
                mark_seen(conn, args.source_id, c.url, c.lastmod)

    if args.dry_run:
        print("(--dry-run: state not persisted, re-running will show the same changes)")
    else:
        print(f"Marked {len(to_fetch)} fetched URLs as seen. Remaining {len(changed) - len(to_fetch)} "
              f"will still show as changed next run until fetched.")


if __name__ == "__main__":
    sys.exit(main())
