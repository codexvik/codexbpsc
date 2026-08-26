# Technical Architecture (B2G Version): Bihar Exam Trust & Verification Infrastructure

> Intended audience: this document is written to be handed to Claude Code (or an equivalent coding agent) as the primary build spec. It assumes no prior context beyond what's written here. The key difference from a pure-consumer build: every component below is designed to support more than one government source from day one, even though only BPSC is populated at Phase 0.

---

## 1. System Overview

```
        ┌───────────────────────────┐        ┌───────────────────────────┐
        │  BPSC (Bihar) - Source #1  │  ...   │  Future state PSC - #N     │
        │  bpsc.bihar.gov.in          │        │  (config-defined)          │
        └─────────────┬───────────────┘        └─────────────┬───────────────┘
                      │  polls per source config                 │
                      ▼                                          ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                     Ingestion Service                          │
        │   - source_config registry (per-government-body settings)     │
        │   - sitemap/page diff checker, generic per config              │
        └───────────────────────────┬─────────────────────────────────┘
                                    │  raw HTML / PDF text
                                    ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                    Extraction Service                          │
        │   - LLM-based structuring, schema shared across sources        │
        └───────────────────────────┬─────────────────────────────────┘
                                    │  structured record
                                    ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                       Core Database                            │
        │  (sources, exams, notices, diffs, subscriptions, results)      │
        └───────┬─────────────┬─────────────────┬─────────────────────┘
                │             │                 │
                ▼             ▼                 ▼
   ┌───────────────┐ ┌────────────────┐ ┌─────────────────────────┐
   │ Notification    │ │ Public Web       │ │ Government Dashboard      │
   │ Service (WA)    │ │ Frontend (B2C)   │ │ (B2G, timeliness +        │
   │                 │ │                  │ │  scorecard data)          │
   └───────────────┘ └────────────────┘ └─────────────────────────┘
                │
                ▼
   ┌───────────────┐
   │ Archival Service │
   │ (Wayback API)     │
   └───────────────┘
```

## 2. The Core Architectural Difference From the B2C-Only Version

Everything BPSC-specific must live in **configuration**, not code. This is the single most important decision in this document — it's cheap to do now (Phase 0, one source) and expensive to retrofit later (once a second state's PSC needs onboarding). Concretely:

```json
// source_config example — one row per government body tracked
{
  "source_id": "bpsc_bihar",
  "display_name": "Bihar Public Service Commission",
  "state": "Bihar",
  "sitemap_urls": [
    "https://bpsc.bihar.gov.in/bsc_notification-sitemap1.xml",
    "... through sitemap7.xml"
  ],
  "robots_txt_verified": true,
  "poll_interval_minutes": 20,
  "notification_url_pattern": "https://bpsc.bihar.gov.in/notifications/{id}/",
  "results_listing_url": "https://bpsc.bihar.gov.in/notification-category/results/",
  "extraction_schema_version": "v1",       // most bodies can share one schema; override only if a source's structure genuinely differs
  "category_certificate_map": { ... }       // Bihar-specific reservation category → certificate mapping, used by the eligibility checker
}
```

Adding a second state's PSC (e.g., a Rajasthan or MP equivalent body) means: research its site structure, confirm robots.txt permissiveness, add a new `source_config` entry, verify the shared extraction schema still fits (adjust only if needed) — not a rebuild of the ingestion or extraction services.

## 3. Confirmed Data Sources — BPSC (Source #1, Verified Live Aug 2026)

- **Sitemap index**: `https://bpsc.bihar.gov.in/sitemap_index.xml`
- **Notification sitemaps** (7 paginated files as of writing): `https://bpsc.bihar.gov.in/bsc_notification-sitemap{1-7}.xml` — each entry has a `<lastmod>` timestamp, minute-precision; this is the primary change-detection signal, requiring only a small periodic fetch rather than full-page diffing
- **robots.txt**: confirmed permissive — `Disallow:` is empty
- **No public REST API**: `/wp-json/wp/v2/posts` returns empty; content lives under a custom post type (`bsc_notification`) not exposed via standard WordPress REST — build against the sitemap + page-scrape approach, not `wp-json`
- **Results**: currently PDF-based

When a second source is added, this section's equivalent research (sitemap availability, robots.txt, REST API status, PDF vs. structured results) must be repeated and logged in that source's config comments — do not assume another state's PSC uses the same CMS or publishing pattern as BPSC's WordPress setup.

## 4. Ingestion Service (Generic, Config-Driven)

**Logic, per configured source, on its own poll schedule:**
1. Fetch the source's configured sitemap file(s) (or, for a source without a sitemap, fall back to a configured listing-page diff — build this fallback path even though BPSC doesn't need it, since not every future source will have Yoast-style sitemaps)
2. Parse `<loc>`/`<lastmod>` pairs; compare against last-seen values stored per source in the database
3. Queue new/changed URLs for fetching
4. Fetch full page content (and any linked PDFs) for queued URLs only
5. Respect a per-source rate limit (e.g., no more than 1 request per 2-3 seconds) regardless of what robots.txt technically permits
6. Pass raw content, tagged with `source_id`, to the Extraction Service

## 5. Extraction Service

Same LLM-based structuring approach as the citizen-only version — schema, human-review gate, and PDF handling are unchanged in principle, but every extracted record must carry `source_id` so multi-source data never gets conflated:

