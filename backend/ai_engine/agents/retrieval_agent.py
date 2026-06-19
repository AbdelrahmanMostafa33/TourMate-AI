"""
Retrieval Agent — Stage 2 of the multi-agent pipeline.

Responsibilities:
1. Filter places from the database using structured preference criteria.
2. Apply SQL-style filters: city, category, rating, price_level.
3. Preserve category diversity (always include hotels for accommodation).
4. Return the filtered set to the Ranking Agent.

This agent acts as the bridge between raw place data and the
ranking/relevance layer. It answers: "Which places *could* be relevant?"
The Ranking Agent then answers: "Which places are *most* relevant?"
"""

import math
from typing import Optional
from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city
from ai_engine.tools.haversine import haversine


# ── Filter thresholds ────────────────────────────────────────────────────────

MIN_RATING = 3.5
# Minimum popularity score to include a place (0 = no filter)
MIN_POPULARITY = 0
# Maximum distance from city center in km (None = no limit)
MAX_DISTANCE_KM = 50


def _compute_city_center(places: list[dict]) -> Optional[tuple[float, float]]:
    """Compute the geographic centroid of non-hotel places."""
    non_hotel = [p for p in places if p.get("category") != "hotel"]
    if not non_hotel:
        return None
    center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)
    center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)
    return (center_lat, center_lon)


def _apply_filters(
    places: list[dict],
    preferences: dict,
    city: str,
) -> list[dict]:
    """
    Apply structured filters to the place set.

    Filters applied:
    - Category: match user interests (always keep hotels)
    - Rating: minimum threshold
    - Distance: within MAX_DISTANCE_KM of city center
    - Interest tags: at least one tag matches user interests
    """
    center = _compute_city_center(places)
    interests = set(preferences.get("interests_from_conversation", []))
    walking_tolerance = preferences.get("walking_tolerance", "medium")

    filtered = []
    for place in places:
        # ── Always keep hotels (needed for accommodation suggestions) ──
        if place.get("category") == "hotel":
            filtered.append(place)
            continue

        # ── Rating filter ──
        rating = place.get("rating", 0) or 0
        if rating < MIN_RATING:
            continue

        # ── Distance filter ──
        if center and MAX_DISTANCE_KM:
            dist = haversine(center[0], center[1], place["lat"], place["lon"])
            if dist > MAX_DISTANCE_KM:
                continue

        # ── Interest relevance filter ──
        # Keep a place if:
        # 1. No interests specified (broad search)
        # 2. Its category matches an interest
        # 3. Any of its interest_tags match
        if interests:
            category_match = place.get("category", "") in interests
            tag_match = any(
                t in interests
                for t in place.get("interest_tags", [])
            )
            name_match = any(
                kw in place.get("name", "").lower()
                for kw in interests
            )
            if not (category_match or tag_match or name_match):
                continue

        filtered.append(place)

    return filtered


def _ensure_diversity(places: list[dict], duration_days: int) -> list[dict]:
    """
    Ensure the filtered set has minimum category diversity.

    Even after interest filtering, we want to guarantee that the
    planner has at least a few options in each major category.
    """
    min_per_category = {
        "attractions": max(duration_days * 2, 4),
        "restaurant": max(duration_days, 3),
        "hotel": max(duration_days // 2 + 1, 2),
    }

    by_category: dict[str, list] = {}
    for place in places:
        cat = place.get("category", "other")
        by_category.setdefault(cat, []).append(place)

    result = []
    for cat, min_count in min_per_category.items():
        available = by_category.get(cat, [])
        # Take up to the minimum needed, sorted by popularity
        available.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)
        result.extend(available[:min_count])

    # Also include any other categories not in min_per_category
    for cat, cat_places in by_category.items():
        if cat not in min_per_category:
            result.extend(cat_places)

    return result


async def run_retrieval_agent(state: TripState) -> TripState:
    """
    Main Retrieval Agent workflow.

    1. Load all places for the destination city.
    2. Apply structured filters based on extracted preferences.
    3. Ensure minimum diversity across categories.
    4. Store filtered candidates in state for the Ranking Agent.
    """
    city = state.get("destination_city", "")
    duration_days = state.get("duration_days", 3)
    preferences = state.get("extracted_preferences") or {}
    profile = state.get("profile") or {}
    interests = profile.get("interests", [])

    # Stage 1: Load all available places for the city
    all_places = get_places_for_city(city, interests=interests)

    if not all_places:
        state["filtered_places"] = []
        state["error"] = f"No places found for city: {city}"
        return state

    # Stage 2: Apply structured filters
    filtered = _apply_filters(all_places, preferences, city)

    # Stage 3: Ensure category diversity
    diverse = _ensure_diversity(filtered, duration_days)

    state["filtered_places"] = diverse
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[RetrievalAgent] {len(all_places)} total → {len(filtered)} filtered → {len(diverse)} after diversity"]
    )

    return state
