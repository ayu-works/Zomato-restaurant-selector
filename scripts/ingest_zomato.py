"""Thin CLI wrapper around `restaurant_rec.phase1.ingest`.

Run from the repo root:

    python scripts/ingest_zomato.py
    python scripts/ingest_zomato.py --input-csv data/raw/zomato.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from restaurant_rec.phase1.ingest import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
