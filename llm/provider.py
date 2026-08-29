"""
Provider-agnostic LLM calls (2026-08-27, "allow me to use any model...
sometimes use local or sometimes other to save on the cost" -- cloud-only
for now). Reads which provider/model/key is active from llm.config
(Settings-page-editable, stored in Postgres) and dispatches to the right
SDK. extraction/extractor.py and integrity/search.py call through here
instead of instantiating a provider client directly, so switching
providers in Settings changes both without either module knowing which
provider is actually running.

Two capabilities, matching what those two callers actually need:
- extract_structured(): text OR PDF (vision) in, a validated Pydantic
  instance out. Anthropic via client.messages.parse(output_format=...);
  OpenAI via client.responses.parse(text_format=...) -- verified against
  OpenAI's current docs 2026-08-27, not assumed from training data, since
  this skill only covers Anthropic and the Responses API shape has moved
  since these models were trained.
- search_web(): a web-search-enabled call, returns raw final text (the
  caller parses it, e.g. as JSON) -- Anthropic's web_search_20260209
  server tool vs. OpenAI's web_search tool on the Responses API.
"""

from __future__ import annotations

import base64
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from llm.config import ActiveLLMConfig, get_active_config

T = TypeVar("T", bound=BaseModel)


def extract_structured(
    *,
    system_prompt: str,
    schema: Type[T],
    user_text: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
) -> T:
    """Exactly one of user_text/pdf_bytes must be given."""
    if (user_text is None) == (pdf_bytes is None):
        raise ValueError("extract_structured needs exactly one of user_text or pdf_bytes")

    cfg = get_active_config()
    if cfg.provider == "openai":
        return _extract_openai(cfg, system_prompt, user_text, pdf_bytes, schema)
    return _extract_anthropic(cfg, system_prompt, user_text, pdf_bytes, schema)


def search_web(*, system_prompt: str, query: str) -> str:
    cfg = get_active_config()
    if cfg.provider == "openai":
        return _search_openai(cfg, query, system_prompt)
    return _search_anthropic(cfg, system_prompt, query)


# --- Anthropic ---------------------------------------------------------


def _anthropic_client(cfg: ActiveLLMConfig):
    import anthropic

    return anthropic.Anthropic(api_key=cfg.api_key) if cfg.api_key else anthropic.Anthropic()


def _extract_anthropic(cfg, system_prompt, user_text, pdf_bytes, schema):
    client = _anthropic_client(cfg)

    if pdf_bytes is not None:
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        content = [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
            {"type": "text", "text": "Read this document -- it may be a scanned image -- and structure it."},
        ]
    else:
        content = user_text

    response = client.messages.parse(
        model=cfg.model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
        output_format=schema,
    )
    return response.parsed_output


def _search_anthropic(cfg, system_prompt, query):
    client = _anthropic_client(cfg)
    response = client.messages.create(
        model=cfg.model,
        max_tokens=4096,
        system=system_prompt,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": query}],
    )
    text_blocks = [b.text for b in response.content if b.type == "text"]
    return text_blocks[-1] if text_blocks else ""


# --- OpenAI --------------------------------------------------------------


def _openai_client(cfg: ActiveLLMConfig):
    from openai import OpenAI

    return OpenAI(api_key=cfg.api_key) if cfg.api_key else OpenAI()


def _extract_openai(cfg, system_prompt, user_text, pdf_bytes, schema):
    client = _openai_client(cfg)

    if pdf_bytes is not None:
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        content = [
            {"type": "input_file", "filename": "notice.pdf", "file_data": f"data:application/pdf;base64,{pdf_b64}"},
            {"type": "input_text", "text": "Read this document -- it may be a scanned image -- and structure it."},
        ]
    else:
        content = [{"type": "input_text", "text": user_text}]

    response = client.responses.parse(
        model=cfg.model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        text_format=schema,
    )
    return response.output_parsed


def _search_openai(cfg, query, system_prompt):
    client = _openai_client(cfg)
    response = client.responses.create(
        model=cfg.model,
        tools=[{"type": "web_search"}],
        input=f"{system_prompt}\n\n{query}",
    )
    return response.output_text
