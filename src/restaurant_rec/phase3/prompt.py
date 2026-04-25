"""Prompt rendering for the Groq call (Phase 3).

The shortlist is serialized as compact JSON so the model has unambiguous
field names; the system prompt locks the output contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from ..phase2.preferences import UserPreferences

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You are an expert restaurant recommender.

Rules:
- Recommend ONLY from the shortlist provided in the user message; never invent restaurants or fields.
- Use each restaurant's `id` exactly as given.
- Respect the user's min_rating and budget_max_inr; do not rank a venue that violates them.
- Cite concrete attributes (cuisine, rating, cost_for_two) when explaining a pick.
- Keep each explanation to one short paragraph (<=2 sentences).
- Output STRICT JSON matching this schema, with no prose, no markdown fences, no comments:
{
  "summary": "string",
  "recommendations": [
    {"restaurant_id": "string", "rank": 1, "explanation": "string"}
  ]
}
- `rank` starts at 1 and is contiguous.
- If the shortlist is empty, return {"summary": "...", "recommendations": []}.
"""


@dataclass
class RenderedPrompt:
    system: str
    user: str
    version: str = PROMPT_VERSION


def _shortlist_payload(shortlist: pd.DataFrame) -> list[dict]:
    """Project the shortlist down to LLM-relevant fields."""
    cols = ["id", "name", "locality", "cuisines", "rating", "cost_for_two", "votes", "raw_features"]
    df = shortlist[[c for c in cols if c in shortlist.columns]].copy()
    records: list[dict] = []
    for _, row in df.iterrows():
        rec = {
            "id": str(row.get("id")),
            "name": row.get("name"),
            "locality": row.get("locality"),
            "cuisines": list(row.get("cuisines") or []),
            "rating": _scalar(row.get("rating")),
            "cost_for_two": _scalar(row.get("cost_for_two")),
            "votes": _scalar(row.get("votes")),
        }
        feats = row.get("raw_features")
        if feats and not _is_na(feats):
            rec["features"] = str(feats)
        records.append(rec)
    return records


def _scalar(v):
    if v is None or _is_na(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def _is_na(v) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def render_prompt(
    prefs: UserPreferences,
    shortlist: pd.DataFrame,
    *,
    top_k: int = 5,
) -> RenderedPrompt:
    pref_summary = {
        "location": prefs.location,
        "cuisine": prefs.cuisine_list() or None,
        "min_rating": prefs.min_rating,
        "budget_max_inr": prefs.budget_max_inr,
        "extras": prefs.extras,
    }
    shortlist_records = _shortlist_payload(shortlist)
    user = (
        f"User preferences:\n{json.dumps(pref_summary, indent=2, default=str)}\n\n"
        f"Shortlist ({len(shortlist_records)} candidates):\n"
        f"{json.dumps(shortlist_records, indent=2, default=str)}\n\n"
        f"Return the top {min(top_k, max(len(shortlist_records), 1))} ranked picks "
        f"as JSON per the schema in the system message."
    )
    return RenderedPrompt(system=SYSTEM_PROMPT, user=user)
