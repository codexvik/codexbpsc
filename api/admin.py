"""
Ops console (2026-08-25, "this is our IP layer", later "think of it
holistically... build a complete admin suite") -- the operator surface for
running the whole pipeline: what the crawler found, the human-review gate
extraction.extractor.needs_human_review requires before a flagged notice
can go live, triggering extraction and notification sends, and visibility
into crawler health. Five sections:

- Dashboard (/dashboard): KPIs + charts (Chart.js via CDN -- real app page,
  not a sandboxed Artifact, so an external script tag is fine) + crawler
  job status (last run time/result per job, from ingestion_state.db's
  job_runs table).
- Exams (/exams, /exams/{id}): the master list of every exam being tracked
  (2026-08-25, "is there a way to find which exam/job this notification is
  related to") and a detail page per exam -- status, vacancy count, any
  calendar/notice discrepancy, and every notice ever tied to it. The
  Notices table's exam name links here, so a notice can always be traced
  back to its exam's full history, not just the one row.
- Notices (/notices): ONE filterable table (status/source/confidence) that
  replaced the earlier separate Pending Review + Review History card pages
  (2026-08-25, "it should be more like a table... so I can use the right
  filter"). Inline Approve/Reject/Send actions per row; filters round-trip
  through hidden form fields so acting on a row doesn't lose your filter.
  Old /review and /history URLs redirect here for anything with them
  bookmarked.
- Run Extraction (/extract, /extract/run): trigger the LLM call that turns
  a detected URL into a real notice. Kept manual on purpose -- no
  unattended LLM spend (2026-08-25 scheduling decision).
- Settings (/settings): what's being crawled, and now (2026-08-25, "may be
  you can allow the edit of crawler frequency") how often -- editable,
  minutes/hours/days. Adding a whole new source is still a
  source_config.py change + restart (that stays out of scope, per the
  earlier "view-only for now" decision); only the two frequency numbers for
  an already-registered source are editable. The edit is real, not
  cosmetic: it writes into sources.config_json in Postgres, and
  ingestion.scheduler re-reads that on every check cycle (see
  scheduler.py's _get_effective_minutes), so a saved change takes effect
  within about a minute without restarting the scheduler process.

Server-rendered HTML, no build step/framework. Two places use inline JS on
purpose, nothing else: submit-button busy states (2026-08-25, "when i press
extract it does not do anything") so a 10-30s extraction call doesn't look
frozen, and Chart.js for the dashboard's graphs.

No auth yet -- this must not be exposed on a public-facing deployment until
some access control is added. Fine for local-only use today.

Mounted into api/main.py under the /admin prefix.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment
from markupsafe import Markup

from db.connection import get_connection
from extraction.extractor import extract_notice, extract_notice_from_pdf, needs_human_review
from extraction.pdf_handler import fetch_pdf_bytes
from extraction.persist import persist_notice
from ingestion.page_fetcher import fetch_page
from ingestion.rate_limiter import RateLimiter
from ingestion.source_config import SOURCE_CONFIGS, active_source_ids, get_source_config
from ingestion.scheduler import run_calendar_sync, run_notice_poll
from ingestion.state_store import connect as ingestion_connect, get_job_runs, record_job_run, get_recent as get_recent_seen
from integrity.search import search_incidents_for_exam
from llm.config import get_settings as get_llm_settings, save_settings as save_llm_settings
from notifications.notifier import notify_subscribers

router = APIRouter(prefix="/admin", tags=["admin"])

_env = Environment(autoescape=True)

_PAGE_SHELL = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} — Codex BPSC Ops</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {
    --bg: #f5f3ee;
    --surface: #ffffff;
    --surface-alt: #faf8f2;
    --border: #e3ddd0;
    --border-strong: #d3cabb;
    --ink: #1d2621;
    --muted: #6c756c;
    --accent: #2b5f5c;
    --accent-dark: #1e4442;
    --success: #1c7a3f;
    --success-bg: #e3f5e9;
    --success-border: #b8e3c6;
    --warning: #96660b;
    --warning-bg: #fdf1dc;
    --danger: #a13a3a;
    --danger-bg: #fbeaea;
    --radius: 10px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh; display: flex;
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg); color: var(--ink); font-size: 14px; line-height: 1.5;
  }
  .mono { font-family: 'IBM Plex Mono', ui-monospace, Menlo, Consolas, monospace; }
  .sidebar {
    width: 216px; flex-shrink: 0; background: var(--surface);
    border-right: 1px solid var(--border); padding: 26px 14px;
    display: flex; flex-direction: column; gap: 26px; position: sticky; top: 0; height: 100vh;
  }
  .brand { padding: 0 10px; }
  .brand .eyebrow { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
  .brand strong { display: block; font-size: 16px; font-weight: 700; color: var(--ink); margin-top: 3px; }
  .nav-list { display: flex; flex-direction: column; gap: 3px; }
  .nav-item {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 10px 12px; border-radius: 8px; color: var(--muted); text-decoration: none;
    font-size: 13.5px; font-weight: 600; border-left: 3px solid transparent;
  }
  .nav-item:hover { background: var(--surface-alt); color: var(--ink); }
  .nav-item.active { background: var(--surface-alt); color: var(--accent-dark); border-left-color: var(--accent); }
  .nav-badge { background: var(--warning-bg); color: var(--warning); font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 999px; }
  .nav-item.active .nav-badge { background: var(--accent); color: #fff; }
  main { flex: 1; padding: 40px 44px; max-width: 1040px; }
  h1 { font-size: 22px; font-weight: 700; margin: 0 0 6px; letter-spacing: -.01em; }
  .page-sub { font-size: 13.5px; color: var(--muted); margin: 0 0 24px; max-width: 680px; line-height: 1.55; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; margin-bottom: 14px; }
  .meta { font-size: 11.5px; color: var(--muted); margin-bottom: 10px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .meta strong { color: var(--ink); font-size: 13.5px; font-weight: 600; }
  .pill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; }
  .pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
  .pill-risky { background: var(--warning-bg); color: var(--warning); }
  .pill-conf-low { background: var(--danger-bg); color: var(--danger); }
  .pill-conf-medium { background: var(--warning-bg); color: var(--warning); }
  .pill-conf-high { background: var(--success-bg); color: var(--success); }
  .pill-source { background: var(--surface-alt); color: var(--ink); border: 1px solid var(--border-strong); }
  .pill-source::before { display: none; }
  .pill-row { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
  .summary { font-size: 15px; font-weight: 600; margin: 4px 0 8px; line-height: 1.4; }
  .diff { font-size: 12.5px; margin: 8px 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; background: var(--surface-alt); border-radius: 7px; padding: 8px 10px; }
  .diff .old { color: var(--danger); text-decoration: line-through; }
  .diff .new { color: var(--success); font-weight: 600; }
  a.source-link { font-size: 11.5px; color: var(--accent-dark); word-break: break-all; text-decoration: none; }
  a.source-link:hover { text-decoration: underline; }
  .actions { margin-top: 14px; display: flex; gap: 8px; }
  button {
    padding: 9px 16px; border-radius: 7px; border: none; font-weight: 700; font-size: 13px;
    cursor: pointer; font-family: inherit; transition: filter .1s ease;
  }
  button:hover { filter: brightness(.94); }
  button.small { padding: 6px 11px; font-size: 12px; }
  .approve { background: var(--success); color: #fff; }
  .reject { background: var(--danger); color: #fff; }
  .send { background: var(--accent); color: #fff; }
  .empty { color: var(--muted); padding: 44px 20px; text-align: center; border: 1px dashed var(--border-strong); border-radius: var(--radius); font-size: 13.5px; }
  .status-pill { display: inline-flex; align-items: center; gap: 5px; font-weight: 700; font-size: 11.5px; }
  .status-pill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
  .status-approved { color: var(--success); }
  .status-rejected { color: var(--danger); }
  .status-pending { color: var(--warning); }
  .sent-note { font-size: 12px; color: var(--muted); }
  .extract-form { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px; display: flex; flex-direction: column; gap: 14px; }
  .field-label { font-size: 11.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; display: block; margin-bottom: 6px; }
  .extract-form select, .extract-form textarea {
    font-family: inherit; font-size: 13.5px; padding: 10px 12px; border: 1px solid var(--border-strong);
    border-radius: 7px; background: var(--surface-alt); color: var(--ink); width: 100%; display: block;
  }
  .extract-form textarea { font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: 12.5px; resize: vertical; }
  .extract-form select:focus, .extract-form textarea:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
  .error-text { color: var(--danger); }
  .banner { background: var(--success-bg); color: var(--success); border: 1px solid var(--success-border); border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; font-size: 13.5px; font-weight: 600; }
  .hint-inline { font-size: 13px; color: var(--muted); margin-top: 18px; }
  .hint-inline a { color: var(--accent-dark); font-weight: 600; text-decoration: none; }
  .hint-inline a:hover { text-decoration: underline; }
  .info-icon {
    display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px;
    border-radius: 50%; background: var(--surface-alt); border: 1px solid var(--border-strong);
    color: var(--muted); font-size: 9.5px; font-weight: 700; font-style: normal; cursor: help;
    vertical-align: middle; margin-left: 2px;
  }
  .source-group { margin-bottom: 22px; }
  .source-group-title { font-size: 13.5px; font-weight: 700; margin-bottom: 10px; }
  ol.steps { margin: 10px 0 0; padding-left: 20px; font-size: 13px; color: var(--ink); }
  ol.steps li { margin-bottom: 6px; line-height: 1.5; }
  .stepper-wrap { display: flex; align-items: stretch; flex-wrap: wrap; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 4px; margin-bottom: 26px; gap: 2px; }
  .step { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; padding: 12px 20px; text-decoration: none; color: var(--ink); border-radius: 7px; border-left: 3px solid transparent; flex: 1; min-width: 88px; }
  .step:hover { background: var(--surface-alt); }
  .step .n { font-size: 1.3rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; }
  .step .l { font-size: .68rem; color: var(--muted); font-weight: 700; text-align: center; line-height: 1.25; text-transform: uppercase; letter-spacing: .03em; margin-top: 2px; }
  .step.active { background: var(--surface-alt); border-left-color: var(--accent); }
  .step.active .n { color: var(--accent-dark); }
  .step-sep { display: flex; align-items: center; color: var(--border-strong); font-size: 1.05rem; padding: 0 1px; flex-shrink: 0; }
  h2.section-heading { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); margin: 30px 0 12px; }
  .candidate-list { display: flex; flex-direction: column; gap: 2px; margin-bottom: 6px; }
  .candidate-row { display: flex; align-items: flex-start; gap: 10px; padding: 9px 8px; border-radius: 7px; cursor: pointer; }
  .candidate-row:hover { background: var(--surface-alt); }
  .candidate-row input { margin-top: 3px; flex-shrink: 0; accent-color: var(--accent); }
  .candidate-main { flex: 1; display: flex; flex-direction: column; gap: 5px; min-width: 0; }
  .candidate-title { font-size: 13.5px; font-weight: 600; }
  .candidate-hints { display: flex; gap: 6px; flex-wrap: wrap; }
  .candidate-meta { font-size: 11px; color: var(--muted); flex-shrink: 0; white-space: nowrap; margin-top: 3px; }
  .pill-guess { background: var(--surface-alt); color: var(--accent-dark); border: 1px solid var(--border-strong); }
  .pill-guess::before { display: none; }

  .frequency-form { display: flex; flex-direction: column; gap: 12px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
  .freq-field { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .freq-field label { font-size: 12.5px; font-weight: 600; color: var(--ink); min-width: 190px; }
  .freq-field input[type=number] { width: 70px; font-family: inherit; font-size: 13px; padding: 7px 8px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface-alt); color: var(--ink); }
  .freq-field select { font-family: inherit; font-size: 13px; padding: 7px 8px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface-alt); color: var(--ink); }
  .freq-saved { font-size: 12px; color: var(--success); font-weight: 600; }
  .result-status { font-size: 13px; font-weight: 600; margin-top: 10px; padding: 8px 12px; border-radius: 7px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .result-status a { color: inherit; text-decoration: underline; font-weight: 700; }
  .result-status-ok { background: var(--success-bg); color: var(--success); }
  .result-status-warn { background: var(--warning-bg); color: var(--warning); }
  .result-status-neutral { background: var(--surface-alt); color: var(--muted); }
  button[disabled], button.is-busy { cursor: wait !important; opacity: .75; position: relative; padding-left: 34px; }
  button.small.is-busy { padding-left: 28px; }
  button.is-busy::before {
    content: ""; position: absolute; left: 12px; top: 50%; width: 13px; height: 13px;
    margin-top: -6.5px; border-radius: 50%; border: 2px solid rgba(255,255,255,.5);
    border-top-color: #fff; animation: spin .7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .busy-banner {
    display: none; align-items: center; gap: 10px; background: var(--surface-alt);
    border: 1px solid var(--border-strong); border-radius: 8px; padding: 12px 16px;
    margin-bottom: 18px; font-size: 13.5px; font-weight: 600; color: var(--ink);
  }
  .busy-banner.is-visible { display: flex; }
  .busy-banner .spinner {
    width: 15px; height: 15px; flex-shrink: 0; border-radius: 50%;
    border: 2px solid var(--border-strong); border-top-color: var(--accent);
    animation: spin .7s linear infinite;
  }
  @media (prefers-reduced-motion: reduce) { button.is-busy::before, .busy-banner .spinner { animation: none; } }

  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 30px; }
  .kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px 18px; }
  .kpi-value { font-size: 27px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; margin-bottom: 7px; color: var(--ink); }
  .kpi-label { font-size: 11.5px; color: var(--muted); font-weight: 600; }
  .kpi-card.accent-warning .kpi-value { color: var(--warning); }
  .kpi-card.accent-success .kpi-value { color: var(--success); }
  .kpi-card.accent-brand .kpi-value { color: var(--accent-dark); }

  .job-status-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 30px; }
  .job-status-card { flex: 1; min-width: 240px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 14px 18px; display: flex; align-items: flex-start; gap: 11px; }
  .job-status-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
  .job-status-dot.ok { background: var(--success); }
  .job-status-dot.err { background: var(--danger); }
  .job-status-dot.stale { background: var(--muted); }
  .job-status-name { font-weight: 700; font-size: 13px; }
  .job-status-detail { font-size: 12px; color: var(--muted); margin-top: 3px; }

  .chart-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }
  .chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; margin-bottom: 16px; }
  .chart-card h3 { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); margin: 0 0 16px; }
  .chart-canvas-wrap { position: relative; height: 210px; }
  .chart-canvas-wrap.short { height: 170px; }
  @media (max-width: 760px) { .chart-grid { grid-template-columns: 1fr; } }

  .filter-bar { display: flex; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; align-items: flex-end; }
  .filter-field { display: flex; flex-direction: column; gap: 4px; }
  .filter-field label { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); }
  .filter-field select { font-family: inherit; font-size: 13px; padding: 7px 10px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--ink); min-width: 140px; }

  .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); background: var(--surface); }
  table.notices-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .notices-table th { text-align: left; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; color: var(--muted); padding: 11px 14px; border-bottom: 1px solid var(--border); background: var(--surface-alt); white-space: nowrap; }
  .notices-table td { padding: 12px 14px; border-bottom: 1px solid var(--border); vertical-align: top; }
  .notices-table tr:last-child td { border-bottom: none; }
  .notices-table tr:hover td { background: var(--surface-alt); }
  .cell-title { font-weight: 600; font-size: 13.5px; margin-bottom: 3px; max-width: 320px; }
  .cell-title-link { font-weight: 600; font-size: 13.5px; color: var(--ink); text-decoration: none; display: inline-block; max-width: 320px; }
  .cell-title-link:hover { color: var(--accent-dark); text-decoration: underline; }
  .cell-summary { font-size: 12.5px; color: var(--ink); margin: 3px 0; max-width: 340px; line-height: 1.4; }
  .cell-diff { font-size: 11.5px; margin: 4px 0; display: flex; gap: 6px; flex-wrap: wrap; max-width: 340px; }
  .cell-diff .old { color: var(--danger); text-decoration: line-through; }
  .cell-diff .new { color: var(--success); font-weight: 600; }
  .col-actions { white-space: nowrap; }
  .inline-form { display: inline-block; margin-right: 6px; }

  table.settings-table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
  table.settings-table td { padding: 8px 4px; border-bottom: 1px solid var(--border); }
  table.settings-table td:first-child { color: var(--muted); font-weight: 600; width: 240px; }
  table.settings-table tr:last-child td { border-bottom: none; }
</style>
</head>
<body>
<aside class="sidebar">
  <div class="brand">
    <div class="eyebrow">Codex BPSC</div>
    <strong>Ops Console</strong>
  </div>
  <nav class="nav-list">
    <a class="nav-item {{ 'active' if current == 'dashboard' else '' }}" href="/admin/dashboard">Dashboard</a>
    <a class="nav-item {{ 'active' if current == 'notices' else '' }}" href="/admin/extract">
      Notices
      {% if pending_count %}<span class="nav-badge">{{ pending_count }}</span>{% endif %}
    </a>
    <a class="nav-item {{ 'active' if current == 'exams' else '' }}" href="/admin/exams">Exams</a>
    <a class="nav-item {{ 'active' if current == 'integrity' else '' }}" href="/admin/integrity">Integrity Scoreboard</a>
    <a class="nav-item {{ 'active' if current == 'settings' else '' }}" href="/admin/settings">Settings</a>
  </nav>
</aside>
<main>
<div id="busy-banner" class="busy-banner"><span class="spinner"></span><span id="busy-banner-text"></span></div>
{{ body }}
</main>
<script>
  document.addEventListener('submit', function (e) {
    var form = e.target;
    var btn = form.querySelector('button[type="submit"]');
    if (!btn) return;
    if (btn.disabled) { e.preventDefault(); return; }
    btn.disabled = true;
    btn.classList.add('is-busy');
    if (btn.dataset.busyText) { btn.textContent = btn.dataset.busyText; }
    if (form.dataset.bannerText) {
      var banner = document.getElementById('busy-banner');
      document.getElementById('busy-banner-text').textContent = form.dataset.bannerText;
      banner.classList.add('is-visible');
    }
  });
</script>
</body>
</html>
"""

