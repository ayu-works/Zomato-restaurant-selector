"""Parse and validate the LLM response (Phase 3).

Order of attempts:
1. Strict JSON parse (Groq JSON mode usually returns clean JSON).
2. Extract the largest {...} block and re-parse.
3. Markdown numbered-list fallback ("1. <id> - explanation").
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger(__name__)

_NUMBERED = re.compile(r"^\s*(\d+)[.)]\s*([\w\-]+)\s*[-:]\s*(.+)$", re.MULTILINE)
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class Recommendation(BaseModel):
    restaurant_id: str = Field(..., min_length=1)
    rank: int = Field(..., ge=1)
    explanation: str = Field(default="")


class LLMOutput(BaseModel):
    summary: str = ""
    recommendations: list[Recommendation] = Field(default_factory=list)


@dataclass
class ParseResult:
    output: LLMOutput
    method: str  # "json", "json_extracted", "markdown", "empty"
    raw: str


def parse_llm_response(text: str, *, allowed_ids: set[str] | None = None) -> ParseResult:
    """Parse the LLM response, falling back through repair strategies."""
    raw = text or ""
    if not raw.strip():
        return ParseResult(LLMOutput(), method="empty", raw=raw)

    # 1. strict JSON
    parsed = _try_json(raw)
    if parsed is not None:
        return _finalize(parsed, "json", raw, allowed_ids)

    # 2. extract first/largest JSON block
    m = _JSON_BLOCK.search(raw)
    if m:
        parsed = _try_json(m.group(0))
        if parsed is not None:
            return _finalize(parsed, "json_extracted", raw, allowed_ids)

    # 3. markdown numbered list fallback
    items: list[Recommendation] = []
    for match in _NUMBERED.finditer(raw):
        rank, rid, explanation = match.groups()
        try:
            items.append(
                Recommendation(
                    restaurant_id=rid.strip(),
                    rank=int(rank),
                    explanation=explanation.strip(),
                )
            )
        except ValidationError:
            continue
    if items:
        out = LLMOutput(summary="", recommendations=items)
        return _finalize(out.model_dump(), "markdown", raw, allowed_ids)

    log.warning("LLM response could not be parsed; returning empty output")
    return ParseResult(LLMOutput(), method="empty", raw=raw)


def _try_json(s: str) -> dict | None:
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        return None


def _finalize(
    data: dict,
    method: str,
    raw: str,
    allowed_ids: set[str] | None,
) -> ParseResult:
    try:
        out = LLMOutput.model_validate(data)
    except ValidationError as e:
        log.warning("LLM output failed schema validation: %s", e)
        out = LLMOutput()

    if allowed_ids is not None and out.recommendations:
        kept = [r for r in out.recommendations if r.restaurant_id in allowed_ids]
        dropped = len(out.recommendations) - len(kept)
        if dropped:
            log.warning("Dropped %d LLM recommendation(s) with unknown ids", dropped)
        # re-rank contiguously
        for new_rank, rec in enumerate(kept, start=1):
            rec.rank = new_rank
        out.recommendations = kept

    return ParseResult(out, method=method, raw=raw)
