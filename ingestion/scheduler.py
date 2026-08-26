"""
Runs the detection-only jobs on a timer (2026-08-25 decision: no automatic
extraction -- that stays a manual/human-triggered step, so there's no
unattended LLM spend). Two jobs, independently scheduled per source_config:

- notice_poll: fetches config's notice_feed_url (ingestion.notice_feed) and
  diffs it against ingestion_state.db to find newly-appeared PDF notices,
  every `poll_interval_minutes`. Replaced the original sitemap-based
  approach on 2026-08-25 -- see notice_feed.py's module docstring: BPSC's
  notification sitemap points at JS-rendered pages that come back empty on
  a plain fetch (verified 5/5 sampled), so nothing extractable was ever
  reachable that way. The notice feed page is server-rendered with direct
  PDF links, so no backlog-draining/rate-limiting complexity is needed --
  it's a small, un-paginated "what's currently new" list, not a deep
  archive to crawl.
- calendar_sync: the exam master-list sync (ingestion.exam_registry_sync),
  every `exam_calendar_sync_interval_minutes`.

Both intervals are re-read from Postgres (sources.config_json) on every
check cycle (2026-08-25, admin Settings page's frequency editor) rather
than fixed once at startup -- see _get_effective_minutes. That's what
makes a frequency change saved in the admin panel take effect within
~60s without restarting this process. Falls back to source_config.py's
static default if the DB has no override yet (first run) or the DB is
briefly unreachable.

Newly-detected notices are logged AND recorded (title + url) in
ingestion_state.db so the admin panel's "Run Extraction" page can list them
for one-click extraction -- an operator shouldn't have to read this log
file by hand to find a URL. Nothing is auto-extracted; extraction.run_extract
--url / the admin panel are still how one becomes a real notice.

Run: python -m ingestion.scheduler
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from db.connection import get_connection
from ingestion.exam_registry_sync import sync_exam_calendar
from ingestion.notice_feed import fetch_notice_feed
from ingestion.source_config import get_source_config
from ingestion.state_store import connect, get_all_seen, mark_seen, record_job_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60


def run_notice_poll(source_id: str) -> str:
    """Returns a short human-readable result string -- recorded by
    run_forever via record_job_run so the admin panel's Dashboard/Settings
    pages can show a real "last ran, found N" per job."""
    logger.info("[notice_poll] Checking %s's notice feed for new notices...", source_id)
    try:
        links = fetch_notice_feed(source_id)
    except Exception as exc:
        logger.warning("[notice_poll] Failed to fetch notice feed: %s", exc)
        return f"failed: {exc}"

    with connect() as conn:
        already_seen = get_all_seen(conn, source_id)
        new_links = [link for link in links if link.url not in already_seen]

        if not new_links:
            logger.info("[notice_poll] Nothing new (%d notice(s) currently on the feed, all already seen).", len(links))
            return f"0 new ({len(links)} on feed)"

        logger.info("[notice_poll] %d new notice(s) detected out of %d on the feed.", len(new_links), len(links))
        detected_at = datetime.now(timezone.utc).isoformat()
        for link in new_links:
            logger.info("[notice_poll] New: %s -- %r (not extracted -- use the admin panel's Run Extraction page)", link.url, link.title)
            # This feed has no per-item lastmod to diff against -- presence
            # in seen_urls at all is the "already processed" signal, so the
            # detection timestamp itself is a fine stand-in value here.
            mark_seen(conn, source_id, link.url, lastmod=detected_at, title=link.title)

        return f"{len(new_links)} new ({len(links)} on feed)"


def run_calendar_sync(source_id: str) -> str:
    logger.info("[calendar_sync] Syncing exam calendar for %s...", source_id)
    counts = sync_exam_calendar(source_id)
    logger.info("[calendar_sync] Done: %s", counts)
    return f"{counts['inserted']} inserted, {counts['updated']} updated, {counts['unchanged']} unchanged"


def _get_effective_minutes(source_id: str, config_key: str, default_minutes: int) -> int:
    """Live override support for the admin Settings page's frequency editor
    -- checks sources.config_json in Postgres first, falls back to the
    static source_config.py default. Queried every check cycle (cheap: one
    indexed row lookup every CHECK_EVERY_SECONDS) rather than cached, so a
    saved change is picked up without restarting the scheduler."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT config_json ->> %s AS v FROM sources WHERE source_id = %s", (config_key, source_id)
            ).fetchone()
            if row and row["v"] is not None:
                return int(row["v"])
    except Exception:
        logger.exception("Failed to read live interval override for %s/%s, using default", source_id, config_key)
    return default_minutes


def run_forever(source_id: str = "bpsc_bihar"):
    config = get_source_config(source_id)

    jobs = {
        "notice_poll": {
            "config_key": "poll_interval_minutes",
            "default_minutes": config["poll_interval_minutes"],
            "last_run": None,
            "run": lambda: run_notice_poll(source_id),
        },
        "calendar_sync": {
            "config_key": "exam_calendar_sync_interval_minutes",
            "default_minutes": config["exam_calendar_sync_interval_minutes"],
            "last_run": None,
            "run": lambda: run_calendar_sync(source_id),
        },
    }

    logger.info(
        "Scheduler starting for %s -- notice_poll every %s min (default), calendar_sync every %s min (default), "
        "live-overridable from the admin Settings page. Detection only, no auto-extraction.",
        source_id, jobs["notice_poll"]["default_minutes"], jobs["calendar_sync"]["default_minutes"],
    )

    while True:
        now = datetime.now()
        for name, job in jobs.items():
            interval_minutes = _get_effective_minutes(source_id, job["config_key"], job["default_minutes"])
            interval = timedelta(minutes=interval_minutes)
            if job["last_run"] is None or now - job["last_run"] >= interval:
                try:
                    result = job["run"]()
                except Exception as exc:
                    logger.exception("[%s] job failed, will retry next cycle", name)
                    result = f"failed: {exc}"
                with connect() as conn:
                    record_job_run(conn, f"{name}:{source_id}", result or "ok")
                job["last_run"] = now
        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    run_forever()
