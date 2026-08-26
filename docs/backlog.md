# Backlog

Deliberately parked items — not scope-creep, just not now. Each one has a reason to exist and a reason it's not built yet.

## Store original extracted text alongside the paraphrase

`extraction/schema.py`'s `ExtractedNotice` / `notices` table currently store only `summary_plain_language` (an LLM-generated paraphrase) and `source_url` (a link to the original PDF/page) — not the actual text the LLM read to produce that paraphrase.

**Why it matters:** the paraphrase is *generated*, not extracted verbatim — confirmed 2026-08-24 when asked directly whether "If you passed the DSO/Assistant Director main exam..." was on the source PDF (it isn't; it's Claude's plain-language rewrite of the actual bureaucratic wording). Right now, the only ways to catch a wrong paraphrase are the confidence score, the human-review gate, or a user clicking through to the source themselves — nothing lets a reviewer see the paraphrase next to what it was paraphrased from.

**What it'd take:** add a `raw_extracted_text` (or similar) field to `LLMExtractedFields`/`ExtractedNotice` and the `notices` table, populated from the same read the model already does — no second LLM call needed, just also returning the source text (or a faithful excerpt of it) in the same structured-output call.

**Status:** parked 2026-08-24, per Vikash — revisit before this becomes a trust/accuracy problem in practice, not after.

## Wire up the archival service

`archival/wayback_client.py` is built and unit-tested (5/5 cases passing against a mocked client) but not called from anywhere in the pipeline — `notices.archive_url` stays null, and the frontend always shows "Not yet independently archived."

**Why it matters:** the "verified" link is core to the design doc's "evidence, not claims" principle and is explicitly Phase 0 scope in the PRD.

**What it'd take:** call `archive_url()` when a notice is persisted (from ingestion or wherever the DB-write step ends up living), store the result in `notices.archive_url`. Needs real `IA_ACCESS_KEY`/`IA_SECRET_KEY` credentials (free, from archive.org) to actually test end-to-end.

**Status:** parked 2026-08-23, per Vikash — "may be too much for MVP right now."

## WhatsApp notification channel

`notifications/whatsapp_sender.py` (tech doc section 7, section 12 repo layout) — sending actual WhatsApp messages on subscribe-confirmation and on a reviewed notice. The `subscriptions` table and `/subscribe` endpoint exist and capture phone numbers; no message has ever actually been sent.

**Why it's parked instead of built:** WhatsApp Business API requires a Meta Business account, phone number registration, and — the real lead-time item — every message template needs Meta's pre-approval before it can send. That approval process is external and can't be done by either Claude or a generic dev environment; it needs Vikash's business to go through Meta's onboarding.

**What it'd take:** once Meta approval is in hand (business account + approved templates + a phone number ID), build `notifications/whatsapp_sender.py` against the WhatsApp Business Cloud API, reusing the same "reviewed notice → subscriber lookup by exam_id → send" trigger logic already built for Telegram in `notifications/notifier.py` — just add a WhatsApp delivery branch alongside the Telegram one.

**Status:** parked 2026-08-24, per Vikash — building Telegram first since it has no approval lead time; WhatsApp to follow once Meta Business API access is set up.
