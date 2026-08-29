"""
LLM-based structuring of raw notice text into the shared schema (tech
architecture doc, section 5), plus the human-review gate.

Calls go through llm.provider (2026-08-27, "allow me to use any model...
to save on the cost") rather than instantiating anthropic.Anthropic()
directly -- which provider/model/key actually runs is decided by the
admin Settings page, not by this module. Default remains Anthropic with
ANTHROPIC_API_KEY (or another credential source the SDK resolves
automatically) until a different provider is picked in Settings.
"""

from __future__ import annotations

import logging

from extraction.schema import RISKY_CHANGE_TYPES, ExtractedNotice, LLMExtractedFields
from llm.provider import extract_structured

logger = logging.getLogger(__name__)

# PRD / tech architecture doc section 5: the human-review gate must exist as
# a toggle from the start, default ON. Do not flip this off without explicit
# product sign-off -- it is what stops a bad extraction from silently
# triggering a WhatsApp notification.
HUMAN_REVIEW_GATE_ENABLED = True

SYSTEM_PROMPT = """You structure official Indian state exam-body notices (BPSC and similar) into a fixed schema for a citizen-facing notification platform.

Rules:
- summary_plain_language must be ONE short sentence a non-bureaucratic reader can understand immediately (e.g. "Your exam has been postponed to a new date"), not a restatement of the official wording.
- old_value/new_value: fill both only when this notice revises a previously stated fact (a date, a vacancy count, a venue). Leave both null for a brand-new notification with nothing to compare against.
- effective_date: the date the change takes effect, in YYYY-MM-DD format if determinable, else null. Do not guess a date that isn't stated or clearly implied by the text.
- confidence: "high" only when the notice's meaning and every field above are unambiguous from the text. Use "medium" or "low" whenever the source text is vague, appears truncated/boilerplate-only, or requires inference rather than a value read directly from the page.
- Do not invent an advt_no, exam_name, or date that is not present in the text.
"""


def extract_notice(page_text: str, source_url: str, source_id: str) -> ExtractedNotice:
    fields = extract_structured(
        system_prompt=SYSTEM_PROMPT,
        schema=LLMExtractedFields,
        user_text=f"Source URL: {source_url}\n\nNotice text:\n{page_text}",
    )
    return ExtractedNotice.from_llm_fields(fields, source_id=source_id, source_url=source_url)


def extract_notice_from_pdf(pdf_bytes: bytes, source_url: str, source_id: str) -> ExtractedNotice:
    """
    Sends the PDF directly to the model as a document/vision input rather
    than pre-extracting text with pypdf. Verified necessary against real
    BPSC notices (Aug 2026), most of which are scanned/image-only PDFs
    with no embedded text layer -- vision reads those; pypdf cannot. See
    pdf_handler.py module docstring.
    """
    fields = extract_structured(
        system_prompt=f"{SYSTEM_PROMPT}\n\nSource URL: {source_url}",
        schema=LLMExtractedFields,
        pdf_bytes=pdf_bytes,
    )
    return ExtractedNotice.from_llm_fields(fields, source_id=source_id, source_url=source_url)


def needs_human_review(notice: ExtractedNotice) -> bool:
    """
    With the gate ON (default), any output below "high" confidence, or of a
    high-stakes change_type (postponement / vacancy_revision /
    result_declared), must be manually reviewed before it can trigger a
    notification. Toggling the gate off bypasses this entirely.
    """
    if not HUMAN_REVIEW_GATE_ENABLED:
        return False
    return notice.confidence != "high" or notice.change_type in RISKY_CHANGE_TYPES