_DASHBOARD = """
<h1>Dashboard</h1>
<p class="page-sub">Live snapshot of the pipeline — what the crawler has found, what's waiting on you, what's already gone out.</p>

<div class="kpi-grid">
  <div class="kpi-card accent-brand"><div class="kpi-value"><a href="/admin/exams" style="color:inherit;text-decoration:none;">{{ exam_count }}</a></div><div class="kpi-label">Exams Monitored</div></div>
  <div class="kpi-card accent-warning"><div class="kpi-value">{{ kpis.pending }}</div><div class="kpi-label">Pending Review</div></div>
  <div class="kpi-card accent-success"><div class="kpi-value">{{ kpis.approved }}</div><div class="kpi-label">Approved</div></div>
  <div class="kpi-card"><div class="kpi-value">{{ kpis.rejected }}</div><div class="kpi-label">Rejected</div></div>
  <div class="kpi-card accent-brand"><div class="kpi-value">{{ kpis.notified }}</div><div class="kpi-label">Sent to Subscribers</div></div>
  <div class="kpi-card"><div class="kpi-value">{{ kpis.today }}</div><div class="kpi-label">Detected Today</div></div>
  <div class="kpi-card accent-brand"><div class="kpi-value">{{ subscribers }}</div><div class="kpi-label">Active Subscribers</div></div>
</div>

<h2 class="section-heading">Crawler status</h2>
{% if crawl_banner %}<p class="banner">{{ crawl_banner }}</p>{% endif %}
<div class="job-status-row">
  {% for j in jobs %}
  <div class="job-status-card">
    <span class="job-status-dot {{ j.dot }}"></span>
    <div><div class="job-status-name">{{ j.label }}</div><div class="job-status-detail">{{ j.detail }}</div></div>
  </div>
  {% endfor %}
</div>
<div class="actions" style="margin-bottom:30px; flex-wrap: wrap; align-items: center; gap: 14px;">
  <form method="post" action="/admin/crawl/notices/run" data-banner-text="Checking for new notices — this is free, no LLM call involved." style="display:inline-block;">
    <button class="send small" type="submit" data-busy-text="Checking…">Check for New Notices <span class="info-icon" title="Checks every source's notice feed for anything new. Free — no LLM call. Feeds the Notices → Detected list.">i</span></button>
  </form>
  <form method="post" action="/admin/crawl/calendar/run" data-banner-text="Syncing exam master list — this is free, no LLM call involved." style="display:inline-block;">
    <button class="send small" type="submit" data-busy-text="Syncing…">Sync Exam Master List <span class="info-icon" title="Re-reads every source's exam calendar page for vacancy counts and new cycles. Free — no LLM call. Feeds the Exams list.">i</span></button>
  </form>
  <span class="sent-note">Both free — same checks the scheduler runs automatically. Extraction (which costs money) still needs a separate click.</span>
</div>

<div class="chart-grid">
  <div class="chart-card">
    <h3>Notices detected — last 14 days</h3>
    <div class="chart-canvas-wrap"><canvas id="chart-daily"></canvas></div>
  </div>
  <div class="chart-card">
    <h3>Confidence breakdown</h3>
    <div class="chart-canvas-wrap"><canvas id="chart-confidence"></canvas></div>
  </div>
</div>
<div class="chart-card">
  <h3>Change type breakdown</h3>
  <div class="chart-canvas-wrap short"><canvas id="chart-changetype"></canvas></div>
</div>

<script>
(function () {
  var dailyData = {{ daily_json }};
  var confData = {{ conf_json }};
  var typeData = {{ type_json }};
  var css = getComputedStyle(document.documentElement);
  var accent = css.getPropertyValue('--accent').trim();
  var success = css.getPropertyValue('--success').trim();
  var warning = css.getPropertyValue('--warning').trim();
  var danger = css.getPropertyValue('--danger').trim();
  var muted = css.getPropertyValue('--muted').trim();
  var ink = css.getPropertyValue('--ink').trim();
  var gridColor = 'rgba(0,0,0,.06)';

  new Chart(document.getElementById('chart-daily'), {
    type: 'bar',
    data: { labels: dailyData.labels, datasets: [{ label: 'Notices', data: dailyData.values, backgroundColor: accent, borderRadius: 4, maxBarThickness: 26 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0, color: muted }, grid: { color: gridColor } },
        x: { ticks: { color: muted, maxRotation: 0, autoSkip: true, maxTicksLimit: 7 }, grid: { display: false } }
      }
    }
  });

  new Chart(document.getElementById('chart-confidence'), {
    type: 'doughnut',
    data: { labels: confData.labels, datasets: [{ data: confData.values, backgroundColor: [success, warning, danger], borderWidth: 0 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '65%',
      plugins: { legend: { position: 'bottom', labels: { color: ink, boxWidth: 10, font: { size: 11 }, padding: 12 } } }
    }
  });

  new Chart(document.getElementById('chart-changetype'), {
    type: 'bar',
    data: { labels: typeData.labels, datasets: [{ data: typeData.values, backgroundColor: accent, borderRadius: 4, maxBarThickness: 20 }] },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, ticks: { precision: 0, color: muted }, grid: { color: gridColor } },
        y: { ticks: { color: ink, font: { size: 11.5 } }, grid: { display: false } }
      }
    }
  });
})();
</script>
"""

