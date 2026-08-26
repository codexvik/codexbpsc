"""
Shared extraction schema (tech architecture doc, section 5). Every source
(BPSC today, other state PSCs later) is structured into this same shape, so
downstream consumers (DB, API, notifications) never need per-source
branching.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["notice", "program", "interview", "result", "advertisement", "corrigendum"]
ChangeType = Literal[
    "new_notification", "postponement", "date_change", "vacancy_revision", "result_declared", "other"
]
Confidence = Literal["high", "medium", "low"]

# Section 5 / PRD: these change_types are always high-stakes enough to
# require manual review before they can trigger a notification, regardless
# of confidence.
RISKY_CHANGE_TYPES = {"postponement", "vacancy_revision", "result_declared"}


class LLMExtractedFields(BaseModel):
    """
    What the model is asked to infer from raw notice text. source_id and
    source_url are already known from the ingestion step and are
    deliberately NOT part of this model -- asking the LLM to reproduce them
    just invites hallucination of a URL/source that doesn't match input.
    """

    exam_name: str
    advt_no: Optional[str] = None
    category: Category
    change_type: ChangeType
    summary_plain_language: str = Field(
        description="One short, plain-language sentence a candidate can understand at a glance."
    )
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    effective_date: Optional[str] = None
    confidence: Confidence


class ExtractedNotice(BaseModel):
    """Full structured record -- tech architecture doc, section 5."""

    source_id: str
    exam_name: str
    advt_no: Optional[str] = None
    category: Category
    change_type: ChangeType
    summary_plain_language: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    effective_date: Optional[str] = None
    source_url: str
    confidence: Confidence

    @classmethod
    def from_llm_fields(cls, fields: LLMExtractedFields, source_id: str, source_url: str) -> "ExtractedNotice":
        return cls(source_id=source_id, source_url=source_url, **fields.model_dump())
