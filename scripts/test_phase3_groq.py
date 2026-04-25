"""Connectivity smoke tests for Phase 3 (Groq LLM).

Runs 3 scenarios:
  1. Healthy path  — real Groq call, strict-JSON output, items returned.
  2. Empty match   — preferences that yield zero shortlist; LLM must NOT be called.
  3. No-cuisine    — broad query (just location + min_rating); checks variety.

Run from repo root after `cp .env.example .env` and setting GROQ_API_KEY:

    python scripts/test_phase3_groq.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Force UTF-8 so ₹ etc. don't crash the Windows console.
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from restaurant_rec.config import AppConfig
from restaurant_rec.phase2 import UserPreferences
from restaurant_rec.phase3 import recommend


def banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def assert_(cond: bool, msg: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        raise SystemExit(1)


def test_healthy_path(cfg: AppConfig) -> None:
    banner("TEST 1: Healthy Groq call (Koramangala 5th Block, North Indian)")
    prefs = UserPreferences(
        location="Koramangala 5th Block",
        cuisine="North Indian",
        min_rating=4.0,
        budget_max_inr=1500,
    )
    res = recommend(prefs, cfg)
    meta = res.meta

    print(f"  summary: {res.summary[:120]}")
    print(f"  items returned: {len(res.items)}")
    print(f"  parse_method:   {meta.get('parse_method')}")
    print(f"  llm_called:     {meta.get('llm_called')}")
    print(f"  model:          {meta.get('model')}")
    print(f"  duration_llm_ms:{meta.get('duration_llm_ms'):.0f}")
    if meta.get("llm_usage"):
        u = meta["llm_usage"]
        print(f"  tokens:         prompt={u.get('prompt_tokens')} completion={u.get('completion_tokens')}")

    assert_(meta.get("llm_called") is True, "LLM was actually called (not fallback)")
    assert_(meta.get("parse_method", "").startswith("json"), "JSON parse path used")
    assert_(len(res.items) > 0, "At least one recommendation returned")
    assert_(all(it.id and it.name for it in res.items), "Every item has id and name")
    assert_(
        all(it.rank == i + 1 for i, it in enumerate(res.items)),
        "Ranks are contiguous starting at 1",
    )
    assert_(
        all(it.explanation and len(it.explanation) > 10 for it in res.items),
        "Every item has a non-trivial explanation",
    )

    print("\n  Sample picks:")
    for it in res.items[:3]:
        print(f"    #{it.rank} {it.name} ({it.locality}) - rating {it.rating}, ₹{int(it.cost_for_two) if it.cost_for_two else '?'} for two")


def test_empty_shortlist(cfg: AppConfig) -> None:
    banner("TEST 2: Empty shortlist short-circuits LLM (impossible cuisine)")
    prefs = UserPreferences(
        location="Koramangala 5th Block",
        cuisine="MartianFusion",   # guaranteed no match
        min_rating=4.0,
    )
    res = recommend(prefs, cfg)
    meta = res.meta

    print(f"  summary:       {res.summary}")
    print(f"  items:         {len(res.items)}")
    print(f"  llm_called:    {meta.get('llm_called')}")
    print(f"  filter_reason: {meta.get('filter_reason')}")

    assert_(len(res.items) == 0, "No items returned for impossible cuisine")
    assert_(meta.get("llm_called") is False, "LLM was NOT called (cost saved)")
    assert_(meta.get("filter_reason") == "NO_CUISINE", "Filter reason is NO_CUISINE")


def test_broad_query(cfg: AppConfig) -> None:
    banner("TEST 3: Broad query (Indiranagar, no cuisine pref, min_rating=4.5)")
    prefs = UserPreferences(
        location="Indiranagar",
        min_rating=4.5,
        budget_max_inr=2000,
        extras="good for a date night",
    )
    res = recommend(prefs, cfg)
    meta = res.meta

    print(f"  summary:        {res.summary[:140]}")
    print(f"  items:          {len(res.items)}")
    print(f"  shortlist_size: {meta.get('shortlist_size')}")
    print(f"  parse_method:   {meta.get('parse_method')}")

    assert_(meta.get("llm_called") is True, "LLM was called")
    assert_(meta.get("shortlist_size", 0) > 0, "Phase 2 produced a non-empty shortlist")
    assert_(len(res.items) > 0, "LLM produced at least one recommendation")
    assert_(
        len({it.id for it in res.items}) == len(res.items),
        "All recommended ids are unique",
    )

    print("\n  Picks:")
    for it in res.items:
        print(f"    #{it.rank} {it.name} - rating {it.rating}, ₹{int(it.cost_for_two) if it.cost_for_two else '?'} for two")


def main() -> int:
    if not os.environ.get("GROQ_API_KEY"):
        # Pre-import-time check: groq_client also calls load_dotenv(), but we
        # surface a friendlier error before running tests.
        from dotenv import load_dotenv
        load_dotenv()
        if not os.environ.get("GROQ_API_KEY"):
            print("ERROR: GROQ_API_KEY not set. Add it to .env in the repo root.")
            return 2

    cfg = AppConfig.load()
    test_healthy_path(cfg)
    test_empty_shortlist(cfg)
    test_broad_query(cfg)

    print("\n" + "=" * 72)
    print("All tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
