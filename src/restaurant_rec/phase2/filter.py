"""Deterministic filtering pipeline (Phase 2).

Order: location → cuisine → rating → budget → rank+cap.
Returns a FilterResult with reason codes when the pipeline empties out,
so the UI can show specific messages.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from ..config import FilterCfg
from .preferences import UserPreferences

log = logging.getLogger(__name__)


class ReasonCode(str, Enum):
    OK = "OK"
    NO_LOCATION = "NO_LOCATION"
    NO_CUISINE = "NO_CUISINE"
    NO_RATING = "NO_RATING"
    NO_BUDGET = "NO_BUDGET"


@dataclass
class FilterResult:
    shortlist: pd.DataFrame
    reason: ReasonCode = ReasonCode.OK
    relaxed_min_rating: float | None = None
    stage_counts: dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0

    @property
    def is_empty(self) -> bool:
        return len(self.shortlist) == 0


def _filter_location(df: pd.DataFrame, location: str) -> pd.DataFrame:
    loc = location.strip().lower()
    if not loc:
        return df
    city = df["city"].fillna("").str.lower()
    locality = df["locality"].fillna("").str.lower()
    return df[(city == loc) | (locality == loc) | city.str.contains(loc, na=False) | locality.str.contains(loc, na=False)]


def _filter_cuisines(df: pd.DataFrame, cuisines: list[str]) -> pd.DataFrame:
    if not cuisines:
        return df
    wanted = {c.strip().lower() for c in cuisines if c.strip()}
    if not wanted:
        return df

    def has_match(row_cuisines) -> bool:
        if not isinstance(row_cuisines, (list, tuple)):
            return False
        lowered = {str(c).strip().lower() for c in row_cuisines}
        if wanted & lowered:
            return True
        # substring/token fallback: "Biryani" should match "North Indian, Biryani"
        joined = " ".join(lowered)
        return any(w in joined for w in wanted)

    return df[df["cuisines"].map(has_match)]


def _filter_rating(df: pd.DataFrame, min_rating: float) -> pd.DataFrame:
    if min_rating <= 0:
        return df
    return df[df["rating"].fillna(-1) >= min_rating]


def _filter_budget(df: pd.DataFrame, budget_max_inr: float | None) -> pd.DataFrame:
    if budget_max_inr is None:
        return df
    # Keep rows with known cost_for_two <= budget_max_inr (unknown cost dropped).
    return df[df["cost_for_two"].notna() & (df["cost_for_two"] <= budget_max_inr)]


def _rank_and_cap(df: pd.DataFrame, cap: int) -> pd.DataFrame:
    if df.empty:
        return df
    return (
        df.sort_values(
            by=["rating", "votes"],
            ascending=[False, False],
            na_position="last",
        )
        .head(cap)
        .reset_index(drop=True)
    )


def filter_restaurants(
    catalog: pd.DataFrame,
    prefs: UserPreferences,
    cfg: FilterCfg | None = None,
) -> FilterResult:
    cfg = cfg or FilterCfg()
    t0 = time.perf_counter()
    stages: dict[str, int] = {"catalog": len(catalog)}

    df = _filter_location(catalog, prefs.location)
    stages["after_location"] = len(df)
    if df.empty:
        return _done(df, ReasonCode.NO_LOCATION, stages, t0)

    df = _filter_cuisines(df, prefs.cuisine_list())
    stages["after_cuisine"] = len(df)
    if df.empty:
        return _done(df, ReasonCode.NO_CUISINE, stages, t0)

    relaxed_min: float | None = None
    rated = _filter_rating(df, prefs.min_rating)
    stages["after_rating"] = len(rated)
    if len(rated) < cfg.relax_min_matches and prefs.min_rating > 0:
        fallback_min = max(0.0, prefs.min_rating - cfg.rating_relax_step)
        relaxed = _filter_rating(df, fallback_min)
        if len(relaxed) > len(rated):
            log.info(
                "Relaxing min_rating %.2f → %.2f (matches %d → %d)",
                prefs.min_rating, fallback_min, len(rated), len(relaxed),
            )
            rated = relaxed
            relaxed_min = fallback_min
            stages["after_rating_relaxed"] = len(rated)

    df = rated
    if df.empty:
        return _done(df, ReasonCode.NO_RATING, stages, t0, relaxed_min=relaxed_min)

    df = _filter_budget(df, prefs.budget_max_inr)
    stages["after_budget"] = len(df)
    if df.empty:
        return _done(df, ReasonCode.NO_BUDGET, stages, t0, relaxed_min=relaxed_min)

    short = _rank_and_cap(df, cfg.max_shortlist_candidates)
    stages["shortlist"] = len(short)
    return _done(short, ReasonCode.OK, stages, t0, relaxed_min=relaxed_min)


def _done(
    df: pd.DataFrame,
    reason: ReasonCode,
    stages: dict[str, int],
    t0: float,
    relaxed_min: float | None = None,
) -> FilterResult:
    duration_ms = (time.perf_counter() - t0) * 1000.0
    log.info(
        "filter_restaurants reason=%s duration_ms=%.2f stages=%s",
        reason.value, duration_ms, stages,
    )
    return FilterResult(
        shortlist=df.reset_index(drop=True) if not df.empty else df,
        reason=reason,
        relaxed_min_rating=relaxed_min,
        stage_counts=stages,
        duration_ms=duration_ms,
    )
