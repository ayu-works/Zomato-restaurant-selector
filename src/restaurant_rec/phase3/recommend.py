"""End-to-end recommendation orchestration (Phase 3).

`recommend()` chains: load catalog -> filter (Phase 2) -> render prompt ->
call Groq -> parse -> heuristic fallback if parse empty -> merge LLM
ranks with catalog facts for display.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..config import AppConfig
from ..phase2 import (
    FilterResult,
    ReasonCode,
    UserPreferences,
    filter_restaurants,
    load_catalog,
)
from .groq_client import GroqAuthError, GroqCallError, call_groq
from .parser import LLMOutput, parse_llm_response
from .prompt import PROMPT_VERSION, render_prompt

log = logging.getLogger(__name__)

EMPTY_SUMMARY = (
    "No restaurants matched these preferences. Try widening the area, "
    "lowering the rating threshold, or raising the budget."
)


@dataclass
class RecommendationItem:
    id: str
    name: str
    cuisines: list[str]
    rating: float | None
    cost_for_two: float | None
    budget_tier: str | None
    locality: str | None
    rank: int
    explanation: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "cuisines": self.cuisines,
            "rating": self.rating,
            "estimated_cost": self.budget_tier,
            "cost_display": _cost_display(self.cost_for_two),
            "locality": self.locality,
            "explanation": self.explanation,
            "rank": self.rank,
        }


@dataclass
class RecommendationResult:
    summary: str
    items: list[RecommendationItem]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "items": [it.to_dict() for it in self.items],
            "meta": self.meta,
        }


def _cost_display(cost: float | None) -> str | None:
    if cost is None:
        return None
    return f"₹{int(cost)} for two"


def _heuristic_output(shortlist: pd.DataFrame, top_k: int) -> LLMOutput:
    """Fallback ranking when the LLM call fails or returns nothing usable."""
    from .parser import Recommendation

    head = shortlist.head(top_k)
    items = [
        Recommendation(
            restaurant_id=str(row["id"]),
            rank=i + 1,
            explanation=(
                f"Ranked by rating ({row.get('rating')}) and votes "
                f"({row.get('votes')}); cuisines: "
                f"{', '.join(row.get('cuisines') or [])}."
            ),
        )
        for i, (_, row) in enumerate(head.iterrows())
    ]
    return LLMOutput(
        summary="LLM unavailable; falling back to highest-rated picks from the shortlist.",
        recommendations=items,
    )


def _merge_with_catalog(
    output: LLMOutput, shortlist: pd.DataFrame
) -> list[RecommendationItem]:
    by_id = {str(row["id"]): row for _, row in shortlist.iterrows()}
    items: list[RecommendationItem] = []
    for rec in output.recommendations:
        row = by_id.get(rec.restaurant_id)
        if row is None:
            continue
        items.append(
            RecommendationItem(
                id=str(row["id"]),
                name=row.get("name") or "",
                cuisines=list(row.get("cuisines") or []),
                rating=_scalar(row.get("rating")),
                cost_for_two=_scalar(row.get("cost_for_two")),
                budget_tier=row.get("budget_tier"),
                locality=row.get("locality"),
                rank=rec.rank,
                explanation=rec.explanation,
            )
        )
    return items


def _scalar(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v.item() if hasattr(v, "item") else v


def _filter_summary(reason: ReasonCode, fr: FilterResult) -> str:
    msgs = {
        ReasonCode.NO_LOCATION: "No restaurants found for that location.",
        ReasonCode.NO_CUISINE: "No restaurants in that area match the requested cuisine.",
        ReasonCode.NO_RATING: "No restaurants in that area meet the minimum rating.",
        ReasonCode.NO_BUDGET: "No restaurants in that area fit the budget.",
    }
    base = msgs.get(reason, EMPTY_SUMMARY)
    if fr.relaxed_min_rating is not None:
        base += f" (Relaxed min_rating to {fr.relaxed_min_rating}.)"
    return base


def recommend(
    prefs: UserPreferences,
    config: AppConfig,
    *,
    catalog: pd.DataFrame | None = None,
) -> RecommendationResult:
    t0 = time.perf_counter()
    if catalog is None:
        catalog = load_catalog(config.paths.processed_catalog)

    fr = filter_restaurants(catalog, prefs, config.filter)

    meta: dict[str, Any] = {
        "shortlist_size": len(fr.shortlist),
        "model": config.llm.model,
        "prompt_version": PROMPT_VERSION,
        "filter_reason": fr.reason.value,
        "filter_stages": fr.stage_counts,
        "duration_filter_ms": fr.duration_ms,
    }
    if fr.relaxed_min_rating is not None:
        meta["relaxed_min_rating"] = fr.relaxed_min_rating

    if fr.is_empty:
        return RecommendationResult(
            summary=_filter_summary(fr.reason, fr),
            items=[],
            meta={**meta, "llm_called": False},
        )

    rendered = render_prompt(prefs, fr.shortlist, top_k=config.llm.top_k)

    t_llm = time.perf_counter()
    output: LLMOutput
    parse_method = "skipped"
    llm_called = False
    llm_error: str | None = None
    try:
        resp = call_groq(system=rendered.system, user=rendered.user, cfg=config.llm)
        llm_called = True
        allowed = {str(x) for x in fr.shortlist["id"].tolist()}
        parsed = parse_llm_response(resp.content, allowed_ids=allowed)
        output = parsed.output
        parse_method = parsed.method
        meta["llm_usage"] = resp.usage
        meta["llm_finish_reason"] = resp.finish_reason
        if not output.recommendations:
            log.info("LLM returned no usable recommendations; using heuristic fallback")
            output = _heuristic_output(fr.shortlist, config.llm.top_k)
            parse_method = parse_method + "+heuristic"
    except (GroqAuthError, GroqCallError) as e:
        log.warning("Groq call failed (%s); falling back to heuristic ranking", e)
        llm_error = str(e)
        output = _heuristic_output(fr.shortlist, config.llm.top_k)
        parse_method = "heuristic"

    meta["duration_llm_ms"] = (time.perf_counter() - t_llm) * 1000.0
    meta["parse_method"] = parse_method
    meta["llm_called"] = llm_called
    if llm_error:
        meta["llm_error"] = llm_error

    items = _merge_with_catalog(output, fr.shortlist)
    summary = output.summary or _default_summary(prefs, items)

    meta["duration_total_ms"] = (time.perf_counter() - t0) * 1000.0
    return RecommendationResult(summary=summary, items=items, meta=meta)


def _default_summary(prefs: UserPreferences, items: list[RecommendationItem]) -> str:
    cuisine = ", ".join(prefs.cuisine_list()) if prefs.cuisine_list() else "any cuisine"
    return (
        f"Top {len(items)} picks in {prefs.location} for {cuisine} "
        f"(min rating {prefs.min_rating})."
    )
