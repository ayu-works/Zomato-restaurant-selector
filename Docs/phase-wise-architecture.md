**Phase-Wise Architecture: AI-Powered Restaurant Recommendation System

This document expands the build plan for the Zomato-style recommendation service described in [problemStatement.md](about:blank). Each phase lists objectives, components, interfaces, data artifacts, and exit criteria.

---

System context

Purpose: Combine a real restaurant dataset with user preferences and an LLM to produce ranked recommendations with natural-language explanations.

High-level flow:

1. Offline or on-demand: load and normalize restaurant records.
2. Online: accept preferences → filter catalog to a shortlist → prompt Groq (Phase 3) → return structured UI payload.

Non-goals (unless you add them later): user accounts, live Zomato scraping, training custom embedding models.

---

Phase 1 — Foundation, dataset contract, and catalog

1.1 Objectives

* Establish a single source of truth for restaurant data after Hugging Face ingest.
* Define a canonical schema so filtering, prompting, and UI do not depend on raw column names.
* Make ingestion repeatable (same command → same artifact).

1.2 Dataset source

* Primary:[ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) via datasets library or export script.

1.3 Canonical schema (recommended fields)

Map HF columns to internal names (exact mapping depends on dataset columns; validate after first load):

| Internal field            | Role                                                                                                   |
| ------------------------- | ------------------------------------------------------------------------------------------------------ |
| id                        | Stable string or hash (if missing, derive from name+location)                                          |
| name                      | Restaurant name                                                                                        |
| location/city             | For location filter (normalize: trim, title case, alias map e.g. "Bengaluru" → "Bangalore" if needed) |
| cuisines                  | List of strings or single pipe/comma-separated field parsed to list                                    |
| rating                    | Float 0–5 (or dataset scale; document and normalize)                                                  |
| cost_for_twoorapprox_cost | Numeric or categorical; derivebudget_tier:low                                                          |
| votes/review_count        | Optional; use for tie-breaking in shortlist                                                            |
| addressorlocality         | Optional; richer prompts and UI                                                                        |
| raw_features              | Optional blob for “family-friendly” style hints if present in text columns                           |

1.4 Components

| Component        | Responsibility                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| Ingestion script | Download/load split, select columns, rename to canonical schema                                         |
| Validators       | Row-level checks (rating range, required name/location), quarantine or drop bad rows with counts logged |
| Transformers     | Parse cuisines, normalize city, computebudget_tierfrom rules (e.g. quantiles or fixed thresholds)       |
| Catalog store    | Versioned file: Parquet (preferred), SQLite, or JSON Lines for small prototypes                         |

Implementation lives under restaurant_rec.phase1 (ingest, transform, validate, schema) and scripts/ingest_zomato.py.

1.5 Artifacts and layout (suggested)

data/

  raw/              # optional: snapshot of downloaded slice

  processed/

    restaurants.parquet   # or restaurants.db

scripts/

  ingest_zomato.py   # or notebooks/01_ingest.ipynb for exploration-only phase

src/restaurant_rec/

  config.py          # shared: AppConfig, paths, dataset + filter tuning

  phase1/            # catalog ingest + schema

  phase2/            # preferences, load catalog, deterministic filter

  phase3/            # Groq prompts, JSON parse, `recommend()` orchestration

1.6 Configuration

* Path to catalog file, encoding, and threshold constants (rating scale, budget cutoffs) in config.yaml or environment variables.

1.7 Exit criteria

* Documented schema with example row (JSON).
* One command reproduces processed/restaurants.* from HF.
* Documented row counts before/after cleaning and top reasons for drops.

---

Phase 2 — Preference model and deterministic filtering

2.1 Objectives

* Convert user input into a typed preference object.
* Produce a bounded shortlist (e.g. 20–50 venues) that is small enough for one LLM call but diverse enough to rank.

2.2 Preference model (API / domain)

Structured input (align with problem statement):

| Field      | Type              | Notes                                                                                            |
| ---------- | ----------------- | ------------------------------------------------------------------------------------------------ |
| location   | string            | Required for first version; fuzzy match optional later                                           |
| budget     | enum              | low                                                                                              |
| cuisine    | string or list    | Match againstcuisines(substring or token match)                                                  |
| min_rating | float             | Hard filter:rating >= min_rating                                                                 |
| extras     | string (optional) | Free text: “family-friendly”, “quick service”; used in LLM prompt and optional keyword boost |

Optional extensions: max_results_shortlist, dietary, neighborhood.

2.3 Filtering pipeline (order matters)

