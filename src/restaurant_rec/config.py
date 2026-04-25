from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


@dataclass
class Paths:
    raw_dir: Path
    processed_catalog: Path


@dataclass
class DatasetCfg:
    hf_id: str
    split: str = "train"
    default_city: str | None = None


@dataclass
class SchemaCfg:
    rating_scale_max: float = 5.0
    budget_tiers: dict[str, int] = field(
        default_factory=lambda: {"low_max_inr": 500, "medium_max_inr": 1200}
    )


@dataclass
class FilterCfg:
    max_shortlist_candidates: int = 40
    relax_min_matches: int = 5
    rating_relax_step: float = 0.5


@dataclass
class LLMCfg:
    provider: str = "groq"
    model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout_s: float = 30.0
    top_k: int = 5
    prompt_version: str = "v1"


@dataclass
class AppConfig:
    paths: Paths
    dataset: DatasetCfg
    schema: SchemaCfg
    filter: FilterCfg = field(default_factory=FilterCfg)
    llm: LLMCfg = field(default_factory=LLMCfg)
    city_aliases: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "AppConfig":
        cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        p = raw.get("paths", {})
        paths = Paths(
            raw_dir=_resolve(p.get("raw_dir", "data/raw")),
            processed_catalog=_resolve(
                p.get("processed_catalog", "data/processed/restaurants.parquet")
            ),
        )
        ds = raw.get("dataset", {})
        dataset = DatasetCfg(
            hf_id=ds.get("hf_id", "ManikaSaini/zomato-restaurant-recommendation"),
            split=ds.get("split", "train"),
            default_city=ds.get("default_city"),
        )
        sc = raw.get("schema", {})
        schema = SchemaCfg(
            rating_scale_max=float(sc.get("rating_scale_max", 5.0)),
            budget_tiers=sc.get(
                "budget_tiers", {"low_max_inr": 500, "medium_max_inr": 1200}
            ),
        )
        fc = raw.get("filter", {}) or {}
        filter_cfg = FilterCfg(
            max_shortlist_candidates=int(fc.get("max_shortlist_candidates", 40)),
            relax_min_matches=int(fc.get("relax_min_matches", 5)),
            rating_relax_step=float(fc.get("rating_relax_step", 0.5)),
        )
        lc = raw.get("llm", {}) or {}
        llm_cfg = LLMCfg(
            provider=lc.get("provider", "groq"),
            model=lc.get("model", "llama-3.3-70b-versatile"),
            temperature=float(lc.get("temperature", 0.2)),
            max_tokens=int(lc.get("max_tokens", 1200)),
            timeout_s=float(lc.get("timeout_s", 30.0)),
            top_k=int(lc.get("top_k", 5)),
            prompt_version=lc.get("prompt_version", "v1"),
        )
        return cls(
            paths=paths,
            dataset=dataset,
            schema=schema,
            filter=filter_cfg,
            llm=llm_cfg,
            city_aliases=raw.get("city_aliases", {}) or {},
        )


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (REPO_ROOT / path)
