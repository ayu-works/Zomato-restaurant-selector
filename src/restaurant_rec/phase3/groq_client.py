"""Thin Groq SDK wrapper for the Phase 3 LLM call."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

from ..config import LLMCfg

log = logging.getLogger(__name__)

# Load .env from cwd / repo root once at import time.
load_dotenv()


class GroqAuthError(RuntimeError):
    pass


class GroqCallError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


def _client():
    try:
        from groq import Groq  # type: ignore
    except ImportError as e:
        raise GroqCallError(
            "The 'groq' package is required. Install with `pip install -e .`."
        ) from e

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise GroqAuthError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return Groq(api_key=api_key)


def call_groq(
    *,
    system: str,
    user: str,
    cfg: LLMCfg,
    json_mode: bool = True,
) -> LLMResponse:
    client = _client()
    log.info(
        "groq call model=%s temp=%s max_tokens=%s json_mode=%s",
        cfg.model, cfg.temperature, cfg.max_tokens, json_mode,
    )
    kwargs: dict = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "timeout": cfg.timeout_s,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:  # SDK raises various subtypes; surface uniformly
        raise GroqCallError(f"Groq API call failed: {e}") from e

    choice = resp.choices[0]
    return LLMResponse(
        content=choice.message.content or "",
        model=resp.model,
        usage=getattr(resp, "usage", None) and resp.usage.model_dump(),
        finish_reason=choice.finish_reason,
    )
