"""Canonical catalog schema for the restaurant recommender.

Phase 1 contract: downstream phases (filtering, prompting, UI) must only
depend on these field names, not on the Hugging Face source columns.
"""
from __future__ import annotations

CANONICAL_COLUMNS: list[str] = [
    "id",
    "name",
    "city",
    "locality",
    "address",
    "cuisines",
    "rating",
    "votes",
    "cost_for_two",
    "budget_tier",
    "raw_features",
]

# Map candidate raw column names (lower-cased) -> canonical field.
# Multiple raw candidates per canonical field handle dataset variations.
RAW_TO_CANONICAL: dict[str, str] = {
    # id
    "restaurant id": "id",
    "restaurant_id": "id",
    "res_id": "id",
    "id": "id",
    # name
    "name": "name",
    "restaurant name": "name",
    "restaurant_name": "name",
    # city
    "city": "city",
    "location city": "city",
    # locality / neighbourhood
    # `listed_in(city)` in the Bangalore Zomato dump holds neighbourhood
    # names (e.g. "BTM", "Koramangala 5th Block"), not a real city — map to locality.
    "listed_in(city)": "locality",
    "listed in(city)": "locality",
    "location": "locality",
    "locality": "locality",
    "area": "locality",
    "neighbourhood": "locality",
    # address
    "address": "address",
    "full_address": "address",
    # cuisines
    "cuisines": "cuisines",
    "cuisine": "cuisines",
    # rating
    "rate": "rating",
    "rating": "rating",
    "aggregate_rating": "rating",
    "aggregate rating": "rating",
    # votes
    "votes": "votes",
    "vote": "votes",
    "review_count": "votes",
    "reviews": "votes",
    # cost
    "approx_cost(for two people)": "cost_for_two",
    "approx_cost": "cost_for_two",
    "approx cost(for two people)": "cost_for_two",
    "average_cost_for_two": "cost_for_two",
    "cost_for_two": "cost_for_two",
    "cost": "cost_for_two",
    # extras text blob candidates
    "rest_type": "raw_features",
    "listed_in(type)": "raw_features",
    "dish_liked": "raw_features",
}


BUDGET_TIERS = ("low", "medium", "high")


def example_row() -> dict:
    """Canonical example row used in docs and tests.

    Mirrors what `restaurants.parquet` contains for a real venue from the
    Bangalore Zomato slice.
    """
    return {
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
        "raw_features": "Microbrewery",
    }