_SETTINGS = """
<h1>Settings</h1>
<p class="page-sub">What's being crawled and how often. Adding a whole new source is still a code change in ingestion/source_config.py + a restart — but crawl frequency for an existing source is editable below and takes effect within about a minute, no restart needed.</p>

{% if saved %}<p class="banner">Saved — the scheduler will pick up the new frequency on its next check (within ~60 seconds).</p>{% endif %}

{% for s in sources %}
<div class="card">
  <div class="meta"><strong>{{ s.display_name }}</strong><span class="pill pill-source">{{ s.source_id }}</span></div>
  <table class="settings-table">
    <tr><td>State</td><td>{{ s.state }}</td></tr>
    <tr><td>Board category</td><td>{{ s.board_category or "—" }}</td></tr>
    <tr><td>Official website</td><td><a class="source-link" href="{{ s.official_website }}" target="_blank" rel="noopener">{{ s.official_website }}</a></td></tr>
    <tr><td>Notice feed (crawled for changes)</td><td><a class="source-link" href="{{ s.notice_feed_url }}" target="_blank" rel="noopener">{{ s.notice_feed_url }}</a></td></tr>
    <tr><td>Exam calendar (master list)</td><td><a class="source-link" href="{{ s.exam_calendar_url }}" target="_blank" rel="noopener">{{ s.exam_calendar_url }}</a></td></tr>
    <tr><td>Rate limit between requests</td><td>{{ s.rate_limit_seconds }}s (not editable here)</td></tr>
  </table>

  <form class="frequency-form" method="post" action="/admin/settings/{{ s.source_id }}/frequency">
    <div class="freq-field">
      <label for="poll-{{ s.source_id }}">Notice crawl every</label>
      <input type="number" id="poll-{{ s.source_id }}" name="poll_value" min="1" value="{{ s.poll_value }}" required>
      <select name="poll_unit">
        <option value="minutes" {{ 'selected' if s.poll_unit == 'minutes' else '' }}>minutes</option>
        <option value="hours" {{ 'selected' if s.poll_unit == 'hours' else '' }}>hours</option>
        <option value="days" {{ 'selected' if s.poll_unit == 'days' else '' }}>days</option>
      </select>
    </div>
    <div class="freq-field">
      <label for="cal-{{ s.source_id }}">Exam calendar sync every</label>
      <input type="number" id="cal-{{ s.source_id }}" name="calendar_value" min="1" value="{{ s.cal_value }}" required>
      <select name="calendar_unit">
        <option value="minutes" {{ 'selected' if s.cal_unit == 'minutes' else '' }}>minutes</option>
        <option value="hours" {{ 'selected' if s.cal_unit == 'hours' else '' }}>hours</option>
        <option value="days" {{ 'selected' if s.cal_unit == 'days' else '' }}>days</option>
      </select>
    </div>
    <div class="actions">
      <button class="approve small" type="submit" data-busy-text="Saving…">Save Frequency</button>
    </div>
  </form>
</div>
{% endfor %}

<h2 class="section-heading">Crawler status</h2>
<p class="page-sub" style="margin-bottom:12px;">
  Two crawlers per source, grouped below by which source they belong to — this stays readable once a
  second board is added, instead of an unlabeled pile of cards. Both run automatically on the schedule
  set above; this just shows when each last ran and what it found.
</p>
{% for s in source_groups %}
<div class="source-group">
  <div class="source-group-title">{{ s.display_name }}</div>
  <div class="job-status-row" style="margin-bottom:0;">
    <div class="job-status-card">
      <span class="job-status-dot {{ s.notice_job.dot }}"></span>
      <div>
        <div class="job-status-name">Notice Crawler <span class="info-icon" title="Checks this source's notice feed for anything new since the last check. Free — no LLM call. Feeds the Notices → Detected list.">i</span></div>
        <div class="job-status-detail">{{ s.notice_job.detail }}</div>
      </div>
    </div>
    <div class="job-status-card">
      <span class="job-status-dot {{ s.calendar_job.dot }}"></span>
      <div>
        <div class="job-status-name">Exam Master List Crawler <span class="info-icon" title="Re-reads this source's exam calendar page for vacancy counts and new exam cycles. Free — no LLM call. Feeds the Exams list.">i</span></div>
        <div class="job-status-detail">{{ s.calendar_job.detail }}</div>
      </div>
    </div>
  </div>
</div>
{% endfor %}
<p class="hint-inline">The scheduler process (<code class="mono">python -m ingestion.scheduler</code>) has to actually be running for these to update — this page shows the last time it reported in, not whether it's running right now.</p>

<h2 class="section-heading">Adding a new source</h2>
<div class="card">
  <p class="page-sub" style="margin-bottom:10px;">
    Not self-service yet — adding a source is a code change, not a form, because each one needs real
    verification first (the right feed URL, confirming robots.txt allows it, catching quirks like
    JS-rendered pages that look fine but return no content). Once that's done for a source, here's what
    actually adding it involves:
  </p>
  <ol class="steps">
    <li>Add an entry to <code class="mono">ingestion/source_config.py</code>'s <code class="mono">SOURCE_CONFIGS</code> dict — notice feed URL, exam calendar URL, crawl frequency, rate limit.</li>
    <li>Add a matching row to the <code class="mono">sources</code> table (via <code class="mono">db/seed.py</code> or directly).</li>
    <li>Restart the API server and the scheduler process.</li>
  </ol>
  <p class="page-sub" style="margin:10px 0 0;">Tell me when a second source is ready to add and I'll do the verification pass and the change together, same as BPSC.</p>
</div>

<h2 class="section-heading">AI provider</h2>
<p class="page-sub" style="margin-bottom:12px;">
  Which model runs extraction and integrity search, and whose API key pays for it. Switch providers to
  trade cost against quality — a cheaper model costs less per run but may need more manual review.
  Local/self-hosted models aren't supported yet, cloud providers only for now.
</p>
{% if llm_saved %}<p class="banner">AI provider settings saved.</p>{% endif %}
<div class="card">
  <form class="frequency-form" method="post" action="/admin/settings/llm">
    <div class="freq-field">
      <label for="llm-provider" style="min-width:140px;">Active provider</label>
      <select id="llm-provider" name="active_provider">
        <option value="anthropic" {{ 'selected' if llm.active_provider == 'anthropic' else '' }}>Anthropic (Claude)</option>
        <option value="openai" {{ 'selected' if llm.active_provider == 'openai' else '' }}>OpenAI (GPT)</option>
      </select>
    </div>
  </form>

  <table class="settings-table" style="margin-top:18px;">
    <tr><td colspan="2" style="color:var(--ink);font-weight:700;padding-top:0;">Anthropic</td></tr>
  </table>
  <form class="frequency-form" method="post" action="/admin/settings/llm" style="margin-top:0;padding-top:10px;">
    <input type="hidden" name="active_provider" value="{{ llm.active_provider }}">
    <div class="freq-field">
      <label for="anthropic-model" style="min-width:140px;">Model</label>
      <input type="text" id="anthropic-model" name="anthropic_model" value="{{ llm.anthropic_model }}" style="width:220px;">
    </div>
    <div class="freq-field">
      <label for="anthropic-key" style="min-width:140px;">API key</label>
      <input type="password" id="anthropic-key" name="anthropic_api_key" placeholder="{{ 'saved — leave blank to keep' if llm.anthropic_api_key else 'not set — falls back to ANTHROPIC_API_KEY env var' }}" style="width:320px;" autocomplete="new-password">
    </div>
    <div class="actions">
      <button class="approve small" type="submit" data-busy-text="Saving…">Save Anthropic Settings</button>
    </div>
  </form>

  <table class="settings-table" style="margin-top:18px;">
    <tr><td colspan="2" style="color:var(--ink);font-weight:700;padding-top:0;">OpenAI</td></tr>
  </table>
  <form class="frequency-form" method="post" action="/admin/settings/llm" style="margin-top:0;padding-top:10px;">
    <input type="hidden" name="active_provider" value="{{ llm.active_provider }}">
    <div class="freq-field">
      <label for="openai-model" style="min-width:140px;">Model</label>
      <input type="text" id="openai-model" name="openai_model" value="{{ llm.openai_model }}" style="width:220px;">
    </div>
    <div class="freq-field">
      <label for="openai-key" style="min-width:140px;">API key</label>
      <input type="password" id="openai-key" name="openai_api_key" placeholder="{{ 'saved — leave blank to keep' if llm.openai_api_key else 'not set — falls back to OPENAI_API_KEY env var' }}" style="width:320px;" autocomplete="new-password">
    </div>
    <div class="actions">
      <button class="approve small" type="submit" data-busy-text="Saving…">Save OpenAI Settings</button>
    </div>
  </form>
</div>
<p class="hint-inline">Keys are stored in this server's own database, never shown back once saved, and never sent anywhere except the provider you picked.</p>
"""

_EXAMS_LIST = """
<h1>Exams</h1>
<p class="page-sub">
  The master list — every exam/job being tracked, {{ from_calendar_count }} of them from the free daily
  calendar sync alone, independent of any notice. A notice gets tied to one of these automatically
  when it's extracted: matched by advertisement number when the notice states one, or by name when
  it doesn't (see the "matched by" note on each exam's page). No match found means a new exam row
  gets created right then. Showing <strong><span id="exam-count">0</span></strong> of {{ exams|length }}.
</p>

<div class="filter-bar">
  <div class="filter-field">
    <label for="exam-status">Status</label>
    <select id="exam-status" onchange="filterExams()">
      <option value="active" selected>Active (Shown on B2C)</option>
      <option value="inactive">Inactive</option>
      <option value="all">All</option>
    </select>
  </div>
  <div class="filter-field">
    <label for="exam-source">Source</label>
    <select id="exam-source" onchange="filterExams()">
      <option value="">All Sources</option>
      {% for sid in source_ids %}<option value="{{ sid }}">{{ sid }}</option>{% endfor %}
    </select>
  </div>
  <div class="filter-field">
    <label for="exam-search">Search</label>
    <input type="text" id="exam-search" oninput="filterExams()" placeholder="Filter by name or advt no…">
  </div>
</div>

<div class="table-wrap">
<table class="notices-table" id="exams-table">
  <thead><tr><th>Exam</th><th>Source</th><th>Advt No</th><th>Vacancies</th><th>Status</th><th>Notices</th><th>B2C</th></tr></thead>
  <tbody>
  {% for e in exams %}
  <tr data-search="{{ (e.name ~ ' ' ~ (e.advt_no or '')) | lower }}" data-status="{{ 'active' if e.visible_on_b2c else 'inactive' }}" data-source="{{ e.source_id }}">
    <td><a class="cell-title-link" href="/admin/exams/{{ e.id }}">{{ e.name }}</a></td>
    <td><span class="pill pill-source">{{ e.source_id }}</span></td>
    <td class="mono">{{ e.advt_no or "—" }}</td>
    <td class="mono">{{ e.vacancy_count if e.vacancy_count is not none else "—" }}</td>
    <td>{{ e.status or "—" }}</td>
    <td class="mono">{{ e.notice_count }}</td>
    <td><span class="status-pill {{ 'status-approved' if e.visible_on_b2c else 'status-pending' }}">{{ 'Live' if e.visible_on_b2c else 'Hidden' }}</span></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% if not exams %}
<p class="empty">No exams tracked yet.</p>
{% endif %}
<script>
function filterExams() {
  var q = document.getElementById('exam-search').value.toLowerCase();
  var status = document.getElementById('exam-status').value;
  var source = document.getElementById('exam-source').value;
  var visible = 0;
  document.querySelectorAll('#exams-table tbody tr').forEach(function (row) {
    var matchesSearch = !q || row.dataset.search.indexOf(q) !== -1;
    var matchesStatus = status === 'all' || row.dataset.status === status;
    var matchesSource = !source || row.dataset.source === source;
    var show = matchesSearch && matchesStatus && matchesSource;
    row.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  var countEl = document.getElementById('exam-count');
  if (countEl) countEl.textContent = visible;
}
document.addEventListener('DOMContentLoaded', filterExams);
</script>
"""

