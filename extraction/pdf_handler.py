"""
PDF handling for linked results/advertisement PDFs (tech architecture doc,
section 4 step 4 identifies PDF links during ingestion; this module is
where they're turned into content the extractor can use).

Verified against real BPSC notices (Aug 2026): most are scanned/image-only
PDFs with no embedded text layer -- pypdf's extract_text() returns empty on
them. Rather than requiring a separate OCR dependency, the extractor sends
PDF bytes straight to Claude as a document input, which reads scanned PDFs
natively via vision. extract_text_from_pdf_bytes() is kept as a cheap,
no-LLM-call path for the (less common) PDFs that do carry a real text
layer -- see extractor.extract_notice_from_pdf for how the two combine.
"""

from __future__ import annotations

import io
import logging

import requests
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def fetch_pdf_bytes(url: str, user_agent: str, timeout_seconds: int) -> bytes:
    resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.content


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages_text = []
    for i, page in enumerate(reader.pages):
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as exc:
            logger.warning("Failed to extract text from PDF page %d: %s", i, exc)
    return "\n".join(pages_text).strip()


def fetch_and_extract_pdf_text(url: str, user_agent: str, timeout_seconds: int) -> str:
    return extract_text_from_pdf_bytes(fetch_pdf_bytes(url, user_agent, timeout_seconds))
