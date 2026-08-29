"""
Web-search-assisted candidate discovery for the Integrity Scoreboard's
Phase 0 historical baseline (2026-08-27, "you could also crawl on the
internet and give a side panel to select"). Uses the active provider's
server-side web search tool (not a raw scraper, and not necessarily
Anthropic -- see llm/provider.py, 2026-08-27) so every candidate carries a
real URL actually found live -- nothing here is invented. Scoped to one
exam at a time by design, matching the roadmap's own corroboration
principle: a machine surfaces candidates, a human decides what's real.
This module only returns candidates -- it never writes to
integrity_incidents itself; that happens in api/admin.py only after an
operator picks which ones to keep.
"""

from __future__ import annotations

import json
import logging

from llm.provider import search_web

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are researching real, publicly documented exam-integrity incidents \
(paper leaks, malpractice allegations, re-tests ordered, administrative irregularities) for \
a specific government exam. Use web search to find real news articles, court records, or \
official statements. Only include an incident if you found a real source URL for it during \
this search -- never invent one, and never include an incident you are not confident is real \
and specifically about this exam.

After searching, respond with ONLY a JSON array (no other text, no markdown fences) of \
objects with these exact keys:
- "headline": short string describing the incident
- "snippet": one-sentence summary of what happened
- "incident_type": one of "paper_leak", "re_test_ordered", "malpractice", "admin_irregularity", "other"
- "centre": exam centre name if the incident was centre-specific, else null
- "incident_date": "YYYY-MM-DD" if determinable, else null
- "source_url": the real URL you found this from -- required for every entry

If you find no real, sourced incidents, respond with an empty array: []"""


def search_incidents_for_exam(exam_name: str, board_name: str, keyword: str = "") -> list:
    """Returns a list of candidate dicts (headline, snippet, incident_type,
    centre, incident_date, source_url). Every returned candidate has a
    non-empty source_url -- anything without one is dropped here, not left
    for the caller to filter. `keyword` narrows the search (2026-08-27,
    "add cycle name or key word") -- e.g. a cycle label like "TRE-3" or a
    specific term like "leak" -- appended to the query when given."""
    query = (
        f'Real documented exam-integrity incidents (paper leak, malpractice, re-test ordered, '
        f'administrative irregularity) for "{exam_name}" conducted by {board_name}.'
    )
    if keyword.strip():
        query += f' Focus the search on: {keyword.strip()}.'

    raw = search_web(system_prompt=_SYSTEM_PROMPT, query=query).strip()
    if not raw:
        return []
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        candidates = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Integrity search returned non-JSON output, discarding: %r", raw[:300])
        return []
    if not isinstance(candidates, list):
        return []

    cleaned = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("source_url"):
            continue  # no citation, no candidate -- the roadmap's own rule
        cleaned.append(
            {
                "headline": c.get("headline") or "",
                "snippet": c.get("snippet") or "",
                "incident_type": c.get("incident_type") or "other",
                "centre": c.get("centre"),
                "incident_date": c.get("incident_date"),
                "source_url": c["source_url"],
            }
        )
    return cleaned