_EXAM_DETAIL = """
<h1>{{ exam.name }}</h1>
<p class="page-sub">{{ exam.source_name }} &middot; {{ exam.category or "uncategorized" }}</p>

{% if banner %}<p class="banner">{{ banner }}</p>{% endif %}

<div class="card">
  <table class="settings-table">
    <tr><td>Advertisement No.</td><td>{{ exam.advt_no or "—" }}</td></tr>
    <tr><td>Vacancies</td><td>{{ exam.vacancy_count if exam.vacancy_count is not none else "—" }}</td></tr>
    <tr><td>Status</td><td>{{ exam.status or "—" }}</td></tr>
    <tr><td>Matched by</td><td>{{ "advertisement number" if exam.advt_no else "name (no advt no on any linked notice yet)" }}</td></tr>
    <tr><td>Tracked since</td><td>{{ exam.created_at_fmt }}</td></tr>
    <tr>
      <td>Shown on B2C site</td>
      <td>
        <span class="status-pill {{ 'status-approved' if exam.visible_on_b2c else 'status-pending' }}" style="margin-right:10px;">{{ 'Live' if exam.visible_on_b2c else 'Hidden' }}</span>
        <form method="post" action="/admin/exams/{{ exam.id }}/visibility" style="display:inline;">
          <input type="hidden" name="visible" value="{{ '0' if exam.visible_on_b2c else '1' }}">
          <button class="{{ 'reject' if exam.visible_on_b2c else 'approve' }} small" type="submit" data-busy-text="Saving…">
            {{ 'Hide from B2C' if exam.visible_on_b2c else 'Show on B2C' }}
          </button>
        </form>
      </td>
    </tr>
  </table>
  {% if exam.discrepancy %}
  <p class="result-status result-status-warn" style="margin-top:14px;">&#9888; {{ exam.discrepancy }}</p>
  {% endif %}
</div>

<h2 class="section-heading">Run extraction for this exam</h2>
<p class="page-sub" style="margin-bottom:12px;">Paste a notice URL (PDF or page) about this specific exam. Same extraction as the main Run Extraction page, just scoped here for convenience.</p>
<form class="extract-form" method="post" action="/admin/exams/{{ exam.id }}/extract" data-banner-text="Extracting — this can take up to 30 seconds per URL.">
  <div>
    <label class="field-label" for="exam-urls">Notice URL(s) — one per line</label>
    <textarea id="exam-urls" name="urls" rows="3" placeholder="https://bpsc.bihar.gov.in/wp-content/uploads/..."></textarea>
  </div>
  <div class="actions">
    <button class="approve" type="submit" data-busy-text="Extracting…">Extract &amp; Save <span class="info-icon" title="Sends this URL to the AI to pull out exam name, dates, and vacancy details, scoped to this exam. Costs one AI call. Result lands in Notices → Pending Review.">i</span></button>
  </div>
</form>

<h2 class="section-heading">Integrity incidents</h2>
<p class="page-sub" style="margin-bottom:12px;">
  {% if exam.visible_on_b2c %}<a href="/admin/integrity?exam_id={{ exam.id }}">Search for or log integrity incidents for this exam &rarr;</a>{% else %}Enable "Show on B2C" above first — only exams marked active show up there.{% endif %}
</p>

<h2 class="section-heading">Notices for this exam ({{ notices|length }})</h2>
{% if notices %}
<div class="table-wrap">
<table class="notices-table">
  <thead><tr><th>Detected</th><th>Change</th><th>Confidence</th><th>Status</th><th>Summary</th><th>Actions</th></tr></thead>
  <tbody>
  {% for n in notices %}
  <tr>
    <td class="mono">{{ n.detected_at_fmt }}</td>
    <td><span class="pill pill-risky">{{ n.change_type }}</span></td>
    <td><span class="pill pill-conf-{{ n.confidence }}">{{ n.confidence }}</span></td>
    <td>
      {% if n.rejected %}<span class="status-pill status-rejected">Rejected</span>
      {% elif n.reviewed %}<span class="status-pill status-approved">Approved</span>
      {% else %}<span class="status-pill status-pending">Pending</span>{% endif %}
    </td>
    <td><div class="cell-summary" style="margin:0;">{{ n.summary_plain_language }}</div><a class="source-link" href="{{ n.source_url }}" target="_blank" rel="noopener">source ↗</a></td>
    <td class="col-actions">
      {% if not n.reviewed and not n.rejected %}
      <form method="post" action="/admin/review/{{ n.id }}/approve" class="inline-form">
        <input type="hidden" name="redirect_to" value="/admin/exams/{{ exam.id }}">
        <button class="approve small" type="submit" data-busy-text="…">Approve</button>
      </form>
      <form method="post" action="/admin/review/{{ n.id }}/reject" class="inline-form">
        <input type="hidden" name="redirect_to" value="/admin/exams/{{ exam.id }}">
        <button class="reject small" type="submit" data-busy-text="…">Reject</button>
      </form>
      {% elif n.reviewed and not n.notified_at %}
      <form method="post" action="/admin/notify/{{ n.id }}" class="inline-form" data-banner-text="Sending to subscribers…">
        <input type="hidden" name="redirect_to" value="/admin/exams/{{ exam.id }}">
        <button class="send small" type="submit" data-busy-text="…">Send <span class="info-icon" title="Delivers this approved notice to every subscriber tracking this exam, by SMS/Telegram. One-time — can't be sent twice.">i</span></button>
      </form>
      {% elif n.notified_at %}
      <span class="sent-note">Sent {{ n.notified_at_fmt }}</span>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% else %}
<p class="empty">No notices for this exam yet — it's only in the calendar sync so far.</p>
{% endif %}

<p class="hint-inline"><a href="/admin/exams">&larr; Back to all exams</a></p>
"""

_INTEGRITY_SEARCH_RESULTS = """
<h1>Integrity Search — {{ exam_name }}</h1>
<p class="page-sub">
  {% if keyword %}Narrowed to "{{ keyword }}". {% endif %}Every candidate below came with a real source URL found
  live — nothing is invented, and nothing is saved yet. Check the ones that are real and relevant, then Log Selected.
</p>

{% if candidates %}
<form method="post" action="/admin/integrity/search/save">
  <input type="hidden" name="exam_id" value="{{ exam_id }}">
  <input type="hidden" name="search_id" value="{{ search_id }}">
  <div class="candidate-list">
    {% for c in candidates %}
    <label class="candidate-row">
      <input type="checkbox" name="candidates" value="{{ c.json }}">
      <span class="candidate-main">
        <span class="candidate-title">{{ c.headline }}</span>
        <span class="cell-summary" style="margin:2px 0;">{{ c.snippet }}</span>
        <span class="candidate-hints">
          <span class="pill pill-risky">{{ c.incident_type }}</span>
          {% if c.centre %}<span class="pill pill-guess">{{ c.centre }}</span>{% endif %}
          {% if c.incident_date %}<span class="pill pill-guess">{{ c.incident_date }}</span>{% endif %}
        </span>
        <a class="source-link" href="{{ c.source_url }}" target="_blank" rel="noopener">{{ c.source_url }}</a>
      </span>
    </label>
    {% endfor %}
  </div>
  <div class="actions">
    <button class="approve" type="submit" data-busy-text="Saving…">Log Selected</button>
  </div>
</form>
{% else %}
<p class="empty">No sourced candidates found for this exam{% if keyword %} matching "{{ keyword }}"{% endif %}.</p>
{% endif %}

<p class="hint-inline"><a href="/admin/integrity">&larr; Back to Integrity</a></p>
"""

_INTEGRITY_DUPLICATE_WARNING = """
<h1>Already searched — {{ exam_name }}</h1>
<p class="result-status result-status-warn">
  &#9888; You searched this exam{% if keyword %} for "{{ keyword }}"{% endif %} on {{ prior_searched_at_fmt }} —
  {{ prior.candidates_found }} candidate(s) found, {{ prior.candidates_logged }} logged. Searching again spends
  money finding the same thing, unless you think something new has happened since then.
</p>
<form method="post" action="/admin/integrity/search" style="margin-top:16px;">
  <input type="hidden" name="exam_id" value="{{ exam_id }}">
  <input type="hidden" name="keyword" value="{{ keyword }}">
  <input type="hidden" name="force" value="1">
  <div class="actions">
    <button class="send" type="submit" data-busy-text="Searching…">Search Anyway <span class="info-icon" title="Runs a fresh paid web search for this exam/keyword even though an identical search already ran. Use this only if you think something new has happened since the last search.">i</span></button>
  </div>
</form>
<p class="hint-inline"><a href="/admin/integrity/history">View full search history</a> &middot; <a href="/admin/integrity">&larr; Back to Integrity</a></p>
"""

_INTEGRITY_HISTORY_PAGE = """
<h1>Integrity Search History</h1>
<p class="page-sub">Every web search run so far, whether or not anything from it got logged — check here before spending on the same search twice.</p>

{% if searches %}
<div class="table-wrap">
<table class="notices-table">
  <thead><tr><th>Exam</th><th>Keyword</th><th>When</th><th>Found</th><th>Logged</th></tr></thead>
  <tbody>
  {% for s in searches %}
  <tr>
    <td><div class="cell-title">{{ s.exam_name }}</div></td>
    <td>{{ s.keyword or "—" }}</td>
    <td class="mono">{{ s.searched_at_fmt }}</td>
    <td class="mono">{{ s.candidates_found }}</td>
    <td class="mono">{{ s.candidates_logged }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% else %}
<p class="empty">No searches run yet.</p>
{% endif %}

<p class="hint-inline"><a href="/admin/integrity">&larr; Back to Integrity</a></p>
"""

_INTEGRITY_PAGE = """
<h1>Integrity — Historical Baseline</h1>
<p class="page-sub">
  Building a real, sourced record of exam-integrity incidents (leaks, malpractice, re-tests) for your
  tracked exams — the foundation a future Red/Amber/Green rating gets built on later. Nothing here is
  invented: every entry needs a real link to a news article, court record, or official statement.
</p>

{% if banner %}<p class="banner">{{ banner }}</p>{% endif %}

<h2 class="section-heading">Search for incidents</h2>
<p class="page-sub" style="margin-bottom:12px;">
  Pick one of your active exams (the ones you've marked "Show on B2C"), optionally narrow with a cycle
  name or keyword, then search — a paid web search, results shown for you to pick from, nothing saved
  automatically. Already searched this before? Submitting will warn you first instead of spending again
  silently — see <a href="/admin/integrity/history">Search History</a> to check beforehand.
</p>
<form method="post" action="/admin/integrity/search" data-banner-text="Searching the web — this can take up to a minute.">
  <div class="frequency-form" style="padding:0;border:none;margin-top:0;">
    <div class="freq-field">
      <label for="s-exam" style="min-width:140px;">Exam</label>
      <select id="s-exam" name="exam_id" required style="flex:1;font-family:inherit;font-size:13.5px;padding:9px 10px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);">
        <option value="" disabled {{ 'selected' if not selected_exam_id else '' }}>Select an exam…</option>
        {% for e in active_exams %}<option value="{{ e.id }}" {{ 'selected' if e.id == selected_exam_id else '' }}>{{ e.name }}</option>{% endfor %}
      </select>
    </div>
    <div class="freq-field">
      <label for="s-keyword" style="min-width:140px;">Cycle / keyword (optional)</label>
      <input type="text" id="s-keyword" name="keyword" placeholder="e.g. TRE-3, leak, Bapu centre" style="flex:1;font-family:inherit;font-size:13.5px;padding:9px 10px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);">
    </div>
    <div class="actions">
      <button class="send small" type="submit" data-busy-text="Searching…">Search the Web <span class="info-icon" title="Paid web search for real, sourced integrity incidents about this exam. Costs money each time it runs — checks your search history first and warns before repeating an identical search.">i</span></button>
    </div>
  </div>
</form>
{% if not active_exams %}
<p class="hint-inline">No exams are marked "Show on B2C" yet — that's the list this dropdown pulls from. Open an exam's page (under Exams) and enable it there, or use "log manually" below instead.</p>
{% endif %}

<h2 class="section-heading">Or log one manually</h2>
<p class="page-sub" style="margin-bottom:12px;">Already know the details? Skip the search — still needs a real source link.</p>
<form class="extract-form" method="post" action="/admin/integrity/add">
  <div>
    <label class="field-label" for="i-exam">Exam / cycle name</label>
    <input type="text" id="i-exam" name="exam_name" list="exam-options" placeholder="Pick an active exam, or type one that predates tracking (e.g. TRE-3)" required style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
    <datalist id="exam-options">
      {% for name in exam_names %}<option value="{{ name }}">{% endfor %}
    </datalist>
  </div>
  <div>
    <label class="field-label" for="i-cycle">Cycle label (optional, if different from above)</label>
    <input type="text" id="i-cycle" name="cycle" placeholder="e.g. TRE-3" style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
  </div>
  <div>
    <label class="field-label" for="i-centre">Centre (leave blank if exam-body-level only)</label>
    <input type="text" id="i-centre" name="centre" placeholder="e.g. Bapu centre, Hazaribagh" style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
  </div>
  <div>
    <label class="field-label" for="i-type">Incident type</label>
    <select id="i-type" name="incident_type">
      <option value="paper_leak">Paper leak</option>
      <option value="re_test_ordered">Re-test ordered</option>
      <option value="malpractice">Malpractice</option>
      <option value="admin_irregularity">Administrative irregularity</option>
      <option value="other">Other</option>
    </select>
  </div>
  <div>
    <label class="field-label" for="i-source">Detection source</label>
    <input type="text" id="i-source" name="detection_source" placeholder="e.g. EOU raid, court petition, news report" required style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
  </div>
  <div>
    <label class="field-label" for="i-date">Incident date (if known)</label>
    <input type="date" id="i-date" name="incident_date" style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
  </div>
  <div>
    <label class="field-label" for="i-resolution">Resolution / outcome (if known)</label>
    <textarea id="i-resolution" name="resolution" rows="2" placeholder="What actually happened"></textarea>
  </div>
  <div>
    <label class="field-label" for="i-url">Source URL — required, this is the citation</label>
    <input type="url" id="i-url" name="source_url" placeholder="https://..." required style="font-family:inherit;font-size:13.5px;padding:10px 12px;border:1px solid var(--border-strong);border-radius:7px;background:var(--surface-alt);color:var(--ink);width:100%;">
  </div>
  <div class="actions">
    <button class="approve" type="submit" data-busy-text="Saving…">Log Incident</button>
  </div>
</form>

<h2 class="section-heading">Logged incidents ({{ incidents|length }})</h2>
{% if incidents %}
<div class="table-wrap">
<table class="notices-table">
  <thead><tr><th>Exam / Cycle</th><th>Centre</th><th>Type</th><th>Date</th><th>Detected via</th><th>Source</th></tr></thead>
  <tbody>
  {% for inc in incidents %}
  <tr>
    <td><div class="cell-title">{{ inc.exam_name }}</div>{% if inc.cycle %}<div class="cell-summary" style="margin:0;">{{ inc.cycle }}</div>{% endif %}</td>
    <td>{{ inc.centre or "— (exam-body level)" }}</td>
    <td><span class="pill pill-risky">{{ inc.incident_type }}</span></td>
    <td class="mono">{{ inc.incident_date_fmt or "—" }}</td>
    <td>{{ inc.detection_source }}</td>
    <td><a class="source-link" href="{{ inc.source_url }}" target="_blank" rel="noopener">source ↗</a></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% else %}
<p class="empty">Nothing logged yet. This is where Phase 0 starts — add the first real, sourced incident above.</p>
{% endif %}
"""

