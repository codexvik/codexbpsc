"""
Last-seen state for change detection (tech architecture doc, section 4, step 2).

This is a lightweight local SQLite store for Phase 0 / early development, so
the ingestion service is runnable and testable against live BPSC data before
the full multi-source Postgres schema (db/schema.sql, section 6) exists. The
`seen_urls` table here maps directly onto the eventual `notices`/`sources`
tracking columns and is meant to be migrated into Postgres, not replaced by
a different design, once step 4 (API layer) stands up the real database.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "ingestion_state.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_urls (
    source_id       TEXT NOT NULL,
    url             TEXT NOT NULL,
    lastmod         TEXT NOT NULL,
    first_seen_at   TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    PRIMARY KEY (source_id, url)
);
CREATE TABLE IF NOT EXISTS job_runs (
    job_name        TEXT PRIMARY KEY,
    last_run_at     TEXT,
    last_result     TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn):
    conn.executescript(SCHEMA)
    # `title` added 2026-08-25 for the admin panel's "recently detected"
    # list (api/admin.py) -- CREATE TABLE IF NOT EXISTS above won't add a
    # column to an already-existing table, so migrate it in by hand.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(seen_urls)").fetchall()}
    if "title" not in cols:
        conn.execute("ALTER TABLE seen_urls ADD COLUMN title TEXT")


@contextmanager
def connect(db_path: Path = DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_seen_lastmod(conn, source_id: str, url: str):
    row = conn.execute(
        "SELECT lastmod FROM seen_urls WHERE source_id = ? AND url = ?",
        (source_id, url),
    ).fetchone()
    return row[0] if row else None


def get_all_seen(conn, source_id: str) -> dict:
    rows = conn.execute(
        "SELECT url, lastmod FROM seen_urls WHERE source_id = ?",
        (source_id,),
    ).fetchall()
    return {url: lastmod for url, lastmod in rows}


def mark_seen(conn, source_id: str, url: str, lastmod: str, title: str = None):
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO seen_urls (source_id, url, lastmod, title, first_seen_at, last_checked_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, url) DO UPDATE SET
            lastmod = excluded.lastmod,
            title = COALESCE(excluded.title, seen_urls.title),
            last_checked_at = excluded.last_checked_at
        """,
        (source_id, url, lastmod, title, now, now),
    )


def get_recent(conn, source_id: str, limit: int = 40) -> list:
    """Most-recently-detected pages for a source, newest first -- feeds the
    admin panel's "recently detected, not yet extracted" list (api/admin.py),
    so an operator doesn't have to read .scheduler.log to find a URL."""
    rows = conn.execute(
        """
        SELECT url, title, lastmod, first_seen_at
        FROM seen_urls WHERE source_id = ?
        ORDER BY first_seen_at DESC LIMIT ?
        """,
        (source_id, limit),
    ).fetchall()
    return [{"url": u, "title": t, "lastmod": lm, "first_seen_at": fs} for u, t, lm, fs in rows]


def record_job_run(conn, job_name: str, result: str):
    """job_name is scoped per-source (e.g. "notice_poll:bpsc_bihar") so the
    admin panel's Dashboard/Settings pages (2026-08-25) can show a real
    "last ran at / what happened" per crawler job, not just a log file."""
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO job_runs (job_name, last_run_at, last_result) VALUES (?, ?, ?)
        ON CONFLICT(job_name) DO UPDATE SET last_run_at = excluded.last_run_at, last_result = excluded.last_result
        """,
        (job_name, now, result),
    )


def get_job_runs(conn) -> dict:
    rows = conn.execute("SELECT job_name, last_run_at, last_result FROM job_runs").fetchall()
    return {name: {"last_run_at": at, "last_result": result} for name, at, result in rows}