1. Location filter: Exact or normalized match on city / location.
2. Cuisine filter: At least one cuisine matches user selection (case-insensitive).
3. Rating filter:rating >= min_rating; if too few results, optional relax step (document policy: e.g. lower min by 0.5 once).
4. Budget filter: Match budget_tier to user budget.
5. Ranking for shortlist: Sort by rating desc, then votes desc; take top N.

2.4 Component boundaries

| Module (package path)                | Responsibility                                        |
| ------------------------------------ | ----------------------------------------------------- |
| restaurant_rec.phase2.preferences    | Pydantic validation, defaults (UserPreferences)       |
| restaurant_rec.phase2.filter         | filter_restaurants(catalog_df, prefs) -> FilterResult |
| restaurant_rec.phase2.catalog_loader | Load Parquet into a DataFrame at startup              |

2.5 Edge cases

* Zero matches: Return empty shortlist with reason codes (NO_LOCATION, NO_CUISINE, etc.) for UI messaging.
* Missing rating/cost: Exclude from strict filters or treat as unknown with explicit rules in docs.

2.6 Exit criteria

* Unit tests for filter combinations and empty results.
* Shortlist size and latency predictable (log timing for 100k rows if applicable).

---

Phase 3 — LLM integration: prompt contract and orchestration

**LLM choice (decided): Groq.** Phase 3 uses Groq (GroqCloud / Groq API) as the LLM provider for ranking, explanations, and optional summaries. The Groq API key (`GROQ_API_KEY`) is loaded at runtime from a `.env` file in the project root via `python-dotenv` (see §3.6). `.env` must be git-ignored; only `.env.example` is committed. No other LLM provider is in scope for this phase.

3.1 Objectives

* Given preferences + shortlist JSON, produce ordered recommendations with per-item explanations and optional overall summary.
* Keep behavior testable (template version, structured output where possible).
* Call Groq over HTTP with the official Groq Python SDK or OpenAI-compatible client pointed at Groq’s base URL, using credentials supplied via environment variables populated from .env.

3.2 Inputs to the LLM

* System message: Role (expert recommender), constraints (only recommend from provided list; respect min rating and budget; if list empty, say so).
* User message: Serialized shortlist (compact JSON or markdown table) + preference summary + extras text.

3.3 Output contract

Preferred: JSON from the model (with schema validation and repair retry):

{

  "summary": "string",

  "recommendations": [

    {

    "restaurant_id": "string",

    "rank": 1,

    "explanation": "string"

    }

  ]

}

Fallback: parse markdown numbered list if JSON fails; log and degrade gracefully.

3.4 Prompt engineering checklist

* Include only restaurants from the shortlist (by id) to reduce hallucination.
* Ask for top K (e.g. 5) with one paragraph max per explanation.
* Instruct to cite concrete attributes (cuisine, rating, cost) from the data.

3.5 Orchestration service

| Step | Action                                                                                                      |
| ---- | ----------------------------------------------------------------------------------------------------------- |
| 1    | Build shortlist (Phase 2)                                                                                   |
| 2    | If empty, return structured empty response (skip LLM or single small call explaining no matches)            |
| 3    | Render prompt from template + data                                                                          |
| 4    | CallGroqAPI with timeout and max tokens                                                                     |
| 5    | Parse/validate response; on failure, retry once with “JSON only” reminder or fall back to heuristic order |

3.6 Configuration

