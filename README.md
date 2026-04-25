# AI-Powered Restaurant Recommendation System

Zomato-style restaurant recommender built in phases per
[`Docs/phase-wise-architecture.md`](Docs/phase-wise-architecture.md).

## Phase 1 — Catalog ingestion

Load the [`ManikaSaini/zomato-restaurant-recommendation`](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation)
dataset, normalize it to a canonical schema, and persist as a versioned
Parquet catalog consumed by later phases.

### Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e .
```

### Run ingestion

```bash
python scripts/ingest_zomato.py
```

Output: `data/processed/restaurants.parquet`. The command prints a JSON
summary: `rows_raw`, `rows_in`, `rows_out`, `drop_reasons`, `output_path`.

**Note on dataset scope.** `ManikaSaini/zomato-restaurant-recommendation`
is a Bangalore-only Zomato slice. The raw file has no city column; both
`location` and `listed_in(city)` hold neighbourhoods (e.g. `BTM`,
`Koramangala 5th Block`). Ingestion routes both to `locality` and fills
`city` from `dataset.default_city` in `config.yaml` (defaults to
`Bangalore`).

**Last reproducible run** (HF dataset revision at ingest time):

| Metric             | Value      |
| ------------------ | ---------- |
| Raw rows           | 51,717     |
| Kept rows          | 12,118     |
| Dropped            | 39,599     |
| `missing_cuisines` | 45         |
| `duplicate_id`     | 39,554 (1) |
| Distinct cities    | 1 (Bangalore) |
| Distinct localities | 30        |
| `rating` non-null  | 9,227      |
| `cost_for_two` non-null | 12,062 |

(1) The HF dump lists each venue once per `listed_in(type)` and
`listed_in(city)` neighbourhood; `id = sha1(name|city|locality)`
collapses these to one row per venue per neighbourhood.

Offline fallback (if HF download is blocked):

```bash
python scripts/ingest_zomato.py --input-csv data/raw/zomato.csv
```

### Canonical schema

| Field          | Type           | Notes                                              |
| -------------- | -------------- | -------------------------------------------------- |
| `id`           | string         | Stable — hashed from name+city+locality if absent |
| `name`         | string         | Required                                           |
| `city`         | string         | Normalized via `city_aliases` in `config.yaml`     |
| `locality`     | string         | Falls back to `city` when source is empty          |
| `address`      | string \| null | Optional                                           |
| `cuisines`     | list[string]   | Split on `|,/;`, title-cased                       |
| `rating`       | float \| null  | 0–5 scale; `"NEW"` / invalid → null              |
| `votes`        | int \| null    | Used for tie-breaking                              |
| `cost_for_two` | float \| null  | Parsed INR numeric                                 |
| `budget_tier`  | enum \| null   | `low` ≤ ₹500, `medium` ≤ ₹1200, `high` else    |
| `raw_features` | string \| null | Free-text hints (e.g. `"Casual Dining"`)           |

Thresholds live in [`config.yaml`](config.yaml).

#### Example row (JSON)

```json
{
  "id": "8aea4dccd6d1",
  "name": "Byg Brewski Brewing Company",
  "city": "Bangalore",
  "locality": "Sarjapur Road",
  "address": "Behind MK Retail, Sarjapur Road, Bangalore",
  "cuisines": ["Continental", "North Indian", "Italian", "South Indian", "Finger Food"],
  "rating": 4.9,
  "votes": 16832,
  "cost_for_two": 1600.0,
  "budget_tier": "high",
  "raw_features": "Microbrewery"
}
```

### Drop policy

A row is dropped (and counted under `drop_reasons`) when:

- `missing_name` — empty name
- `missing_location` — both city and locality empty
- `rating_out_of_range` — rating outside `[0, rating_scale_max]`
- `missing_cuisines` — empty cuisine list
- `duplicate_id` — same derived id as an already-kept row (the one with
  higher votes / rating wins)

## Phase 2 — Preferences & deterministic filter

Typed user preferences + a pipeline that shortlists candidates for the
LLM (Phase 3).

```python
from restaurant_rec.config import AppConfig
from restaurant_rec.phase2 import UserPreferences, filter_restaurants, load_catalog

cfg = AppConfig.load()
catalog = load_catalog(cfg.paths.processed_catalog)

prefs = UserPreferences(
    location="Bangalore",
    cuisine=["Italian", "Continental"],
    min_rating=4.0,
    budget_max_inr=1500,
    extras="family-friendly",
)

result = filter_restaurants(catalog, prefs, cfg.filter)
print(result.reason, len(result.shortlist), result.stage_counts)
```

**Pipeline order:** location → cuisine → rating → budget → rank
(`rating` desc, `votes` desc) → cap at `filter.max_shortlist_candidates`.

**Rating relaxation:** if the strict rating filter yields fewer than
`relax_min_matches` rows, `min_rating` is lowered once by
`rating_relax_step` (reported via `result.relaxed_min_rating`).

**Reason codes** (when `shortlist` is empty): `NO_LOCATION`,
`NO_CUISINE`, `NO_RATING`, `NO_BUDGET`, else `OK`.

## Phase 3 — LLM orchestration (Groq)

Renders a prompt from preferences + Phase 2 shortlist, calls Groq, parses
the JSON response, merges LLM ranks with catalog facts, and degrades
gracefully to a heuristic ranking if the call or parse fails.

### Setup

```bash
cp .env.example .env
# edit .env and set GROQ_API_KEY=<your key from console.groq.com>
```

`config.yaml -> llm` controls model, temperature, `max_tokens`, `top_k`,
`prompt_version`. Default model: `llama-3.3-70b-versatile`.

### Usage

```python
from restaurant_rec.config import AppConfig
from restaurant_rec.phase2 import UserPreferences
from restaurant_rec.phase3 import recommend