_STEPPER = """
<div class="stepper-wrap">
  <a class="step {{ 'active' if active == 'detected' else '' }}" href="/admin/extract" title="Notices seen by the crawler that haven't been extracted yet. Extraction costs money and only runs when you trigger it here.">
    <span class="n">{{ counts.detected }}</span><span class="l">Detected</span>
  </a>
  <span class="step-sep">&rarr;</span>
  <a class="step {{ 'active' if active == 'pending' else '' }}" href="/admin/notices?status=pending" title="Extracted, but flagged for a human look before it can go live or be sent.">
    <span class="n">{{ counts.pending }}</span><span class="l">Pending Review</span>
  </a>
  <span class="step-sep">&rarr;</span>
  <a class="step {{ 'active' if active == 'approved' else '' }}" href="/admin/notices?status=approved&notified=0" title="Live on the site, waiting for you to send it to subscribers.">
    <span class="n">{{ counts.approved }}</span><span class="l">Approved</span>
  </a>
  <span class="step-sep">&rarr;</span>
  <a class="step {{ 'active' if active == 'sent' else '' }}" href="/admin/notices?status=approved&notified=1" title="Delivered to Telegram subscribers.">
    <span class="n">{{ counts.sent }}</span><span class="l">Sent</span>
  </a>
</div>
"""

_NOTICES_PAGE = """
<h1>Notices</h1>
<p class="page-sub">Everything the crawler has turned into a notice. Filter to find what needs action.</p>

{% if banner %}<p class="banner">{{ banner }}</p>{% endif %}

<form class="filter-bar" method="get" action="/admin/notices">
  <div class="filter-field">
    <label for="f-status">Status</label>
    <select id="f-status" name="status" onchange="this.form.submit()">
      <option value="pending" {{ 'selected' if filters.status == 'pending' else '' }}>Pending</option>
      <option value="approved" {{ 'selected' if filters.status == 'approved' else '' }}>Approved</option>
      <option value="rejected" {{ 'selected' if filters.status == 'rejected' else '' }}>Rejected</option>
      <option value="" {{ 'selected' if filters.status == '' else '' }}>All</option>
    </select>
  </div>
  <div class="filter-field">
    <label for="f-source">Source</label>
    <select id="f-source" name="source_id" onchange="this.form.submit()">
      <option value="" {{ 'selected' if filters.source_id == '' else '' }}>All Sources</option>
      {% for sid in source_ids %}<option value="{{ sid }}" {{ 'selected' if filters.source_id == sid else '' }}>{{ sid }}</option>{% endfor %}
    </select>
  </div>
  <div class="filter-field">
    <label for="f-conf">Confidence</label>
    <select id="f-conf" name="confidence" onchange="this.form.submit()">
      <option value="" {{ 'selected' if filters.confidence == '' else '' }}>All</option>
      <option value="high" {{ 'selected' if filters.confidence == 'high' else '' }}>High</option>
      <option value="medium" {{ 'selected' if filters.confidence == 'medium' else '' }}>Medium</option>
      <option value="low" {{ 'selected' if filters.confidence == 'low' else '' }}>Low</option>
    </select>
  </div>
  <div class="filter-field">
    <label for="f-notified">Sent</label>
    <select id="f-notified" name="notified" onchange="this.form.submit()">
      <option value="" {{ 'selected' if filters.notified == '' else '' }}>All</option>
      <option value="0" {{ 'selected' if filters.notified == '0' else '' }}>Not yet sent</option>
      <option value="1" {{ 'selected' if filters.notified == '1' else '' }}>Sent</option>
    </select>
  </div>
</form>

{% if rows %}
<div class="table-wrap">
<table class="notices-table">
  <thead><tr><th>Exam</th><th>Source</th><th>Detected</th><th>Change</th><th>Confidence</th><th>Status</th><th>Actions</th></tr></thead>
  <tbody>
  {% for n in rows %}
  <tr>
    <td>
      <a class="cell-title-link" href="/admin/exams/{{ n.exam_id }}">{{ n.exam_name }}</a>
      <div class="cell-summary">{{ n.summary_plain_language }}</div>
      {% if n.old_value or n.new_value %}
      <div class="cell-diff"><span class="old">{{ n.old_value or "—" }}</span> &rarr; <span class="new">{{ n.new_value or "—" }}</span></div>
      {% endif %}
      <a class="source-link" href="{{ n.source_url }}" target="_blank" rel="noopener">source ↗</a>
    </td>
    <td><span class="pill pill-source">{{ n.source_id }}</span></td>
    <td class="mono">{{ n.detected_at_fmt }}</td>
    <td><span class="pill pill-risky">{{ n.change_type }}</span></td>
    <td><span class="pill pill-conf-{{ n.confidence }}">{{ n.confidence }}</span></td>
    <td>
      {% if n.rejected %}<span class="status-pill status-rejected">Rejected</span>
      {% elif n.reviewed %}<span class="status-pill status-approved">Approved</span>
      {% else %}<span class="status-pill status-pending">Pending</span>{% endif %}
    </td>
    <td class="col-actions">
      {% if not n.reviewed and not n.rejected %}
      <form method="post" action="/admin/review/{{ n.id }}/approve" class="inline-form">
        <input type="hidden" name="status" value="{{ filters.status }}"><input type="hidden" name="source_id" value="{{ filters.source_id }}"><input type="hidden" name="confidence" value="{{ filters.confidence }}"><input type="hidden" name="notified" value="{{ filters.notified }}">
        <button class="approve small" type="submit" data-busy-text="…">Approve</button>
      </form>
      <form method="post" action="/admin/review/{{ n.id }}/reject" class="inline-form">
        <input type="hidden" name="status" value="{{ filters.status }}"><input type="hidden" name="source_id" value="{{ filters.source_id }}"><input type="hidden" name="confidence" value="{{ filters.confidence }}"><input type="hidden" name="notified" value="{{ filters.notified }}">
        <button class="reject small" type="submit" data-busy-text="…">Reject</button>
      </form>
      {% elif n.reviewed and not n.notified_at %}
      <form method="post" action="/admin/notify/{{ n.id }}" class="inline-form" data-banner-text="Sending to subscribers…">
        <input type="hidden" name="status" value="{{ filters.status }}"><input type="hidden" name="source_id" value="{{ filters.source_id }}"><input type="hidden" name="confidence" value="{{ filters.confidence }}"><input type="hidden" name="notified" value="{{ filters.notified }}">
        <button class="send small" type="submit" data-busy-text="…">Send <span class="info-icon" title="Delivers this approved notice to every subscriber tracking this exam, by SMS/Telegram. One-time — can't be sent twice.">i</span></button>
      </form>
      {% elif n.notified_at %}
      <span class="sent-note">Sent {{ n.notified_at_fmt }}</span>
      {% endif %}
    </td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</div>
{% else %}
<p class="empty">No notices match this filter.</p>
{% endif %}
"""

_EXTRACT_FORM = """
{{ stepper }}
<h1>Notices — Detected</h1>
<p class="page-sub">
  Stage 1 of the workflow above. The crawler finds pages that changed automatically — turning one into
  a real notice still takes you picking it and confirming it below, which is what costs money. Notices
  that pass the confidence gate go live immediately and move to Approved; flagged ones move to Pending
  Review instead.
</p>

{% if candidates %}
<h2 class="section-heading">Recently detected — not yet extracted</h2>
<p class="page-sub" style="margin-bottom:14px;">
  "Possibly: …" is a keyword guess at which existing exam this is about, and priority is a guess
  from words like "postponement" or "corrigendum" in the title — neither is authoritative, both
  are just to help you triage. Extraction is what actually determines both for real.
</p>
<div class="filter-bar">
  <div class="filter-field">
    <label for="cand-search">Search</label>
    <input type="text" id="cand-search" oninput="filterCandidates()" placeholder="Filter by keyword…">
  </div>
  <div class="filter-field">
    <label for="cand-priority">Priority</label>
    <select id="cand-priority" onchange="filterCandidates()">
      <option value="">All</option>
      <option value="high">Likely high-priority</option>
      <option value="routine">Routine</option>
    </select>
  </div>
</div>
<form class="card" method="post" action="/admin/extract/run" data-banner-text="Extracting — this can take up to 30 seconds per URL. Don't close this tab.">
  <input type="hidden" name="source_id" value="bpsc_bihar">
  <div class="candidate-list" id="candidate-list">
    {% for c in candidates %}
    <label class="candidate-row" data-priority="{{ c.priority }}" data-search="{{ ((c.title or c.url) ~ ' ' ~ (c.guessed_exam or '')) | lower }}">
      <input type="checkbox" name="selected_urls" value="{{ c.url }}">
      <span class="candidate-main">
        <span class="candidate-title">{{ c.title or c.url }}</span>
        <span class="candidate-hints">
          {% if c.guessed_exam %}<span class="pill pill-guess">Exam: possibly {{ c.guessed_exam }}</span>
          {% else %}<span class="pill pill-guess">Exam: no match — would create new</span>{% endif %}
          {% if c.priority == 'high' %}<span class="pill pill-risky">likely high-priority</span>{% endif %}
        </span>
      </span>
      <span class="candidate-meta mono">detected {{ c.first_seen_at[:16] }}</span>
    </label>
    {% endfor %}
  </div>
  <div class="actions">
    <button class="approve" type="submit" data-busy-text="Extracting…">Extract Selected <span class="info-icon" title="Sends each checked notice to the AI to pull out exam name, dates, and vacancy details. Costs one AI call per notice — this is the paid step. Result lands in Notices → Pending Review.">i</span></button>
  </div>
</form>
<script>
function filterCandidates() {
  var q = document.getElementById('cand-search').value.toLowerCase();
  var pr = document.getElementById('cand-priority').value;
  document.querySelectorAll('#candidate-list .candidate-row').forEach(function (row) {
    var matchesSearch = !q || row.dataset.search.indexOf(q) !== -1;
    var matchesPriority = !pr || row.dataset.priority === pr;
    row.style.display = (matchesSearch && matchesPriority) ? '' : 'none';
  });
}
</script>
{% else %}
<p class="page-sub">Nothing new detected right now — either the scheduler hasn't run yet, or everything it found has already been extracted.</p>
{% endif %}

<h2 class="section-heading">Or paste a URL directly</h2>
<form class="extract-form" method="post" action="/admin/extract/run" data-banner-text="Extracting — this can take up to 30 seconds per URL. Don't close this tab.">
  <div>
    <label class="field-label" for="source_id2">Source</label>
    <select id="source_id2" name="source_id">
      {% for sid in source_ids %}<option value="{{ sid }}">{{ sid }}</option>{% endfor %}
    </select>
  </div>
  <div>
    <label class="field-label" for="urls">Notice URLs — one per line</label>
    <textarea id="urls" name="urls" rows="5" placeholder="https://bpsc.bihar.gov.in/notifications/36527/"></textarea>
  </div>
  <div class="actions">
    <button class="approve" type="submit" data-busy-text="Extracting…">Extract &amp; Save <span class="info-icon" title="Sends each URL to the AI to pull out exam name, dates, and vacancy details. Costs one AI call per URL — this is the paid step. Use this for a notice the crawler hasn't picked up yet. Result lands in Notices → Pending Review.">i</span></button>
  </div>
</form>
"""

