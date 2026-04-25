"""Transformations from raw HF rows to the canonical schema."""
from __future__ import annotations

import hashlib
import re
from typing import Any

import pandas as pd

from .schema import CANONICAL_COLUMNS, RAW_TO_CANONICAL

_CUISINE_SEP = re.compile(r"[|,/;]")


def _is_na(value) -> bool:
    """Robust NA check that handles pd.NA, np.nan, NaT, etc."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False
_COST_CLEAN = re.compile(r"[^\d.]")
_RATING_CLEAN = re.compile(r"[^\d.]")


def rename_to_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known raw columns to canonical names; drop unknown ones later."""
    mapping: dict[str, str] = {}
    for col in df.columns:
        key = col.strip().lower()
        canonical = RAW_TO_CANONICAL.get(key)
        if canonical and canonical not in mapping.values():
            mapping[col] = canonical
    return df.rename(columns=mapping)


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee every canonical column is present; fill missing with NA."""
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    return df[CANONICAL_COLUMNS]


def parse_cuisines(value: Any) -> list[str]:
    if value is None or _is_na(value):
        return []
    if isinstance(value, list):
        items = value
    else:
        items = _CUISINE_SEP.split(str(value))
    cleaned = [s.strip() for s in items if s and str(s).strip()]
    # case-normalize but keep human-readable
    return [s.title() for s in cleaned]


def parse_rating(value: Any, scale_max: float = 5.0) -> float | None:
    if value is None or _is_na(value):
        return None
    s = str(value).strip()
    if not s or s.upper() in {"NEW", "-", "N/A", "NA"}:
        return None
    # strip "/5" suffixes etc.
    if "/" in s:
        s = s.split("/")[0]
    s = _RATING_CLEAN.sub("", s)
    if not s:
        return None
    try:
        r = float(s)
    except ValueError:
        return None
    if r < 0 or r > scale_max + 0.01:
        return None
    return round(r, 2)


def parse_cost(value: Any) -> float | None:
    if value is None or _is_na(value):
        return None
    s = _COST_CLEAN.sub("", str(value))
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_votes(value: Any) -> int | None:
    if value is None or _is_na(value):
        return None
    s = re.sub(r"[^\d]", "", str(value))
    return int(s) if s else None


def normalize_city(value: Any, aliases: dict[str, str]) -> str | None:
    if value is None or _is_na(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.title()
    return aliases.get(s, s)


def normalize_text(value: Any) -> str | None:
    if value is None or _is_na(value):
        return None
    s = str(value).strip()
    return s or None


def compute_budget_tier(cost: float | None, tiers: dict[str, int]) -> str | None:
    if cost is None:
        return None
    low_max = tiers.get("low_max_inr", 500)
    med_max = tiers.get("medium_max_inr", 1200)
    if cost <= low_max:
        return "low"
    if cost <= med_max:
        return "medium"
    return "high"


def derive_id(name: str | None, city: str | None, locality: str | None) -> str:
    """Stable short hash used when the dataset lacks an id."""
    key = f"{name or ''}|{city or ''}|{locality or ''}".lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def transform_frame(
    df: pd.DataFrame,
    *,
    city_aliases: dict[str, str],
    rating_scale_max: float,
    budget_tiers: dict[str, int],
    default_city: str | None = None,
) -> pd.DataFrame:
    df = rename_to_canonical(df)
    df = ensure_columns(df).copy()

    df["name"] = df["name"].map(normalize_text)
    df["city"] = df["city"].map(lambda v: normalize_city(v, city_aliases))
    if default_city:
        df["city"] = df["city"].fillna(default_city)
        df.loc[df["city"].astype(str).str.strip() == "", "city"] = default_city
    df["locality"] = df["locality"].map(normalize_text)
    df["address"] = df["address"].map(normalize_text)
    df["cuisines"] = df["cuisines"].map(parse_cuisines)
    df["rating"] = df["rating"].map(lambda v: parse_rating(v, rating_scale_max))
    df["votes"] = df["votes"].map(parse_votes)
    df["cost_for_two"] = df["cost_for_two"].map(parse_cost)
    df["raw_features"] = df["raw_features"].map(normalize_text)
    df["budget_tier"] = df["cost_for_two"].map(
        lambda c: compute_budget_tier(c, budget_tiers)
    )

    # If locality missing but city present, fall back to city (UI "area" field).
    df["locality"] = df["locality"].where(df["locality"].notna(), df["city"])
    df["locality"] = df["locality"].map(normalize_text)

    # Derive id where missing.
    needs_id = df["id"].isna() | (df["id"].astype(str).str.strip() == "")
    df.loc[needs_id, "id"] = df.loc[needs_id].apply(
        lambda r: derive_id(r["name"], r["city"], r["locality"]), axis=1
    )
    df["id"] = df["id"].astype(str)

    return df
