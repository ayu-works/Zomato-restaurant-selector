"""Phase 4 backend contract tests.

Three cases via FastAPI's TestClient (no live server needed):
  1. Healthy POST /api/v1/recommend (real Groq call)
  2. Validation 422 on missing required `location`
  3. Empty filter outcome returns 200 + empty items + reason summary

Run:  python scripts/test_phase4_api.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

from fastapi.testclient import TestClient

from restaurant_rec.phase4.app import app

client = TestClient(app)


def banner(t: str) -> None:
    print("\n" + "=" * 72 + f"\n{t}\n" + "=" * 72)


def assert_(cond: bool, msg: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        raise SystemExit(1)


def test_health_and_lookups() -> None:
    banner("TEST 0: /health + /localities sanity")
    h = client.get("/api/v1/health").json()
    print(f"  health: {h}")
    assert_(h["status"] == "ok", "health endpoint reports ok")
    assert_(h["catalog_rows"] > 0, "catalog has rows")

    locs = client.get("/api/v1/localities").json()
    assert_(len(locs["localities"]) > 0, "localities returned")
    assert_("Koramangala 5th Block" in locs["localities"], "expected locality present")


def test_healthy_recommend() -> None:
    banner("TEST 1: POST /api/v1/recommend — happy path (Groq)")
    body = {
        "location": "Koramangala 5th Block",
        "cuisine": "North Indian",
        "min_rating": 4.0,
        "budget_max_inr": 1500,
    }
    r = client.post("/api/v1/recommend", json=body)
    print(f"  HTTP {r.status_code}")
    data = r.json()
    print(f"  summary: {data['summary'][:120]}")
    print(f"  items:   {len(data['items'])}")
    print(f"  meta:    model={data['meta'].get('model')} parse={data['meta'].get('parse_method')} llm_called={data['meta'].get('llm_called')}")
    for it in data["items"][:2]:
        print(f"    #{it['rank']} {it['name']} - rating {it['rating']} {it['cost_display']}")

    assert_(r.status_code == 200, "200 OK")
    assert_("summary" in data and "items" in data and "meta" in data, "envelope keys present")
    assert_(len(data["items"]) > 0, "at least one item")
    assert_(data["meta"]["llm_called"] is True, "LLM was actually called")
    for it in data["items"]:
        assert_(
            all(k in it for k in ("id", "name", "cuisines", "rating", "estimated_cost", "cost_display", "explanation", "rank")),
            f"item #{it.get('rank')} has all UI fields",
        )


def test_validation_422() -> None:
    banner("TEST 2: POST /api/v1/recommend — validation error")
    # Missing required `location`
    r = client.post("/api/v1/recommend", json={"cuisine": "Italian", "min_rating": 4.0})
    print(f"  HTTP {r.status_code}")
    print(f"  body: {r.json()}")
    assert_(r.status_code == 422, "422 Unprocessable Entity")
    detail = r.json().get("detail", [])
    assert_(any("location" in (".".join(map(str, e.get("loc", [])))) for e in detail), "error cites `location` field")


def test_empty_filter() -> None:
    banner("TEST 3: POST /api/v1/recommend — empty filter (NO_CUISINE)")
    body = {
        "location": "Koramangala 5th Block",
        "cuisine": "MartianFusion",
        "min_rating": 4.0,
    }
    r = client.post("/api/v1/recommend", json=body)
    data = r.json()
    print(f"  HTTP {r.status_code}")
    print(f"  summary:       {data['summary']}")
    print(f"  items:         {len(data['items'])}")
    print(f"  filter_reason: {data['meta'].get('filter_reason')}")
    print(f"  llm_called:    {data['meta'].get('llm_called')}")
    assert_(r.status_code == 200, "200 OK even when empty (per exit criteria)")
    assert_(len(data["items"]) == 0, "items is empty")
    assert_(data["meta"]["filter_reason"] == "NO_CUISINE", "reason is NO_CUISINE")
    assert_(data["meta"]["llm_called"] is False, "LLM was NOT called (cost saved)")


def main() -> int:
    test_health_and_lookups()
    test_healthy_recommend()
    test_validation_422()
    test_empty_filter()
    print("\n" + "=" * 72 + "\nAll Phase 4 backend tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