_EXTRACT_RESULT_ITEM = """
<div class="card">
  <div class="meta"><a class="source-link" href="{{ r.url }}" target="_blank" rel="noopener">{{ r.url }}</a></div>
  {% if r.error %}
    <p class="summary error-text">Failed: {{ r.error }}</p>
  {% else %}
    <div class="meta"><strong>{{ r.exam_name }}</strong></div>
    <div class="pill-row">
      <span class="pill pill-conf-{{ r.confidence }}">confidence: {{ r.confidence }}</span>
    </div>
    <p class="summary">{{ r.summary }}</p>
    {% if not r.created %}
    <p class="result-status result-status-neutral">Already extracted earlier — nothing new saved.</p>
    {% elif r.flagged %}
    <p class="result-status result-status-warn">&rarr; Needs your review before it goes live. <a href="/admin/notices?status=pending">Open Notices</a></p>
    {% else %}
    <p class="result-status result-status-ok">&#10003; Live now, no review needed. <a href="/admin/notices?status=approved">Open Notices to send it</a></p>
    {% endif %}
  {% endif %}
</div>
"""


def _render(title: str, body: str, pending_count: int, current: str) -> str:
    # body is already-rendered, already-escaped HTML (each item template
    # escaped its own untrusted fields) -- wrap it so the outer render
    # doesn't escape it a second time.
    return _env.from_string(_PAGE_SHELL).render(
        title=title, body=Markup(body), pending_count=pending_count, current=current
    )


def _pending_count(conn) -> int:
    return conn.execute("SELECT count(*) AS c FROM notices WHERE NOT reviewed AND NOT rejected").fetchone()["c"]


def _detected_count(conn) -> int:
    """Total candidates waiting to be extracted, across every active
    source -- not capped at the 25 shown on the Run Extraction page, since
    this feeds the stepper's real count, not a display list."""
    return sum(len(_extraction_candidates(conn, sid, limit=200)) for sid in active_source_ids())


def _workflow_counts(conn) -> dict:
    """The four stages of the Notices workflow (2026-08-27, "give a
    workflow on the top" -- folds the old separate Run Extraction page in
    as stage 1 instead of an unrelated menu item). Approved/Sent are
    disjoint by design -- an approved-and-sent notice only counts under
    Sent, so the four numbers describe non-overlapping "needs this action"
    buckets, not cumulative totals."""
    row = conn.execute(
        """
        SELECT
            count(*) FILTER (WHERE NOT reviewed AND NOT rejected) AS pending,
            count(*) FILTER (WHERE reviewed AND notified_at IS NULL) AS approved,
            count(*) FILTER (WHERE notified_at IS NOT NULL) AS sent
        FROM notices
        """
    ).fetchone()
    return {"detected": _detected_count(conn), "pending": row["pending"], "approved": row["approved"], "sent": row["sent"]}


def _render_stepper(conn, active: str) -> str:
    counts = _workflow_counts(conn)
    return _env.from_string(_STEPPER).render(counts=counts, active=active)


def _fmt_dt(dt) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def _job_status(job_runs: dict, job_name: str, label: str) -> dict:
    info = job_runs.get(job_name)
    if not info or not info.get("last_run_at"):
        return {"label": label, "detail": "Never run yet — start the scheduler.", "dot": "stale"}
    result = info.get("last_result") or ""
    dot = "err" if result.startswith("failed") else "ok"
    friendly = info["last_run_at"][:16].replace("T", " ") + " UTC"
    return {"label": label, "detail": f"{friendly} — {result}", "dot": dot}


@router.get("", include_in_schema=False)
@router.get("/", include_in_schema=False)
def admin_root():
    return RedirectResponse(url="/admin/dashboard", status_code=307)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(crawled: Optional[str] = Query(default=None)):
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        kpis = conn.execute(
            """
            SELECT count(*) FILTER (WHERE NOT reviewed AND NOT rejected) AS pending,
                   -- "Approved" means the same thing here as it does on the
                   -- Notices workflow stepper: reviewed AND not yet sent.
                   -- A sent notice only counts under "notified" below, not
                   -- both -- 2026-08-27, same word can't mean two things
                   -- on two pages.
                   count(*) FILTER (WHERE reviewed AND notified_at IS NULL) AS approved,
                   count(*) FILTER (WHERE rejected) AS rejected,
                   count(*) FILTER (WHERE notified_at IS NOT NULL) AS notified,
                   count(*) FILTER (WHERE detected_at >= current_date) AS today
            FROM notices
            """
        ).fetchone()
        subscribers = conn.execute("SELECT count(*) AS c FROM subscriptions WHERE active").fetchone()["c"]
        exam_count = conn.execute("SELECT count(*) AS c FROM exams").fetchone()["c"]
        daily_rows = conn.execute(
            """
            SELECT to_char(d.day, 'Mon DD') AS label, coalesce(n.c, 0) AS value
            FROM generate_series(current_date - interval '13 days', current_date, interval '1 day') AS d(day)
            LEFT JOIN (
                SELECT date_trunc('day', detected_at) AS day, count(*) AS c FROM notices GROUP BY 1
            ) n ON n.day = d.day
            ORDER BY d.day
            """
        ).fetchall()
        conf_rows = conn.execute(
            """
            SELECT confidence AS label, count(*) AS value FROM notices
            WHERE confidence IS NOT NULL GROUP BY confidence
            ORDER BY CASE confidence WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END
            """
        ).fetchall()
        type_rows = conn.execute(
            "SELECT change_type AS label, count(*) AS value FROM notices GROUP BY change_type ORDER BY value DESC"
        ).fetchall()

    with ingestion_connect() as sconn:
        job_runs = get_job_runs(sconn)
    # Generalized over every active source (2026-08-27 scalability pass) --
    # previously hardcoded to bpsc_bihar, which would have silently ignored
    # a second source's crawler status once one existed.
    jobs = []
    for sid in active_source_ids():
        cfg = get_source_config(sid)
        jobs.append(_job_status(job_runs, f"notice_poll:{sid}", f"{cfg['display_name']} — Notice Crawler"))
        jobs.append(_job_status(job_runs, f"calendar_sync:{sid}", f"{cfg['display_name']} — Exam Master List Crawler"))

    daily_json = json.dumps({"labels": [r["label"] for r in daily_rows], "values": [r["value"] for r in daily_rows]})
    conf_json = json.dumps({"labels": [r["label"] for r in conf_rows], "values": [r["value"] for r in conf_rows]})
    type_json = json.dumps({"labels": [r["label"] for r in type_rows], "values": [r["value"] for r in type_rows]})

    crawl_banner = {
        "notices": "Checked for new notices — see updated status above.",
        "calendar": "Exam master list sync finished — see updated status above.",
    }.get(crawled)

    body = _env.from_string(_DASHBOARD).render(
        kpis=kpis,
        subscribers=subscribers,
        exam_count=exam_count,
        jobs=jobs,
        daily_json=Markup(daily_json),
        conf_json=Markup(conf_json),
        type_json=Markup(type_json),
        crawl_banner=crawl_banner,
    )
    return _render("Dashboard", body, pending_count, current="dashboard")


@router.post("/crawl/notices/run")
def crawl_notices_run():
    """Manual, on-demand version of the scheduler's notice-poll job
    (2026-08-27, "what if i want to run another crawl, i dont get it";
    split into its own route 2026-08-28 -- the Dashboard used to fire this
    together with the calendar sync from one undifferentiated "Run Crawl
    Now" button, which is exactly the kind of unlabeled control the user's
    UX review called out ("what is that crawl doing?"). Now it's paired
    one-to-one with Settings' "Notice Crawler" card. Free: detection only,
    no LLM call, same as the scheduler's own job. Safe to run alongside a
    running scheduler process -- both just dedupe against the same
    seen_urls table.

    Wrapped per-source (matching run_forever's own per-job try/except in
    ingestion/scheduler.py) -- unlike the background scheduler loop, this
    runs inside a request, so an unwrapped exception here would surface as
    a raw 500 to whoever clicked the button instead of the "failed: ..."
    message the rest of this admin always shows for a failed action."""
    # Runs for every active source (2026-08-27 scalability pass), not just
    # bpsc_bihar -- one click still checks everything being tracked once a
    # second source exists.
    with ingestion_connect() as sconn:
        for sid in active_source_ids():
            try:
                result_notice = run_notice_poll(sid)
            except Exception as exc:
                result_notice = f"failed: {exc}"
            record_job_run(sconn, f"notice_poll:{sid}", result_notice or "ok")
    return RedirectResponse(url="/admin/dashboard?crawled=notices", status_code=303)


@router.post("/crawl/calendar/run")
def crawl_calendar_run():
    """Manual, on-demand version of the scheduler's exam-calendar sync job
    -- the Sync Exam Master List half of the split described in
    crawl_notices_run's docstring above. Paired one-to-one with Settings'
    "Exam Master List Crawler" card. Free: no LLM call, same as the
    scheduler's own job."""
    with ingestion_connect() as sconn:
        for sid in active_source_ids():
            try:
                result_calendar = run_calendar_sync(sid)
            except Exception as exc:
                result_calendar = f"failed: {exc}"
            record_job_run(sconn, f"calendar_sync:{sid}", result_calendar or "ok")
    return RedirectResponse(url="/admin/dashboard?crawled=calendar", status_code=303)


_MINUTES_PER_UNIT = {"minutes": 1, "hours": 60, "days": 1440}


def _minutes_to_value_unit(total_minutes: int) -> tuple:
    if total_minutes >= 1440 and total_minutes % 1440 == 0:
        return total_minutes // 1440, "days"
    if total_minutes >= 60 and total_minutes % 60 == 0:
        return total_minutes // 60, "hours"
    return total_minutes, "minutes"


def _effective_source_configs(conn) -> dict:
    """Merges each source's static config (ingestion/source_config.py) with
    any live overrides saved from the Settings page (sources.config_json in
    Postgres) -- the DB value wins when present. Only the two frequency
    fields are ever written there today; everything else still comes from
    the static file."""
    db_rows = {r["source_id"]: r["config_json"] for r in conn.execute("SELECT source_id, config_json FROM sources").fetchall()}
    result = {}
    for sid in active_source_ids():
        cfg = dict(SOURCE_CONFIGS[sid])
        db_cfg = db_rows.get(sid) or {}
        for key in ("poll_interval_minutes", "exam_calendar_sync_interval_minutes"):
            if key in db_cfg and db_cfg[key]:
                cfg[key] = db_cfg[key]
        result[sid] = cfg
    return result


@router.get("/settings", response_class=HTMLResponse)
def settings_page(saved: Optional[int] = Query(default=None), llm_saved: Optional[int] = Query(default=None)):
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        effective = _effective_source_configs(conn)
    with ingestion_connect() as sconn:
        job_runs = get_job_runs(sconn)
    sources = []
    source_groups = []
    for sid in active_source_ids():
        cfg = dict(effective[sid])
        cfg["poll_value"], cfg["poll_unit"] = _minutes_to_value_unit(cfg["poll_interval_minutes"])
        cfg["cal_value"], cfg["cal_unit"] = _minutes_to_value_unit(cfg["exam_calendar_sync_interval_minutes"])
        sources.append(cfg)
        source_groups.append(
            {
                "display_name": cfg["display_name"],
                "notice_job": _job_status(job_runs, f"notice_poll:{sid}", "Notice Crawler"),
                "calendar_job": _job_status(job_runs, f"calendar_sync:{sid}", "Exam Master List Crawler"),
            }
        )
    raw_llm = get_llm_settings()
    # Never pass real key values into the template context, even though the
    # template only uses them in a boolean check today -- a future template
    # edit could trivially leak them into rendered HTML otherwise.
    llm_settings = {
        "active_provider": raw_llm["active_provider"],
        "anthropic_model": raw_llm["anthropic_model"],
        "anthropic_api_key": bool(raw_llm.get("anthropic_api_key")),
        "openai_model": raw_llm["openai_model"],
        "openai_api_key": bool(raw_llm.get("openai_api_key")),
    }
    body = _env.from_string(_SETTINGS).render(
        sources=sources, source_groups=source_groups, saved=bool(saved), llm=llm_settings, llm_saved=bool(llm_saved)
    )
    return _render("Settings", body, pending_count, current="settings")


