"""
Reads/writes the singleton LLM provider settings row (2026-08-27, admin
Settings page's "use any model / store the api key" request). One active
provider+model at a time, applied to both extraction and integrity search.
Local models are explicitly out of scope for now (2026-08-27, "do not do
local for now") -- cloud providers only: Anthropic (default, unchanged
behavior) and OpenAI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from db.connection import get_connection

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"


@dataclass
class ActiveLLMConfig:
    provider: str
    model: str
    api_key: Optional[str]  # None means "fall back to the provider SDK's own env-var resolution"


def _ensure_row(conn):
    conn.execute(
        """
        INSERT INTO llm_settings (id, active_provider, anthropic_model, openai_model)
        VALUES (1, 'anthropic', %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (DEFAULT_ANTHROPIC_MODEL, DEFAULT_OPENAI_MODEL),
    )


def get_settings() -> dict:
    with get_connection() as conn:
        _ensure_row(conn)
        return dict(conn.execute("SELECT * FROM llm_settings WHERE id = 1").fetchone())


def save_settings(
    active_provider: str,
    anthropic_model: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_model: Optional[str] = None,
    openai_api_key: Optional[str] = None,
) -> None:
    """Only overwrites a key/model field when a real non-empty value was
    submitted -- switching providers shouldn't force re-pasting a key
    that's already saved. Keys are never read back into the Settings form,
    same reason they're never echoed anywhere else in this admin."""
    updates: dict = {"active_provider": active_provider}
    if anthropic_model:
        updates["anthropic_model"] = anthropic_model
    if openai_model:
        updates["openai_model"] = openai_model
    if anthropic_api_key:
        updates["anthropic_api_key"] = anthropic_api_key
    if openai_api_key:
        updates["openai_api_key"] = openai_api_key

    with get_connection() as conn:
        _ensure_row(conn)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        conn.execute(f"UPDATE llm_settings SET {set_clause}, updated_at = now() WHERE id = 1", list(updates.values()))


def get_active_config() -> ActiveLLMConfig:
    s = get_settings()
    if s["active_provider"] == "openai":
        return ActiveLLMConfig(provider="openai", model=s["openai_model"], api_key=s.get("openai_api_key"))
    return ActiveLLMConfig(provider="anthropic", model=s["anthropic_model"], api_key=s.get("anthropic_api_key"))
