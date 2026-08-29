-- Core data model (tech architecture doc, section 6). One shared schema
-- across every government source (BPSC today, other state PSCs later) --
-- exams/notices/subscriptions/results all scope through sources.id, never
-- a hardcoded BPSC assumption, so onboarding a second source needs a new
-- `sources` row, not a schema change.

CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  source_id TEXT UNIQUE NOT NULL,       -- e.g. "bpsc_bihar", matches ingestion/source_config.py
  display_name TEXT NOT NULL,
  state TEXT,
  config_json JSONB NOT NULL,           -- mirrors source_config.py's SOURCE_CONFIGS entry
  active BOOLEAN DEFAULT true
);

CREATE TABLE exams (
  id SERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id),
  name TEXT NOT NULL,
  advt_no TEXT,
  category TEXT,
  vacancy_count INT,
  status TEXT,
  eligibility_json JSONB,               -- degree/age/category criteria -- design doc section 3.3
  -- Not in the tech doc's original section 6 -- added because the design
  -- doc's exam detail page (section 3.2) requires a key-dates timeline
  -- (application window, admit card, exam date, result) and the original
  -- schema had no field to hold it. Kept as flexible JSONB, matching the
  -- existing eligibility_json pattern, rather than one column per date.
  key_dates_json JSONB,
  -- Not in the tech doc's original section 6 -- added 2026-08-25 for the
  -- exam-calendar master-list sync (ingestion/exam_calendar.py). Raw
  -- section/phase-date/remarks context from BPSC's own Exam Calendar page,
  -- kept as text rather than typed dates since the source itself uses
  -- "TBD", "-----", and relative phrasing inconsistently across rows.
  calendar_snapshot_json JSONB,
  -- Not in the tech doc's original section 6 -- added 2026-08-25 for the
  -- admin Exams page's "enable on B2C" toggle. Defaults false: the
  -- calendar sync creates a bare stub (name/advt_no/vacancy_count, no real
  -- content) for every exam BPSC lists, most of which have no notice yet
  -- and aren't worth showing a citizen. An operator opts an exam in once
  -- it has something real to show, instead of every calendar row
  -- appearing on the public site automatically.
  visible_on_b2c BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_exams_source_id ON exams(source_id);

CREATE TABLE notices (
  id SERIAL PRIMARY KEY,
  exam_id INT NOT NULL REFERENCES exams(id),
  source_url TEXT NOT NULL,
  change_type TEXT NOT NULL,
  summary_plain_language TEXT,
  old_value TEXT,
  new_value TEXT,
  effective_date DATE,
  confidence TEXT,
  reviewed BOOLEAN DEFAULT false,
  -- Not in the tech doc's original section 6 -- added for the review admin
  -- (2026-08-25, "this is our IP layer"). A notice is one of three states:
  -- pending (reviewed=false, rejected=false), approved (reviewed=true), or
  -- rejected (rejected=true) -- a human explicitly decided the extraction
  -- was wrong, distinct from just not-yet-looked-at. Citizen-facing queries
  -- only ever check `reviewed`, so this is additive, not a behavior change.
  rejected BOOLEAN DEFAULT false,
  reviewed_at TIMESTAMP,
  -- Not in the tech doc's original section 6 -- added 2026-08-25 for the
  -- admin panel's "Send to Subscribers" trigger. NULL means never sent;
  -- set once notifications.notifier.notify_subscribers has run for this
  -- notice, so the admin UI can tell "approved" apart from "approved and
  -- delivered" and never offer to send the same notice twice by accident.
  notified_at TIMESTAMP,
  archive_url TEXT,                     -- Wayback Machine snapshot -- populated by the archival service (not yet built)
  official_published_at TIMESTAMP,      -- for the future timeliness dashboard, where determinable
  detected_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_notices_exam_id ON notices(exam_id);
CREATE INDEX idx_notices_detected_at ON notices(detected_at DESC);

CREATE TABLE subscriptions (
  id SERIAL PRIMARY KEY,
  phone_number TEXT,                    -- nullable: a Telegram-only subscriber has no phone number
  telegram_chat_id TEXT,                -- nullable: not every subscriber has linked Telegram
  exam_id INT NOT NULL REFERENCES exams(id),
  subscribed_at TIMESTAMP DEFAULT now(),
  active BOOLEAN DEFAULT true,
  UNIQUE (phone_number, exam_id),       -- re-subscribing just reactivates a row, doesn't duplicate
  CONSTRAINT chk_subscriptions_has_contact CHECK (phone_number IS NOT NULL OR telegram_chat_id IS NOT NULL)
);
CREATE INDEX idx_subscriptions_exam_id ON subscriptions(exam_id);
-- Partial (not the table-level UNIQUE above, which only covers phone_number
-- pairs) so two different Telegram subscribers can't double-subscribe the
-- same exam, while NULL phone_number rows don't collide with each other.
CREATE UNIQUE INDEX idx_subscriptions_telegram_exam ON subscriptions (telegram_chat_id, exam_id) WHERE telegram_chat_id IS NOT NULL;

CREATE TABLE results (
  id SERIAL PRIMARY KEY,
  exam_id INT NOT NULL REFERENCES exams(id),
  roll_number TEXT NOT NULL,
  status TEXT,
  rank INT,
  source_notice_id INT REFERENCES notices(id)
);
CREATE INDEX idx_results_exam_roll ON results(exam_id, roll_number);

-- Not in the tech doc's original section 6 -- added for the "Request a
-- Callback" bar on the redesigned frontend. Deliberately minimal (no
-- routing/assignment/status workflow) since there's no call-center backend
-- yet; just captures the request so it isn't silently discarded.
CREATE TABLE callback_requests (
  id SERIAL PRIMARY KEY,
  phone_number TEXT NOT NULL,
  exam_id INT REFERENCES exams(id),
  requested_at TIMESTAMP DEFAULT now()
);

