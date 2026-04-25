"""FastAPI app for the Phase 4 backend.

Run from repo root after `pip install -e .`:

    uvicorn restaurant_rec.phase4.app:app --reload
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..config import AppConfig, REPO_ROOT
from ..phase2 import UserPreferences, load_catalog
from ..phase3 import recommend

log = logging.getLogger(__name__)


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or AppConfig.load()
    app = FastAPI(
        title="Restaurant Recommender",
        version="0.1.0",
        description="Zomato-style restaurant recommendations powered by Groq.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Eager-load catalog so the first request isn't slow and missing data is
    # surfaced at startup.
    catalog = load_catalog(cfg.paths.processed_catalog)
    log.info("phase4: catalog loaded rows=%d path=%s", len(catalog), cfg.paths.processed_catalog)

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "catalog_rows": int(len(catalog)),
            "model": cfg.llm.model,
            "prompt_version": cfg.llm.prompt_version,
        }

    @app.get("/api/v1/locations")
    def locations() -> dict[str, list[str]]:
        cities = sorted(
            {str(c) for c in catalog["city"].dropna().unique() if str(c).strip()}
        )
        return {"locations": cities}

    @app.get("/api/v1/localities")
    def localities() -> dict[str, list[str]]:
        items = sorted(
            {str(c) for c in catalog["locality"].dropna().unique() if str(c).strip()}
        )
        return {"localities": items}

    @app.post("/api/v1/recommend")
    def recommend_endpoint(prefs: UserPreferences) -> dict[str, Any]:
        try:
            result = recommend(prefs, cfg, catalog=catalog)
        except Exception as e:  # belt-and-suspenders; recommend() handles LLM errors internally
            log.exception("recommend() failed")
            raise HTTPException(status_code=500, detail=f"internal error: {e}") from e
        return result.to_dict()

    # --- Static UI under web/ -----------------------------------------------
    web_dir = REPO_ROOT / "web"
    if web_dir.is_dir():
        app.mount("/static", StaticFiles(directory=web_dir), name="static")
        index_path = web_dir / "index.html"

        @app.get("/", include_in_schema=False)
        def _index():
            if not index_path.is_file():
                raise HTTPException(status_code=404, detail="UI not built")
            return FileResponse(index_path)
    else:
        log.warning("web/ directory not found at %s; UI disabled", web_dir)

    return app


# Module-level instance for `uvicorn restaurant_rec.phase4.app:app`
app = create_app()
