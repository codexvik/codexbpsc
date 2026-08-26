"""
Per-government-body configuration registry.

Tech architecture doc, section 2: everything source-specific (BPSC or any
government body added later) must live here, not hardcoded into poller.py /
page_fetcher.py / extractor.py. Onboarding a second state's PSC means adding
a new entry to SOURCE_CONFIGS (after repeating the section-3-style live
verification for that source) — not touching the ingestion/extraction logic.
"""

SOURCE_CONFIGS = {
    "bpsc_bihar": {
        "source_id": "bpsc_bihar",
        "display_name": "Bihar Public Service Commission",
        "state": "Bihar",

        # Verified live, Aug 2026 (tech architecture doc, section 3).
        "robots_txt_verified": True,
        "sitemap_index_url": "https://bpsc.bihar.gov.in/sitemap_index.xml",
        "sitemap_urls": [
            f"https://bpsc.bihar.gov.in/bsc_notification-sitemap{i}.xml"
            for i in range(1, 8)
        ],
        "has_sitemap": True,
        # Fallback for sources without sitemaps (section 4, step 1). BPSC has
        # sitemaps so this stays unused, but the field exists so the poller's
        # fallback path is exercised by config, not a source-specific branch.
        "listing_fallback_url": None,

        "notification_url_pattern": "https://bpsc.bihar.gov.in/notifications/{id}/",
        "results_listing_url": "https://bpsc.bihar.gov.in/notification-category/results/",
        "official_website": "https://bpsc.bihar.gov.in/",
        # Real notice discovery (2026-08-25, replaces the sitemap poller for
        # notice_poll -- see ingestion/notice_feed.py's module docstring for
        # why: notification_url_pattern's own pages are JS-rendered and come
        # back empty on a plain fetch, verified against 5 live samples. This
        # page is server-rendered with direct PDF links + real titles.
        "notice_feed_url": "https://bpsc.bihar.gov.in/whats-new/",
        # The master list (2026-08-25 finding): a structured table of every
        # active exam (advt no, post, vacancy count, phase dates), distinct
        # from the notification stream. Notices report CHANGES to exams;
        # this page is what actually defines which exams exist -- e.g. TRE
        # 4.0 (32,388 vacancies) is listed here with no advertisement
        # issued yet, so it has never appeared in a notice.
        "exam_calendar_url": "https://bpsc.bihar.gov.in/exam-calendar/",

        # Frontend discovery/browse metadata (2026-08-24 redesign) -- which
        # board-category bucket this source's exams fall under for the
        # category filter, plus display strings for the exam card/detail
        # header. Real, verifiable facts about BPSC itself, not per-exam
        # guesses -- every exam from this source shares the same board.
        "board_category": "State PSC",
        "display_name_hindi": "बिहार लोक सेवा आयोग",
        "monogram": "BPSC",

        "extraction_schema_version": "v1",

        "poll_interval_minutes": 20,
        # Exam calendar changes far less often than notices -- daily is
        # plenty, and polite (2026-08-25 scheduler).
        "exam_calendar_sync_interval_minutes": 24 * 60,
        # Section 4, step 5: respect a per-source rate limit regardless of
        # what robots.txt technically permits.
        "rate_limit_seconds": 2.5,

        "request_timeout_seconds": 20,
        "user_agent": "CodexBPSC-Ingestion/0.1 (+contact: research/pilot bot; polite crawl)",

        # Bihar-specific reservation category -> certificate mapping for the
        # eligibility checker (design doc, section 3.3). Not needed by
        # ingestion; left as a stub until the extraction/API phase populates
        # it from a verified source rather than guessed values.
        "category_certificate_map": {},
    },
}


def get_source_config(source_id: str) -> dict:
    try:
        return SOURCE_CONFIGS[source_id]
    except KeyError:
        raise ValueError(f"No source_config registered for source_id={source_id!r}")


def active_source_ids() -> list:
    return list(SOURCE_CONFIGS.keys())