@router.post("/settings/llm")
def update_llm_settings(
    active_provider: str = Form(...),
    anthropic_model: str = Form(""),
    anthropic_api_key: str = Form(""),
    openai_model: str = Form(""),
    openai_api_key: str = Form(""),
):
    save_llm_settings(
        active_provider=active_provider,
        anthropic_model=anthropic_model.strip() or None,
        anthropic_api_key=anthropic_api_key.strip() or None,
        openai_model=openai_model.strip() or None,
        openai_api_key=openai_api_key.strip() or None,
    )
    return RedirectResponse(url="/admin/settings?llm_saved=1", status_code=303)


@router.post("/settings/{source_id}/frequency")
def update_frequency(
    source_id: str,
    poll_value: int = Form(...),
    poll_unit: str = Form("minutes"),
    calendar_value: int = Form(...),
    calendar_unit: str = Form("minutes"),
):
    poll_minutes = poll_value * _MINUTES_PER_UNIT.get(poll_unit, 1)
    calendar_minutes = calendar_value * _MINUTES_PER_UNIT.get(calendar_unit, 1)
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE sources
            SET config_json = config_json || jsonb_build_object(
                'poll_interval_minutes', %s::int,
                'exam_calendar_sync_interval_minutes', %s::int
            )
            WHERE source_id = %s
            """,
            (poll_minutes, calendar_minutes, source_id),
        )
    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)


@router.get("/exams", response_class=HTMLResponse)
def exams_list():
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        rows = conn.execute(
            """
            SELECT e.id, e.name, e.advt_no, e.vacancy_count, e.status, e.visible_on_b2c, s.source_id,
                   (SELECT count(*) FROM notices n WHERE n.exam_id = e.id) AS notice_count
            FROM exams e JOIN sources s ON s.id = e.source_id
            ORDER BY e.name
            """
        ).fetchall()
        from_calendar_count = conn.execute(
            "SELECT count(*) AS c FROM exams WHERE calendar_snapshot_json IS NOT NULL"
        ).fetchone()["c"]

    body = _env.from_string(_EXAMS_LIST).render(
        exams=rows, from_calendar_count=from_calendar_count, source_ids=active_source_ids()
    )
    return _render("Exams", body, pending_count, current="exams")


@router.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail(
    exam_id: int,
    sent: Optional[int] = Query(default=None),
    failed: Optional[int] = Query(default=None),
    no_channel: Optional[int] = Query(default=None),
    ext_live: Optional[int] = Query(default=None),
    ext_review: Optional[int] = Query(default=None),
    ext_failed: Optional[int] = Query(default=None),
):
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        exam = conn.execute(
            """
            SELECT e.*, s.display_name AS source_name
            FROM exams e JOIN sources s ON s.id = e.source_id
            WHERE e.id = %s
            """,
            (exam_id,),
        ).fetchone()
        if exam is None:
            return _render("Exam Not Found", '<h1>Not found</h1><p class="empty">No exam with that id.</p>', pending_count, current="exams")

        notice_rows = conn.execute(
            "SELECT * FROM notices WHERE exam_id = %s ORDER BY detected_at DESC", (exam_id,)
        ).fetchall()

    exam = dict(exam)
    exam["created_at_fmt"] = _fmt_dt(exam.get("created_at"))
    snapshot = exam.get("calendar_snapshot_json") or {}
    exam["discrepancy"] = snapshot.get("vacancy_count_discrepancy") if isinstance(snapshot, dict) else None

    notices = []
    for n in notice_rows:
        n = dict(n)
        n["detected_at_fmt"] = _fmt_dt(n["detected_at"])
        notices.append(n)

    banner = None
    if sent is not None:
        parts = [f"Sent to {sent} Telegram subscriber(s)"]
        if failed:
            parts.append(f"{failed} failed")
        if no_channel:
            parts.append(f"{no_channel} have no Telegram linked yet")
        banner = ", ".join(parts) + "."
    elif ext_live is not None:
        bits = []
        if ext_live:
            bits.append(f"{ext_live} went live automatically")
        if ext_review:
            bits.append(f"{ext_review} need your review")
        if ext_failed:
            bits.append(f"{ext_failed} failed")
        banner = ("Extraction done — " + ", ".join(bits) + ".") if bits else "Extraction ran but found nothing new."

    body = _env.from_string(_EXAM_DETAIL).render(exam=exam, notices=notices, banner=banner)
    return _render(exam["name"], body, pending_count, current="exams")


@router.post("/exams/{exam_id}/visibility")
def exam_visibility(exam_id: int, visible: str = Form(...)):
    with get_connection() as conn:
        conn.execute("UPDATE exams SET visible_on_b2c = %s WHERE id = %s", (visible == "1", exam_id))
    return RedirectResponse(url=f"/admin/exams/{exam_id}", status_code=303)


@router.post("/exams/{exam_id}/extract")
def exam_extract(exam_id: int, urls: str = Form("")):
    url_list = [u.strip() for u in urls.splitlines() if u.strip()]
    with get_connection() as conn:
        exam = conn.execute(
            "SELECT s.source_id FROM exams e JOIN sources s ON s.id = e.source_id WHERE e.id = %s", (exam_id,)
        ).fetchone()
        if exam is None:
            return RedirectResponse(url="/admin/exams", status_code=303)
        results = _extract_urls(conn, exam["source_id"], url_list)

    live = sum(1 for r in results if not r.get("error") and r.get("created") and not r.get("flagged"))
    review = sum(1 for r in results if not r.get("error") and r.get("created") and r.get("flagged"))
    failed = sum(1 for r in results if r.get("error"))
    return RedirectResponse(
        url=f"/admin/exams/{exam_id}?ext_live={live}&ext_review={review}&ext_failed={failed}", status_code=303
    )


@router.get("/integrity", response_class=HTMLResponse)
def integrity_page(saved: Optional[int] = Query(default=None), exam_id: Optional[int] = Query(default=None)):
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        rows = conn.execute(
            "SELECT * FROM integrity_incidents ORDER BY incident_date DESC NULLS LAST, created_at DESC"
        ).fetchall()
        active_exams = conn.execute("SELECT id, name FROM exams WHERE visible_on_b2c ORDER BY name").fetchall()

    incidents = []
    for r in rows:
        r = dict(r)
        r["incident_date_fmt"] = r["incident_date"].isoformat() if r.get("incident_date") else None
        incidents.append(r)

    banner = "Incident logged." if saved else None
    body = _env.from_string(_INTEGRITY_PAGE).render(
        incidents=incidents,
        banner=banner,
        exam_names=[e["name"] for e in active_exams],
        active_exams=active_exams,
        selected_exam_id=exam_id,
    )
    return _render("Integrity", body, pending_count, current="integrity")


@router.post("/integrity/search", response_class=HTMLResponse)
def integrity_search(exam_id: int = Form(...), keyword: str = Form(""), force: str = Form("")):
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        exam = conn.execute(
            "SELECT e.name, s.display_name AS source_name FROM exams e JOIN sources s ON s.id = e.source_id WHERE e.id = %s",
            (exam_id,),
        ).fetchone()
        if exam is None:
            return RedirectResponse(url="/admin/integrity", status_code=303)

        # Cost-avoidance check (2026-08-27, "what if I run the same
        # keyword and exams again is gonna cost me money uselessly") --
        # matches on exam + normalized keyword against every past search,
        # not just recent ones, since "I already did this" doesn't expire.
        # Doesn't block, just interrupts with the prior result and a
        # deliberate Search Anyway button.
        if not force:
            prior = conn.execute(
                """
                SELECT id, searched_at, candidates_found, candidates_logged
                FROM integrity_searches
                WHERE exam_id = %s AND lower(trim(coalesce(keyword, ''))) = %s
                ORDER BY searched_at DESC LIMIT 1
                """,
                (exam_id, keyword.strip().lower()),
            ).fetchone()
            if prior is not None:
                body = _env.from_string(_INTEGRITY_DUPLICATE_WARNING).render(
                    exam_id=exam_id,
                    exam_name=exam["name"],
                    keyword=keyword,
                    prior=dict(prior),
                    prior_searched_at_fmt=_fmt_dt(prior["searched_at"]),
                )
                return _render("Integrity Search", body, pending_count, current="integrity")

    try:
        results = search_incidents_for_exam(exam["name"], exam["source_name"], keyword=keyword)
    except Exception as exc:
        body = (
            f'<h1>Integrity Search — {exam["name"]}</h1>'
            f'<p class="summary error-text">Search failed: {exc}</p>'
            f'<p class="hint-inline"><a href="/admin/integrity">&larr; Back to Integrity</a></p>'
        )
        return _render("Integrity Search", body, pending_count, current="integrity")

    with get_connection() as conn:
        search_id = conn.execute(
            "INSERT INTO integrity_searches (exam_id, exam_name, keyword, candidates_found) VALUES (%s, %s, %s, %s) RETURNING id",
            (exam_id, exam["name"], keyword.strip() or None, len(results)),
        ).fetchone()["id"]

    candidates = [{**c, "json": json.dumps(c)} for c in results]
    body = _env.from_string(_INTEGRITY_SEARCH_RESULTS).render(
        exam_name=exam["name"], exam_id=exam_id, candidates=candidates, keyword=keyword, search_id=search_id
    )
    return _render("Integrity Search", body, pending_count, current="integrity")


@router.post("/integrity/search/save")
def integrity_search_save_general(
    exam_id: int = Form(...), candidates: list[str] = Form(default=[]), search_id: Optional[int] = Form(None)
):
    with get_connection() as conn:
        exam = conn.execute("SELECT name, source_id FROM exams WHERE id = %s", (exam_id,)).fetchone()
        if exam is None:
            return RedirectResponse(url="/admin/integrity", status_code=303)

        saved = 0
        for raw in candidates:
            try:
                c = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not c.get("source_url"):
                continue
            conn.execute(
                """
                INSERT INTO integrity_incidents
                    (source_id, exam_name, cycle, centre, incident_type, detection_source, resolution, source_url, incident_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    exam["source_id"],
                    exam["name"],
                    None,
                    c.get("centre"),
                    c.get("incident_type") or "other",
                    "News report (web search)",
                    c.get("snippet") or c.get("headline"),
                    c["source_url"],
                    c.get("incident_date") or None,
                ),
            )
            saved += 1

        if search_id:
            conn.execute("UPDATE integrity_searches SET candidates_logged = %s WHERE id = %s", (saved, search_id))

    return RedirectResponse(url=f"/admin/integrity?saved={saved}", status_code=303)


@router.get("/integrity/history", response_class=HTMLResponse)
def integrity_history_page():
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        rows = conn.execute("SELECT * FROM integrity_searches ORDER BY searched_at DESC").fetchall()

    searches = []
    for r in rows:
        r = dict(r)
        r["searched_at_fmt"] = _fmt_dt(r["searched_at"])
        searches.append(r)

    body = _env.from_string(_INTEGRITY_HISTORY_PAGE).render(searches=searches)
    return _render("Integrity Search History", body, pending_count, current="integrity")


@router.post("/integrity/add")
def integrity_add(
    exam_name: str = Form(...),
    cycle: str = Form(""),
    centre: str = Form(""),
    incident_type: str = Form("other"),
    detection_source: str = Form(...),
    incident_date: str = Form(""),
    resolution: str = Form(""),
    source_url: str = Form(...),
):
    with get_connection() as conn:
        source_pk = conn.execute("SELECT id FROM sources WHERE source_id = 'bpsc_bihar'").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO integrity_incidents
                (source_id, exam_name, cycle, centre, incident_type, detection_source, resolution, source_url, incident_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                source_pk,
                exam_name.strip(),
                cycle.strip() or None,
                centre.strip() or None,
                incident_type,
                detection_source.strip(),
                resolution.strip() or None,
                source_url.strip(),
                incident_date or None,
            ),
        )
    return RedirectResponse(url="/admin/integrity?saved=1", status_code=303)


