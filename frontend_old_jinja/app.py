"""
Server-rendered B2C frontend (design doc, all sections) -- Jinja2 templates
+ plain JS only, per the design doc's "minimal JS bundle weight ... no
heavy hero imagery" mobile-first requirement (section 1.3). Calls the
public API (api/main.py) over HTTP rather than touching the database
directly, so every business rule (source scoping, review-gate filtering,
eligibility logic) stays defined in exactly one place.

Run (with the API already running separately):
    uvicorn frontend.app:app --port 8080 --reload
"""

from __future__ import annotations

import os
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8123")

app = FastAPI(title="Codex BPSC Frontend")
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")
templates.env.globals["API_BASE_URL"] = API_BASE_URL

# design doc section 2: consistent status -> color/label across every card
# and detail page, paired with text (never color alone), per section 5
# accessibility notes.
STATUS_DISPLAY = {
    "open": {"label_en": "Open", "label_hi": "खुला", "color": "green"},
    "postponed": {"label_en": "Postponed", "label_hi": "स्थगित", "color": "amber"},
    "closed": {"label_en": "Closed", "label_hi": "बंद", "color": "gray"},
    "result_declared": {
        "label_en": "Result Declared",
        "label_hi": "परिणाम घोषित",
        "color": "blue",
    },
    "interview_scheduled": {
        "label_en": "Interview Scheduled",
        "label_hi": "साक्षात्कार निर्धारित",
        "color": "blue",
    },
}


def status_display(status: Optional[str]) -> dict:
    if status and status in STATUS_DISPLAY:
        return STATUS_DISPLAY[status]
    return {"label_en": status or "Unknown", "label_hi": status or "अज्ञात", "color": "gray"}


templates.env.filters["status_display"] = status_display


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    try:
        resp = requests.get(f"{API_BASE_URL}/exams", timeout=10)
        resp.raise_for_status()
        exams = resp.json()
        api_error = None
    except requests.RequestException:
        exams = []
        api_error = True

    return templates.TemplateResponse("index.html", {"request": request, "exams": exams, "api_error": api_error})


@app.get("/exams/{exam_id}", response_class=HTMLResponse)
def exam_detail(request: Request, exam_id: int):
    try:
        resp = requests.get(f"{API_BASE_URL}/exams/{exam_id}", timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Could not reach the API")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Exam not found")
    resp.raise_for_status()
    exam = resp.json()

    return templates.TemplateResponse("exam_detail.html", {"request": request, "exam": exam})
