"""Row-level validators for the canonical catalog."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    rows_in: int
    rows_out: int
    drop_reasons: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "dropped": self.rows_in - self.rows_out,
            "drop_reasons": dict(self.drop_reasons),
        }


def validate(df: pd.DataFrame, *, rating_scale_max: float = 5.0) -> tuple[pd.DataFrame, ValidationReport]:
    rows_in = len(df)
    reasons: Counter[str] = Counter()

    def _check(row: pd.Series) -> str | None:
        if not row.get("name"):
            return "missing_name"
        if not row.get("city") and not row.get("locality"):
            return "missing_location"
        rating = row.get("rating")
        if rating is not None and not pd.isna(rating):
            if rating < 0 or rating > rating_scale_max + 0.01:
                return "rating_out_of_range"
        cuisines = row.get("cuisines")
        if cuisines is None or (isinstance(cuisines, list) and len(cuisines) == 0):
            return "missing_cuisines"
        return None

    failures = df.apply(_check, axis=1)
    for r in failures.dropna():
        reasons[r] += 1

    kept = df[failures.isna()].copy()

    # Deduplicate by id (keep highest votes, then highest rating)
    if "id" in kept.columns and len(kept) > 0:
        before = len(kept)
        kept = (
            kept.sort_values(
                by=["votes", "rating"], ascending=[False, False], na_position="last"
            )
            .drop_duplicates(subset=["id"], keep="first")
            .reset_index(drop=True)
        )
        dupes = before - len(kept)
        if dupes:
            reasons["duplicate_id"] = dupes

    report = ValidationReport(
        rows_in=rows_in, rows_out=len(kept), drop_reasons=dict(reasons)
    )
    return kept, report