-- Integrity Scoreboard, Phase 0: Historical Baseline (2026-08-27, companion
-- to the Wedge Roadmap's "integrity-scoreboard-roadmap.html"). A structured
-- log of PAST incidents sourced from public record only (EOU raids, court
-- petitions, news) -- never from candidate reports, which is Phase 2's
-- separate, differently-verified intake. This table sets sensitivity for
-- the future RAG color engine (Phase 1) -- history makes an exam/centre
-- need LESS new evidence to escalate, but per the roadmap's own rule, no
-- exam is ever colored Red on history alone, so this table never computes
-- a color by itself. source_url is NOT NULL deliberately: an incident with
-- no citation doesn't belong in this table -- this product's whole
-- thesis is corroboration, not assertion, so fabricating or guessing an
-- entry here would undermine the one thing it's for.
CREATE TABLE integrity_incidents (
  id SERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id),
  exam_name TEXT NOT NULL,              -- free text, not exams.id -- historical incidents (e.g. TRE-3) often predate anything in the exams table
  cycle TEXT,                           -- e.g. "TRE-3", "72nd CCE" -- however the source itself refers to the cycle
  centre TEXT,                          -- exam centre name/code where known; NULL means exam-body-level only
  incident_type TEXT NOT NULL,          -- e.g. paper_leak, re_test_ordered, malpractice, admin_irregularity
  detection_source TEXT NOT NULL,       -- e.g. "EOU raid", "court petition", "news report"
  resolution TEXT,                      -- what actually happened / outcome, where known
  source_url TEXT NOT NULL,             -- citation -- required, see note above
  incident_date DATE,                   -- drives the sensitivity model's time-decay; nullable only when genuinely undated in the source
  created_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_integrity_incidents_source_id ON integrity_incidents(source_id);

-- Integrity search history (2026-08-27, "if you run the same keyword and
-- exams again is gonna cost me money uselessly"). One row per web search
-- actually run, independent of whether anything from it got logged --
-- candidates_found is set when the search runs, candidates_logged is
-- updated afterward once the operator picks which (if any) to keep. Used
-- both for a browsable history page and to warn before re-running an
-- identical search.
CREATE TABLE integrity_searches (
  id SERIAL PRIMARY KEY,
  exam_id INT REFERENCES exams(id),
  exam_name TEXT NOT NULL,
  keyword TEXT,
  candidates_found INT NOT NULL DEFAULT 0,
  candidates_logged INT NOT NULL DEFAULT 0,
  searched_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_integrity_searches_exam_id ON integrity_searches(exam_id);

-- LLM provider settings (2026-08-27, "allow me to use any model and
-- storing the api key ... to save on the cost"). Singleton row (id is
-- always 1) -- one active provider/model at a time, applied to both
-- extraction and integrity search (llm/provider.py reads this instead of
-- either module instantiating a provider SDK client directly). Cloud
-- providers only for now, by explicit decision -- a local model (e.g. via
-- Ollama) was raised and deliberately deferred, not forgotten.
-- Keys are stored in plaintext, same as everything else in this local-only
-- admin -- this table is not more sensitive than sources.config_json,
-- which already holds operational config; if this app is ever deployed
-- somewhere multi-tenant, this table needs real secret storage first.
CREATE TABLE llm_settings (
  id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  active_provider TEXT NOT NULL DEFAULT 'anthropic',   -- 'anthropic' or 'openai'
  anthropic_model TEXT NOT NULL DEFAULT 'claude-opus-5',
  anthropic_api_key TEXT,                              -- NULL falls back to ANTHROPIC_API_KEY env var, same as before this feature existed
  openai_model TEXT NOT NULL DEFAULT 'gpt-5-mini',
  openai_api_key TEXT,                                 -- NULL falls back to OPENAI_API_KEY env var
  updated_at TIMESTAMP DEFAULT now()
);