```json
{
  "source_id": "bpsc_bihar",
  "exam_name": string,
  "advt_no": string | null,
  "category": "notice" | "program" | "interview" | "result" | "advertisement" | "corrigendum",
  "change_type": "new_notification" | "postponement" | "date_change" | "vacancy_revision" | "result_declared" | "other",
  "summary_plain_language": string,
  "old_value": string | null,
  "new_value": string | null,
  "effective_date": string | null,
  "source_url": string,
  "confidence": "high" | "medium" | "low"
}
```

Human review gate for low-confidence or high-stakes `change_type` values remains mandatory, unchanged from the citizen-only spec.

## 6. Core Data Model (Updated for Multi-Source)

```sql
CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  source_id TEXT UNIQUE NOT NULL,       -- e.g. "bpsc_bihar"
  display_name TEXT NOT NULL,
  state TEXT,
  config_json JSONB NOT NULL,           -- the full source_config object, section 2
  active BOOLEAN DEFAULT true
);

CREATE TABLE exams (
  id SERIAL PRIMARY KEY,
  source_id INT REFERENCES sources(id),  -- was implicitly BPSC-only before; now explicit
  name TEXT NOT NULL,
  advt_no TEXT,
  category TEXT,
  vacancy_count INT,
  status TEXT,
  eligibility_json JSONB,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE notices (
  id SERIAL PRIMARY KEY,
  exam_id INT REFERENCES exams(id),
  source_url TEXT NOT NULL,
  change_type TEXT NOT NULL,
  summary_plain_language TEXT,
  old_value TEXT,
  new_value TEXT,
  effective_date DATE,
  confidence TEXT,
  reviewed BOOLEAN DEFAULT false,
  archive_url TEXT,
  official_published_at TIMESTAMP,        -- new: for the timeliness dashboard, if determinable from the source
  detected_at TIMESTAMP DEFAULT now()
);

CREATE TABLE subscriptions (
  id SERIAL PRIMARY KEY,
  phone_number TEXT NOT NULL,
  exam_id INT REFERENCES exams(id),
  subscribed_at TIMESTAMP DEFAULT now(),
  active BOOLEAN DEFAULT true
);

CREATE TABLE results (
  id SERIAL PRIMARY KEY,
  exam_id INT REFERENCES exams(id),
  roll_number TEXT NOT NULL,
  status TEXT,
  rank INT,
  source_notice_id INT REFERENCES notices(id)
);
```

## 7. Notification Service — Unchanged in Mechanics

WhatsApp Business API, same lead-time caveat on template approval, same trigger logic (reviewed notice → subscriber lookup by `exam_id` → send). No B2G-specific change here; this remains purely citizen-facing.

## 8. Archival Service — Unchanged

Every notice detection triggers an Internet Archive "Save Page Now" call; the returned snapshot URL is stored in `notices.archive_url`. This is the trust mechanism underpinning both the citizen notice feed and the government-facing timeliness dashboard's credibility.

## 9. New: Government Dashboard (B2G Layer)

A separate, access-controlled surface (not part of the public web frontend) built from the same `notices` table:

- **Timeliness view**: for each notice, `official_published_at` (where determinable) vs. `detected_at` vs. when the push notification actually went out — exposes the platform's own speed, and indirectly, patterns in how far in advance or how last-minute BPSC itself publishes changes
- **Volume/pattern view**: notice frequency by `change_type` over time — e.g., how many postponements this cycle vs. last, without editorializing
- **Scorecard export**: the same data structured for the public-facing Integrity Scorecard (Phase 1), so the internal and public-facing tools are one data pipeline, not two

**Access model**: Phase 1, internal-only (your own team uses this to build the pitch). Only shared with BPSC/DIT directly once a relationship exists — do not expose this dashboard publicly or to BPSC unprompted before that relationship is established, since an unsolicited "here's how we're grading you" dashboard risks reading as adversarial rather than collaborative.

## 10. Public Web Frontend (B2C Layer) — Unchanged From Original

Exam list, exam detail, eligibility checker, notice feed, subscribe flow, result search — see the original tech architecture doc for full detail; no structural change here beyond ensuring every displayed record correctly scopes to `source_id = bpsc_bihar` (trivial at Phase 0, necessary once a second source exists so Bihar users never see Rajasthan notices by accident, or vice versa).

## 11. Non-Functional Requirements — One Addition

All original requirements (politeness, accuracy-over-speed, data minimization, auditability) carry over unchanged. New: **source isolation** — a bug that leaks one source's data into another source's citizen-facing view is both a product failure and a trust failure at the exact moment multi-state credibility matters most; test this explicitly once a second source is added, not just at launch.

## 12. Suggested Repo Structure

```
/ingestion
  source_config.py         # section 2 — config registry, not hardcoded BPSC logic
  poller.py                 # generic, reads from source_config
  page_fetcher.py
/extraction
  extractor.py               # schema shared across sources (section 5)
  pdf_handler.py
/api
  main.py                    # public API: exams, notices, subscribe, eligibility, result-search — all source_id-scoped
  gov_dashboard_api.py       # access-controlled, section 9
/notifications
  whatsapp_sender.py
/archival
  wayback_client.py
/db
  schema.sql                 # section 6
  migrations/
/frontend
  public/                    # B2C — exam list, detail, search (see design doc)
  gov-dashboard/             # B2G — internal, then shared post-relationship
```