def _notices_redirect_url(status: str, source_id: str, confidence: str, **extra) -> str:
    params = {}
    if status:
        params["status"] = status
    if source_id:
        params["source_id"] = source_id
    if confidence:
        params["confidence"] = confidence
    params.update({k: v for k, v in extra.items() if v is not None})
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return "/admin/notices" + (f"?{query}" if query else "")


@router.get("/notices", response_class=HTMLResponse)
def notices_page(
    status: str = Query(default="pending"),
    source_id: str = Query(default=""),
    confidence: str = Query(default=""),
    notified: Optional[str] = Query(default=None),  # "0"/"1" workflow-stage filter -- NOT the notify-banner count below
    sent: Optional[int] = Query(default=None),
    failed: Optional[int] = Query(default=None),
    no_channel: Optional[int] = Query(default=None),
):
    where = ["1=1"]
    params: list = []
    if status == "pending":
        where.append("NOT n.reviewed AND NOT n.rejected")
    elif status == "approved":
        where.append("n.reviewed")
    elif status == "rejected":
        where.append("n.rejected")
    if source_id:
        where.append("s.source_id = %s")
        params.append(source_id)
    if confidence:
        where.append("n.confidence = %s")
        params.append(confidence)
    if notified == "0":
        where.append("n.notified_at IS NULL")
    elif notified == "1":
        where.append("n.notified_at IS NOT NULL")

    sql = f"""
        SELECT n.*, e.name AS exam_name, s.source_id AS source_id
        FROM notices n
        JOIN exams e ON e.id = n.exam_id
        JOIN sources s ON s.id = e.source_id
        WHERE {' AND '.join(where)}
        ORDER BY n.detected_at DESC
        LIMIT 200
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        pending_count = _pending_count(conn)
        # Stage the stepper highlights, derived from the filters actually
        # in effect -- "All"/"Rejected" don't map to a workflow stage, so
        # neither step lights up for those, which is correct (they're not
        # part of the linear flow the stepper shows).
        if notified == "1":
            stage = "sent"
        elif status == "pending":
            stage = "pending"
        elif status == "approved" and notified == "0":
            stage = "approved"
        else:
            stage = ""
        stepper = _render_stepper(conn, active=stage)

    table_rows = []
    for r in rows:
        r = dict(r)
        r["detected_at_fmt"] = _fmt_dt(r["detected_at"])
        r["notified_at_fmt"] = _fmt_dt(r["notified_at"])
        table_rows.append(r)

    banner = None
    if sent is not None:
        parts = [f"Sent to {sent} Telegram subscriber(s)"]
        if failed:
            parts.append(f"{failed} failed")
        if no_channel:
            parts.append(f"{no_channel} have no Telegram linked yet (WhatsApp not built)")
        banner = ", ".join(parts) + "."

    filters = {"status": status, "source_id": source_id, "confidence": confidence, "notified": notified or ""}
    body = stepper + _env.from_string(_NOTICES_PAGE).render(
        rows=table_rows, filters=filters, source_ids=active_source_ids(), banner=banner
    )
    return _render("Notices", body, pending_count, current="notices")


@router.get("/review", include_in_schema=False)
def review_redirect():
    return RedirectResponse(url="/admin/notices?status=pending", status_code=307)


@router.get("/history", include_in_schema=False)
def history_redirect():
    return RedirectResponse(url="/admin/notices?status=approved", status_code=307)


@router.post("/review/{notice_id}/approve")
def approve(
    notice_id: int,
    status: str = Form(""),
    source_id: str = Form(""),
    confidence: str = Form(""),
    notified: str = Form(""),
    redirect_to: str = Form(""),
):
    with get_connection() as conn:
        conn.execute(
            "UPDATE notices SET reviewed = true, rejected = false, reviewed_at = now() WHERE id = %s",
            (notice_id,),
        )
    return RedirectResponse(
        url=redirect_to or _notices_redirect_url(status, source_id, confidence, notified=notified or None),
        status_code=303,
    )


@router.post("/review/{notice_id}/reject")
def reject(
    notice_id: int,
    status: str = Form(""),
    source_id: str = Form(""),
    confidence: str = Form(""),
    notified: str = Form(""),
    redirect_to: str = Form(""),
):
    with get_connection() as conn:
        conn.execute(
            "UPDATE notices SET rejected = true, reviewed = false, reviewed_at = now() WHERE id = %s",
            (notice_id,),
        )
    return RedirectResponse(
        url=redirect_to or _notices_redirect_url(status, source_id, confidence, notified=notified or None),
        status_code=303,
    )


@router.post("/notify/{notice_id}")
def notify(
    notice_id: int,
    status: str = Form(""),
    source_id: str = Form(""),
    confidence: str = Form(""),
    notified: str = Form(""),
    redirect_to: str = Form(""),
):
    counts = notify_subscribers(notice_id)
    if redirect_to:
        sep = "&" if "?" in redirect_to else "?"
        return RedirectResponse(
            url=f"{redirect_to}{sep}sent={counts['telegram_sent']}&failed={counts['telegram_failed']}&no_channel={counts['no_channel']}",
            status_code=303,
        )
    return RedirectResponse(
        url=_notices_redirect_url(
            status,
            source_id,
            confidence,
            notified=notified or None,
            sent=counts["telegram_sent"],
            failed=counts["telegram_failed"],
            no_channel=counts["no_channel"],
        ),
        status_code=303,
    )


# Heuristic hints for the pre-extraction candidate list (2026-08-25, "not
# sure which exam the pdf is related to, what is the priority") -- these are
# guesses from the title text alone, computed before any LLM call, purely to
# help an operator triage a long list. Neither is authoritative: extraction
# is what actually determines the real exam_name/change_type/confidence.
_GUESS_STOPWORDS = {
    "the", "of", "in", "for", "and", "exam", "examination", "examinations", "competitive",
    "preliminary", "written", "service", "services", "commission", "post", "posts", "regarding",
    "notice", "notices", "important", "advertisement", "advt", "no", "bpsc", "bihar", "public",
    "interview", "date", "commencement", "facility", "candidates", "various", "under",
}
_GUESS_PRIORITY_KEYWORDS = {
    "postpone", "postponed", "postponement", "corrigendum", "cancel", "cancelled", "cancellation",
    "result", "revise", "revised", "revision", "deletion", "deleted",
}


def _significant_tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9.]+", text.lower())
    return {w for w in words if w not in _GUESS_STOPWORDS and len(w) >= 3}


def _guess_exam(title: str, exam_names: list) -> Optional[str]:
    title_tokens = _significant_tokens(title)
    if not title_tokens:
        return None
    best, best_score = None, 1  # require at least 2 overlapping distinctive words
    for name in exam_names:
        overlap = len(title_tokens & _significant_tokens(name))
        if overlap > best_score:
            best, best_score = name, overlap
    return best


def _guess_priority(title: str) -> str:
    lowered = title.lower()
    return "high" if any(k in lowered for k in _GUESS_PRIORITY_KEYWORDS) else "routine"


def _extraction_candidates(pg_conn, source_id: str, limit: int = 25) -> list:
    """Recently-detected pages (ingestion_state.db, written by the
    scheduler) that don't already have a notices row -- i.e. genuinely
    still waiting to be turned into something. Powers the admin panel's
    "recently detected" list so an operator isn't stuck reading a log file
    to find a URL to extract. Each candidate also gets a best-effort
    guessed_exam and priority hint (see _guess_exam/_guess_priority above)."""
    with ingestion_connect() as sconn:
        recent = get_recent_seen(sconn, source_id, limit=limit)
    if not recent:
        return []
    urls = [r["url"] for r in recent]
    already = pg_conn.execute("SELECT source_url FROM notices WHERE source_url = ANY(%s)", (urls,)).fetchall()
    already_urls = {row["source_url"] for row in already}
    candidates = [dict(r) for r in recent if r["url"] not in already_urls]
    if not candidates:
        return []

    exam_names = [
        row["name"]
        for row in pg_conn.execute(
            "SELECT e.name FROM exams e JOIN sources s ON s.id = e.source_id WHERE s.source_id = %s", (source_id,)
        ).fetchall()
    ]
    for c in candidates:
        title = c.get("title") or ""
        c["guessed_exam"] = _guess_exam(title, exam_names)
        c["priority"] = _guess_priority(title)
    return candidates


@router.get("/extract", response_class=HTMLResponse)
def extract_form():
    with get_connection() as conn:
        pending_count = _pending_count(conn)
        candidates = []
        for sid in active_source_ids():
            candidates.extend(_extraction_candidates(conn, sid))
        stepper = _render_stepper(conn, active="detected")
    body = _env.from_string(_EXTRACT_FORM).render(
        source_ids=active_source_ids(), candidates=candidates, stepper=Markup(stepper)
    )
    return _render("Notices — Detected", body, pending_count, current="notices")


def _extract_urls(conn, source_id: str, url_list: list) -> list:
    """Shared core of the extraction trigger -- used by the main Run
    Extraction page and (2026-08-25, "run extraction... for it") the
    per-exam mini extraction form on the exam detail page. Takes an
    already-open connection so a caller can inspect results (e.g. which
    exam_id things landed on) in the same transaction."""
    config = get_source_config(source_id)
    rate_limiter = RateLimiter(config["rate_limit_seconds"])

    results = []
    for url in url_list:
        try:
            if url.lower().split("?")[0].endswith(".pdf"):
                rate_limiter.wait()
                pdf_bytes = fetch_pdf_bytes(
                    url, user_agent=config["user_agent"], timeout_seconds=config["request_timeout_seconds"]
                )
                notice = extract_notice_from_pdf(pdf_bytes=pdf_bytes, source_url=url, source_id=source_id)
            else:
                page = fetch_page(url, source_id, rate_limiter)
                notice = extract_notice(
                    page_text=f"{page.title}\n\n{page.text_content}", source_url=url, source_id=source_id
                )
        except Exception as exc:
            results.append({"url": url, "error": str(exc)})
            continue

        notice_id, created = persist_notice(conn, notice)
        results.append(
            {
                "url": url,
                "error": None,
                "notice_id": notice_id,
                "exam_name": notice.exam_name,
                "confidence": notice.confidence,
                "flagged": needs_human_review(notice),
                "summary": notice.summary_plain_language,
                "created": created,
            }
        )
    return results


@router.post("/extract/run", response_class=HTMLResponse)
def extract_run(source_id: str = Form("bpsc_bihar"), urls: str = Form(""), selected_urls: list[str] = Form(default=[])):
    # Merge both entry points (checkbox picks + pasted textarea) into one
    # deduped, order-preserving list -- only one is ever populated per
    # submit since they're two separate <form>s, but merging is harmless
    # either way.
    url_list = list(dict.fromkeys([u.strip() for u in urls.splitlines() if u.strip()] + selected_urls))

    with get_connection() as conn:
        results = _extract_urls(conn, source_id, url_list)
        pending_count = _pending_count(conn)
        stepper = _render_stepper(conn, active="detected")

    # stepper/head are trusted, already-rendered HTML strings, same as
    # every other piece assembled below -- kept as plain str through this
    # whole function and wrapped in Markup exactly once, by _render() at
    # the end. Wrapping any piece in Markup earlier would auto-escape the
    # next plain string it's concatenated with (Markup.__add__ escapes a
    # plain-str operand), corrupting the raw HTML in these f-strings.
    head = stepper + "<h1>Extraction Results</h1>"
    if not results:
        body = head + '<p class="empty">No URLs were submitted.</p>'
    else:
        live_count = sum(1 for r in results if not r.get("error") and r.get("created") and not r.get("flagged"))
        review_count = sum(1 for r in results if not r.get("error") and r.get("created") and r.get("flagged"))
        error_count = sum(1 for r in results if r.get("error"))
        summary_bits = []
        if live_count:
            summary_bits.append(f"{live_count} went live automatically")
        if review_count:
            summary_bits.append(f"{review_count} need your review")
        if error_count:
            summary_bits.append(f"{error_count} failed")
        summary_line = f"{len(results)} URL(s) processed — " + ", ".join(summary_bits) + "." if summary_bits else f"{len(results)} URL(s) processed."

        item_tpl = _env.from_string(_EXTRACT_RESULT_ITEM)
        body = head + f'<p class="page-sub">{summary_line}</p>' + "".join(item_tpl.render(r=r) for r in results)
        body += '<p class="hint-inline"><a href="/admin/extract">Run more</a> &middot; <a href="/admin/notices?status=pending">Open Notices</a></p>'

    return _render("Extraction Results", body, pending_count, current="notices")
