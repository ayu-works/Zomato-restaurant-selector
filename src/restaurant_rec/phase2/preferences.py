"""User preference model (Phase 2).

Uses numeric `budget_max_inr` per the documented §4 improvement, instead
of low/medium/high tiers.
"""
from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field, field_validator


class UserPreferences(BaseModel):
    location: str = Field(..., min_length=1, description="City or locality name.")
    cuisine: Union[str, list[str], None] = Field(
        default=None, description="One cuisine or a list. Matched case-insensitively."
    )
    min_rating: float = Field(default=0.0, ge=0.0, le=5.0)
    budget_max_inr: float | None = Field(
        default=None, ge=0, description="Max approximate cost for two in INR."
    )
    extras: str | None = Field(
        default=None, description="Free-text hints (e.g. 'family-friendly')."
    )

    @field_validator("location")
    @classmethod
    def _strip_location(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("location must be non-empty")
        return v

    @field_validator("cuisine")
    @classmethod
    def _normalize_cuisine(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            v = [v]
        out = [s.strip() for s in v if s and s.strip()]
        return out or None

    def cuisine_list(self) -> list[str]:
        c = self.cuisine
        if not c:
            return []
        return list(c) if isinstance(c, list) else [c]