* API key (Groq): Keep the Groq API key in a .env file in the project root (or the directory the app loads env from). Use python-dotenv or your framework’s equivalent so values are available as environment variables at runtime. Add .env to .gitignore and commit only a .env.example (or README snippet) listing required variable names with empty or placeholder values.
* Typical variable name:GROQ_API_KEY (confirm against [Groq API documentation](https://console.groq.com/docs) when implementing).
* Non-secret settings: Model id (e.g. Groq-hosted model name), temperature (low for consistency), max_tokens, and display top_k can live in config.yaml or additional env vars as needed.

3.7 Exit criteria

* Golden-file or manual eval sheet for ~10 preference profiles.
* Documented latency and token usage for typical shortlist sizes.

Phase 4 — Application layer: API and presentation

4.1 Objectives

* Expose a single recommendation endpoint (or CLI) that returns everything the UI needs.
* Render Restaurant Name, Cuisine, Rating, Estimated Cost, AI explanation per row.

4.2 Backend API (recommended shape)

POST /api/v1/recommend

Request body: JSON matching Preferences (Phase 2).

Response body:

{

  "summary": "string",

  "items": [

    {

    "id": "string",

    "name": "string",

    "cuisines": ["string"],

    "rating": 4.2,

    "estimated_cost": "medium",

    "cost_display": "₹800 for two",

    "explanation": "string",

    "rank": 1

    }

  ],

  "meta": {

    "shortlist_size": 35,

    "model": "string",

    "prompt_version": "v1"

  }

}

Implementation note: Merge LLM output with catalog rows by restaurant_id to fill cuisine, rating, and cost for display (do not trust the LLM for numeric facts).

Backend (implemented): `restaurant_rec.phase4.app` — FastAPI app with CORS enabled (`allow_origins=["*"]`). Run from repo root after `pip install -e .`:

    uvicorn restaurant_rec.phase4.app:app --reload

Implemented endpoints:

| Method | Path                  | Purpose                                                 |
| ------ | --------------------- | ------------------------------------------------------- |
| GET    | /api/v1/health        | Liveness; reports catalog row count, model, prompt ver. |
| GET    | /api/v1/locations     | Distinct cities in the catalog.                         |
| GET    | /api/v1/localities    | Distinct localities (used by the UI dropdown).          |
| POST   | /api/v1/recommend     | Body = `UserPreferences`; response per §4.2 contract.   |

Interactive docs at `http://127.0.0.1:8000/docs`. The catalog is loaded eagerly at app startup (Phase 1 parquet via Phase 2 `load_catalog`). `GROQ_API_KEY` from `.env` is used by `recommend()` (Phase 3); empty filter outcomes return 200 with empty `items` and skip the LLM call.

Backend contract tests: `python scripts/test_phase4_api.py` exercises the happy path (real Groq call), 422 validation, and empty-filter short-circuit using FastAPI's `TestClient`.

4.3 UI — dual frontend (end-to-end)

Two frontends share the Phase 4 backend; pick the one that matches the goal.

**Vanilla static UI (`web/`)** — implemented.
- Files: `web/index.html`, `web/styles.css`, `web/app.js`.
- Served directly by FastAPI: `GET /` → `web/index.html`, `GET /static/*` → assets.
- Zero build step, zero JS deps. Locality dropdown is populated from
  `GET /api/v1/localities`; submit POSTs to `/api/v1/recommend` and renders
  ranked cards plus a meta line (`shortlist_size`, `model`, `parse_method`,
  `llm_called`, elapsed, `filter_reason`).
- Use when: smoke-testing the backend, demos that need no toolchain.

**Next.js + Tailwind UI (`web-next/`)** — implemented, modeled after `design/` mocks.
- Stack: Next.js 14 (App Router) + TypeScript + Tailwind. No state library;
  hooks only.
- Layout mirrors the design: red brand header with `AI Concierge` highlighted,
  left **Refine** sidebar (`Spicy`, `Under ₹___`, Quick Tags), pill-style
  natural-language **query bar** with inline edit affordance, restaurant **cards**
  with rank badge, rating chip, cuisine chips, gradient placeholder + cuisine
  emoji, and a `"💬 Why this for you?"` tinted box for the LLM explanation, plus
  a chat-style **Refine further…** input at the bottom that re-runs `/recommend`
  with appended extras.
- Lives at `:3000`. `next.config.mjs` rewrites `/api/*` → `http://127.0.0.1:8000/api/*`,
  so the browser sees one origin and there are no CORS preflights. Override the
  backend URL with `BACKEND_URL=…`.
- Use when: visual demos, iterating on UX, or as the launch UI.

How to run:

```bash
# backend
uvicorn restaurant_rec.phase4.app:app --reload   # :8000

# vanilla static UI:           open http://127.0.0.1:8000/
# Next.js UI (separate window):
cd web-next && npm install && npm run dev        # :3000
```

| Option        | Status                                                              |
| ------------- | ------------------------------------------------------------------- |
| Backend API   | **Implemented** — JSON as in §4.2                                   |
| `web/`        | **Implemented** — vanilla HTML+CSS+JS served by FastAPI             |
| `web-next/`   | **Implemented** — Next.js 14 + Tailwind, modeled after `design/`    |
| CLI           | Optional; `curl` or `/docs` work                                    |
| Notebook      | Teaching/demo only                                                  |

4.4 Cross-cutting concerns

* CORS if SPA on different origin.
* Rate limiting if exposed publicly.
* Input validation return 422 with field errors.

4.5 Exit criteria

* Backend:POST /api/v1/recommend returns structured summary, items, and meta; validation errors return 422; empty filter outcomes return 200 with empty items and a clear summary.
* Browser: user opens /, submits preferences → sees summary and ranked cards (or empty-state message).
* Empty and error states copy-reviewed for clarity.

Improvements (tracked)

The following were implemented in code, API, UI, and [phase-wise-architecture.md](about:blank):

1. Locality dropdown — GET /api/v1/localities returns distinct catalog localities; the web UI `<select>` uses that endpoint. GET /api/v1/locations (distinct cities) remains for other clients. The recommend API still accepts JSON field location (matches catalog locality or city).
2. Numeric budget — User preference is budget_max_inr (max approximate cost for two in INR). Phase 2 keeps rows with known cost_for_two ≤ budget_max_inr. Groq prompts describe this value instead of low/medium/high tiers.
3. Fixed shortlist size — max_results_shortlist was removed from user input. filter.max_shortlist_candidates in config.yaml caps rows passed to the LLM (default 40).

Phase 5 — Hardening, observability, and quality

5.1 Objectives

* Improve reliability, debuggability, and iterative prompt/dataset updates without breaking clients.

5.2 Caching

* Key: hash of (preferences, shortlist content hash, prompt_version, model).
* TTL or LRU for repeated queries in demos.

5.3 Logging and metrics

* Structured logs: shortlist_size, duration_filter_ms, duration_llm_ms, outcome (success / empty / error).
* Avoid logging full prompts if they contain sensitive data; truncate or redact.

5.4 Testing strategy

| Layer  | Tests                                                     |
| ------ | --------------------------------------------------------- |
| Filter | Unit tests, property tests optional                       |
| Prompt | Snapshot of rendered template with fixture data           |
| API    | Contract tests for/recommend                              |
| LLM    | Marked optional integration tests with recorded responses |

5.5 Deployment (optional)

* Containerize app + mount data/processed.
* Secrets via env; no keys in repo.
* Concrete plan: see Phase 6 below.

5.6 Exit criteria

* Runbook: how to refresh data, bump prompt version, rotate API keys.
* Basic load/latency note for expected concurrency.

---

Phase 6 — Deployment

6.1 Topology

| Tier     | Hosted on              | Public URL (placeholder)            |
| -------- | ---------------------- | ----------------------------------- |
| Backend  | Streamlit Community Cloud | `https://<app>.streamlit.app`     |
| Frontend | Vercel                 | `https://<app>.vercel.app`          |
| Catalog  | `data/processed/restaurants.parquet` shipped inside the backend repo (~750 KB) | n/a |

The frontend (`web-next/`) calls the backend over HTTPS; the same `next.config.mjs`
rewrite that points at `http://127.0.0.1:8000` locally is repointed at the
Streamlit URL in production via the `BACKEND_URL` env var on Vercel.

6.2 Backend on Streamlit Community Cloud

**Caveat.** Streamlit Community Cloud runs Streamlit apps, not arbitrary FastAPI
processes. To deploy the backend there, ship a thin Streamlit entry point
(`streamlit_app.py`) that imports `restaurant_rec.phase3.recommend` directly and
exposes the same JSON contract via Streamlit's request handling. FastAPI itself
remains the dev/test target (used by `uvicorn` and `web/`); Streamlit is purely
the production wrapper. If a "real" REST host is preferred later, the same image
runs unchanged on Render, Railway, Fly.io, or Hugging Face Spaces — only this
section changes.

Files to add when deploying:

| File                 | Purpose                                                    |
| -------------------- | ---------------------------------------------------------- |
| `streamlit_app.py`   | Streamlit shim that loads `AppConfig`, eager-loads catalog, exposes a form (or query-param JSON endpoint) calling `recommend()`. |
| `requirements.txt`   | Mirrors `pyproject.toml` runtime deps (Streamlit Cloud installs from this). |
| `.streamlit/secrets.toml` | Holds `GROQ_API_KEY` (set via the Streamlit Cloud dashboard, not committed). |
| `data/processed/restaurants.parquet` | Tracked or built in the Cloud build step. |

Deploy steps:

1. Push the repo to GitHub.
2. In Streamlit Cloud: **New app → repo → branch → `streamlit_app.py`**.
3. Add `GROQ_API_KEY` under **Secrets**; the app reads it via
   `st.secrets["GROQ_API_KEY"]` (mirrored into `os.environ` for `groq_client.py`).
4. First boot loads the parquet; subsequent calls reuse the in-memory frame.

Latency note: Groq round-trip dominates (~1–3 s); Streamlit cold start adds
~5–10 s on the first hit after idle.

6.3 Frontend on Vercel (`web-next/`)

Vercel hosts the Next.js app as-is — `web-next/` is the project root.

Configuration:

| Vercel setting            | Value                                          |
| ------------------------- | ---------------------------------------------- |
| Framework preset          | Next.js                                        |
| Root directory            | `web-next`                                     |
| Build command             | `npm run build` (default)                      |
| Output directory          | `.next` (default)                              |
| Node version              | 18 or 20                                       |
| Env var: `BACKEND_URL`    | `https://<your-backend>.streamlit.app`         |

`next.config.mjs` already reads `BACKEND_URL` and applies it to the
`/api/* → ${BACKEND_URL}/api/*` rewrite, so the same code path that proxies to
`127.0.0.1:8000` in development proxies to the Streamlit URL in production.
Because the proxy is server-side (Next route rewrites run on Vercel's edge),
the browser sees only one origin and there are no CORS preflights.

Deploy steps:

1. Connect the GitHub repo on Vercel; set **Root Directory** to `web-next`.
2. Add `BACKEND_URL` under **Settings → Environment Variables** (Production).
3. Deploy. Subsequent pushes to `main` auto-deploy.

6.4 Secrets and config matrix

| Secret / setting       | Where it lives                                    |
| ---------------------- | ------------------------------------------------- |
| `GROQ_API_KEY`         | Streamlit Cloud secrets (backend only)            |
| `BACKEND_URL`          | Vercel env var (frontend only)                    |
| `config.yaml`          | Committed; tweak via PR + redeploy                |
| `restaurants.parquet`  | Committed under `data/processed/`                 |

No key, including `GROQ_API_KEY`, is ever sent to the browser; the frontend
only knows `BACKEND_URL`, and the LLM call happens server-side in the backend.

6.5 Rollback and refresh

* **Backend rollback:** Streamlit Cloud → app history → reboot at the previous
  commit; if the regression is data-side, regenerate the parquet locally
  (`python scripts/ingest_zomato.py`) and push.
* **Frontend rollback:** Vercel → Deployments → "Promote to Production" on
  the previous green build.
* **Prompt bump:** edit `config.yaml` (`llm.prompt_version`) and redeploy the
  backend; the frontend renders whatever `meta.prompt_version` comes back, so
  it does not need redeploying.
* **Key rotation:** rotate `GROQ_API_KEY` in Streamlit Cloud secrets; backend
  picks up new value on the next reboot.

6.6 Exit criteria

* `https://<frontend>.vercel.app/` loads the UI; Refine sidebar + query bar
  + cards render.
* Submitting preferences round-trips through Vercel → Streamlit → Groq and
  returns within ~5 s P95 after warm.
* `GROQ_API_KEY` is not in the repo, in build logs, or visible to the browser.
* Documented runbook covers redeploy, rollback, key rotation, and parquet
  refresh (see §6.5).

---

Dependency graph between phases

Phase 1 (Catalog)

    │

    ▼

Phase 2 (Filter + Preferences)

    │

    ▼

Phase 3 (LLM orchestration)

    │

    ▼

Phase 4 (API + UI)

    │

    ▼

Phase 5 (Hardening)

    │

    ▼

Phase 6 (Deployment: Streamlit + Vercel)

Phases 2–3 can be prototyped in a notebook before extraction into modules; Phase 4 should consume stable interfaces from 2 and 3.

---

Technology stack (suggestion, not mandatory)

| Concern    | Suggested default                                     |
| ---------- | ----------------------------------------------------- |
| Language   | Python 3.11+                                          |
| Data       | pandasorpolars+ Parquet                               |
| Validation | Pydantic v2                                           |
| API        | FastAPI                                               |
| LLM        | Groqvia Groq API; key in.env→ env (e.g.GROQ_API_KEY) |
| UI         | Simple React/Vite or Streamlit for speed              |

Adjust to your course constraints; the phase boundaries stay the same.

---

Traceability to problem statement

| Problem statement item                                              | Phase |
| ------------------------------------------------------------------- | ----- |
| Load HF Zomato dataset, extract fields                              | 1     |
| User preferences (location,budget_max_inr, cuisine, rating, extras) | 2, 4  |
| Filter + prepare data for LLM                                       | 2, 3  |
| Prompt for reasoning and ranking                                    | 3     |
| LLM rank + explanations + summary                                   | 3     |
| Display name, cuisine, rating, cost, explanation                    | 4     |

---

Document version: 2.3 — Added Phase 6 (Deployment): backend on Streamlit Community Cloud via a `streamlit_app.py` shim that imports `recommend()` (FastAPI stays the local dev/test target); frontend (`web-next/`) on Vercel with `BACKEND_URL` repointing the `/api/*` rewrite to the Streamlit URL in production. Secrets matrix, rollback / refresh / prompt-bump runbook, and exit criteria documented in §6. Earlier additions retained: dual frontend (vanilla `web/` + Next.js `web-next/`), Phase 4 backend, Groq-locked Phase 3.**