cfg = AppConfig.load()
prefs = UserPreferences(
    location="Koramangala 5th Block",
    cuisine="North Indian",
    min_rating=4.0,
    budget_max_inr=1500,
    extras="family-friendly",
)
result = recommend(prefs, cfg)
print(result.summary)
for item in result.items:
    print(f"#{item.rank} {item.name} - {item.explanation}")
```

`result.to_dict()` matches the Phase 4 API contract (`summary`, `items`,
`meta`). `meta` includes `shortlist_size`, `model`, `prompt_version`,
`parse_method` (`json` / `json_extracted` / `markdown` / `heuristic`),
`llm_usage`, `duration_filter_ms`, `duration_llm_ms`,
`duration_total_ms`.

### Robustness

- **JSON repair:** strict parse → largest `{...}` block → markdown
  numbered-list fallback.
- **Unknown ids:** any `restaurant_id` the LLM returns that isn't in the
  shortlist is dropped and ranks are renumbered contiguously (numeric
  facts are taken from the catalog row, not the LLM).
- **Empty shortlist:** Phase 2 reason codes drive a clear summary; the
  LLM is not called.
- **LLM failure:** auth/network/timeout falls back to a heuristic ranking
  (top-`top_k` by `rating` then `votes`) so the API still returns
  results.

## Phase 4 — Backend API + Web UI

FastAPI app with a tiny static frontend. End-to-end demo:

```bash
uvicorn restaurant_rec.phase4.app:app --reload
# open http://127.0.0.1:8000/         (UI)
# open http://127.0.0.1:8000/docs     (Swagger)
```

Endpoints:

| Method | Path                | Purpose                                 |
| ------ | ------------------- | --------------------------------------- |
| GET    | `/`                 | Web UI (`web/index.html`)               |
| GET    | `/static/*`         | UI assets                               |
| GET    | `/api/v1/health`    | Liveness + catalog row count + model    |
| GET    | `/api/v1/locations` | Distinct cities                         |
| GET    | `/api/v1/localities`| Distinct localities (UI dropdown source)|
| POST   | `/api/v1/recommend` | Body = `UserPreferences` → `{summary, items, meta}` |

Backend contract tests (TestClient — no live server needed):

```bash
python scripts/test_phase4_api.py
```

## Deploy

### Streamlit Community Cloud (single-deployment demo)

```bash
# local smoke test
pip install -r requirements.txt
streamlit run streamlit_app.py
# open http://localhost:8501
```

On Streamlit Cloud:

1. **New app** → repo `ayu-works/Zomato-restaurant-selector` → branch `main` →
   main file `streamlit_app.py`.
2. **Settings → Secrets** →
   ```toml
   GROQ_API_KEY = "gsk_xxx"
   ```
3. Deploy. The catalog parquet (`data/processed/restaurants.parquet`, ~750 KB)
   is shipped in the repo, so no ingestion happens on the cloud host.

Files involved: `streamlit_app.py`, `requirements.txt`, `runtime.txt` (pins
Python 3.11), `.streamlit/config.toml` (theme), `.streamlit/secrets.toml.example`.

See `Docs/phase-wise-architecture.md` §6 for Topology B (Vercel frontend + REST
backend on Render / Railway / Fly.io / Hugging Face Spaces).

### Project layout

```
config.yaml
pyproject.toml
scripts/ingest_zomato.py
src/restaurant_rec/
  config.py
  phase1/
    schema.py        # canonical columns + raw->canonical map
    transform.py     # parsing & normalization
    validate.py      # row checks, dedup, drop-reason report
    ingest.py        # pipeline + CLI entrypoint
  phase2/
    preferences.py   # UserPreferences (Pydantic)
    catalog_loader.py# cached parquet loader
    filter.py        # filter_restaurants + FilterResult + ReasonCode
  phase3/
    prompt.py        # system+user prompt rendering
    groq_client.py   # Groq SDK wrapper, .env loading
    parser.py        # JSON parse + repair + markdown fallback
    recommend.py     # recommend() orchestration + heuristic fallback
  phase4/
    app.py           # FastAPI app: /api/v1/* + static UI mount
web/                 # vanilla zero-build UI (served at / by FastAPI)
  index.html
  styles.css
  app.js
web-next/            # Next.js 14 + Tailwind UI modeled after design/ mocks
  app/page.tsx
  components/        # Header, RefineSidebar, QueryBar, RestaurantCard, RefineInput
  lib/               # api.ts, types.ts
  next.config.mjs    # rewrites /api/* -> http://127.0.0.1:8000/api/*
data/
  raw/               # optional snapshots
  processed/         # restaurants.parquet (generated)
```
