"""Request/response models for the public API (design doc pages 3.1-3.5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class ExamSummary(BaseModel):
    id: int
    name: str
    advt_no: Optional[str] = None
    category: Optional[str] = None
    vacancy_count: Optional[int] = None
    status: Optional[str] = None
    latest_change_snippet: Optional[str] = None
    notice_count: int = 0
    # Discovery/browse metadata (2026-08-24 redesign) -- sourced from the
    # exam's source_config (board_category/monogram), never guessed per exam.
    board_category: Optional[str] = None
    board_monogram: Optional[str] = None
    # True only once the archival service (parked, docs/backlog.md) actually
    # attaches an archive_url to a notice -- always False until then, not a
    # stand-in "trust" claim.
    verified: bool = False
    next_key_date_label: Optional[str] = None
    next_key_date_value: Optional[str] = None


class NoticeOut(BaseModel):
    id: int
    exam_id: int
    source_url: str
    change_type: str
    summary_plain_language: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    effective_date: Optional[date] = None
    confidence: Optional[str] = None
    archive_url: Optional[str] = None
    detected_at: datetime


class ExamDetail(BaseModel):
    id: int
    name: str
    advt_no: Optional[str] = None
    category: Optional[str] = None
    vacancy_count: Optional[int] = None
    status: Optional[str] = None
    eligibility_json: Optional[dict] = None
    key_dates_json: Optional[dict] = None
    notices: list[NoticeOut]
    board_category: Optional[str] = None
    board_monogram: Optional[str] = None
    board_name: Optional[str] = None
    board_name_hindi: Optional[str] = None
    official_website: Optional[str] = None
    verified: bool = False
    next_key_date_label: Optional[str] = None
    next_key_date_value: Optional[str] = None


class SubscribeRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=20)
    exam_id: int


class SubscribeResponse(BaseModel):
    exam_id: int
    phone_number: str
    active: bool


class EligibilityCheckRequest(BaseModel):
    exam_id: int
    degree: str
    age: int = Field(ge=0, le=100)
    category: str


class EligibilityCheckResponse(BaseModel):
    exam_id: int
    eligible: Optional[bool] = None  # None = we don't have eligibility criteria for this exam yet
    reason: str


class ResultSearchResponse(BaseModel):
    found: bool
    roll_number: str
    status: Optional[str] = None
    rank: Optional[int] = None
    source_notice_url: Optional[str] = None


class CallbackRequest(BaseModel):
    phone_number: str = Field(min_length=8, max_length=20)
    exam_id: Optional[int] = None


class CallbackRequestResponse(BaseModel):
    id: int
    phone_number: str
    exam_id: Optional[int] = None


class AlertItem(BaseModel):
    """One notice, flattened with its exam name -- shaped for a personal
    notification feed (design: 'My Alerts', phone-number lookup, no
    login) rather than for the per-exam notice feed NoticeOut serves."""

    id: int
    exam_id: int
    exam_name: str
    source_url: str
    change_type: str
    summary_plain_language: Optional[str] = None
    effective_date: Optional[date] = None
    confidence: Optional[str] = None
    archive_url: Optional[str] = None
    detected_at: datetime
