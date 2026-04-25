"""End-to-end Phase 1 ingestion: HF dataset -> canonical parquet catalog."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from ..config import AppConfig
from .transform import transform_frame
from .validate import validate

log = logging.getLogger("restaurant_rec.phase1.ingest")


def load_hf_dataframe(hf_id: str, split: str) -> pd.DataFrame:
    """Load a HF dataset split into a pandas DataFrame."""
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "The 'datasets' package is required. Install project deps with "
            "`pip install -e .`"
        ) from e

    log.info("Loading Hugging Face dataset %s (split=%s)", hf_id, split)
    ds = load_dataset(hf_id, split=split)
    return ds.to_pandas()


def run(
    config: AppConfig,
    *,
    input_csv: Path | None = None,
    output: Path | None = None,
) -> dict:
    """Run the ingestion pipeline and write a parquet catalog.

    Returns a summary dict (row counts + drop reasons).
    """
    if input_csv is not None:
        log.info("Loading local CSV fallback %s", input_csv)
        raw = pd.read_csv(input_csv)
    else:
        raw = load_hf_dataframe(config.dataset.hf_id, config.dataset.split)

    rows_raw = len(raw)
    log.info("Loaded %d raw rows with columns: %s", rows_raw, list(raw.columns))

    # Snapshot raw HF dataframe for traceability (architecture §1.5).
    raw_snapshot = config.paths.raw_dir / "zomato_raw.parquet"
    raw_snapshot.parent.mkdir(parents=True, exist_ok=True)
    raw_to_save = raw.copy()
    # `reviews_list` / `menu_item` can hold nested structures parquet rejects;
    # coerce to string so the snapshot always writes.
    for col in ("reviews_list", "menu_item"):
        if col in raw_to_save.columns:
            raw_to_save[col] = raw_to_save[col].astype(str)
    raw_to_save.to_parquet(raw_snapshot, index=False)
    log.info("Wrote raw snapshot (%d rows) to %s", rows_raw, raw_snapshot)

    transformed = transform_frame(
        raw,
        city_aliases=config.city_aliases,
        rating_scale_max=config.schema.rating_scale_max,
        budget_tiers=config.schema.budget_tiers,
        default_city=config.dataset.default_city,
    )

    cleaned, report = validate(
        transformed, rating_scale_max=config.schema.rating_scale_max
    )

    out_path = Path(output) if output else config.paths.processed_catalog
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(out_path, index=False)
    log.info("Wrote %d rows to %s", len(cleaned), out_path)

    summary = {
        "rows_raw": rows_raw,
        **report.to_dict(),
        "raw_snapshot_path": str(raw_snapshot),
        "output_path": str(out_path),
        "columns": list(cleaned.columns),
    }
    log.info("Ingestion summary: %s", json.dumps(summary, indent=2))
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Zomato catalog ingestion (Phase 1)")
    p.add_argument("--config", type=Path, default=None, help="Path to config.yaml")
    p.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Optional local CSV to use instead of the HF dataset (offline runs).",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override the catalog output path.",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = AppConfig.load(args.config)
    summary = run(config, input_csv=args.input_csv, output=args.output)
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
