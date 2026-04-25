"""Catalog loader: read the Phase 1 parquet into a DataFrame once."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd


def _to_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple, np.ndarray)):
        return [str(x) for x in list(v) if x is not None and str(x).strip()]
    if isinstance(v, float) and pd.isna(v):
        return []
    return [str(v)]


@lru_cache(maxsize=4)
def load_catalog(path: str | Path) -> pd.DataFrame:
    """Load the canonical catalog. Cached by path string."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Catalog not found at {p}. Run Phase 1 ingestion first: "
            f"`python scripts/ingest_zomato.py`."
        )
    df = pd.read_parquet(p)
    # Parquet round-trip turns list columns into numpy ndarrays; normalize to list[str].
    if "cuisines" in df.columns:
        df["cuisines"] = df["cuisines"].map(_to_list)
    return df
