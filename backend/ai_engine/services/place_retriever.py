"""
Place Retriever — Stage 2 of the multi-agent pipeline.

Responsibilities:
1. Filter places from the database using structured preference criteria.
2. Apply SQL-style filters: city, category, rating, price_level.
3. Preserve category diversity (always include hotels for accommodation).
4. Return the filtered set to the Candidate Scorer.

This service acts as the bridge between raw place data and the
scoring/relevance layer. It answers: "Which places *could* be relevant?"
The Candidate Scorer then answers: "Which places are *most* relevant?"
"""

from typing import Optional
from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city  # async
from ai_engine.tools.haversine import haversine
from ai_engine.tools.slot_normalizer import map_accommodation_to_type


# ── Filter thresholds ────────────────────────────────────────────────────────

MIN_RATING = 3.5


# Minimum popularity score to include a place (0 = no filter)
MIN_POPULARITY = 0
# Maximum distance from city center in km (None = no limit)
MAX_DISTANCE_KM = 50


def _compute_city_center(places: list[dict]) -> Optional[tuple[float, float]]:
    """Compute the geographic center (centroid) of all non-hotel places."""
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
    Apply structured filtering to a list of candidate places.

    The goal is to remove places that do not match the user's
    preferences while preserving accommodation options.
    """
    center = _compute_city_center(places)
    acc_prefs = preferences.get("accommodation_preferences") or []
    accommodation_type = map_accommodation_to_type(acc_prefs)

    filtered = []
    for place in places:
        # HOTEL FILTERING
        if place.get("category") == "hotel":
            if accommodation_type:
                place_acc = (place.get("accommodation_type") or "").lower()
                if not (
                    accommodation_type in place_acc
                    or place_acc in accommodation_type
                ):
                    continue
            filtered.append(place)
            continue

        # RATING FILTER
        rating = place.get("rating", 0) or 0
        if rating < MIN_RATING:
            continue

        # DISTANCE FILTER
        if center and MAX_DISTANCE_KM:
            dist = haversine(
                center[0], center[1],
                place["lat"], place["lon"]
            )
            if dist > MAX_DISTANCE_KM:
                continue

        filtered.append(place)

    return filtered


def _cap_candidates(
    places: list[dict],
    max_attractions: int = 150,
    max_restaurants: int = 25,
    max_hotels: int = 15,
    samples_per_subcategory: int = 8,
) -> list[dict]:
    """
    Cap the number of candidates per category using per-subcategory sampling.
    """
    hotels = [p for p in places if p.get("category") == "hotel"]
    restaurants = [p for p in places if p.get("category") == "restaurant"]
    attractions = [
        p for p in places
        if p.get("category") not in ("hotel", "restaurant")
    ]

    restaurants.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)
    hotels.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)

    by_subcategory: dict[str, list[dict]] = {}
    for p in attractions:
        sub = (p.get("sub_category") or "").lower() or "other"
        by_subcategory.setdefault(sub, []).append(p)

    result = []
    for sub in by_subcategory:
        group = by_subcategory[sub]
        group.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)
        result.extend(group[:samples_per_subcategory])

    if len(result) < max_attractions:
        remaining = max_attractions - len(result)
        extras = []
        for sub in by_subcategory:
            group = by_subcategory[sub]
            extras.extend(group[samples_per_subcategory:])
        extras.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)
        result.extend(extras[:remaining])

    result = result[:max_attractions]
    result.extend(restaurants[:max_restaurants])
    result.extend(hotels[:max_hotels])
    return result


async def retrieve_places(state: TripState) -> TripState:
    """
    Main Place Retriever workflow.

    The Place Retriever is responsible for finding candidate places
    that match the user's trip requirements before itinerary planning.

    Workflow:
    1. Load all available places for the destination.
    2. Apply preference-based filtering.
    3. Ensure a balanced mix of place categories.
    4. Store the resulting candidates for the Candidate Scorer.
    """
    city = state.get("destination_city", "")
    duration_days = state.get("duration_days") or 3
    preferences = state.get("profile") or {}

    all_places = await get_places_for_city(city)
    if not all_places:
        state["filtered_places"] = []
        state["error"] = f"No places found for city: {city}"
        return state

    filtered = _apply_filters(all_places, preferences, city)

    diverse = _cap_candidates(
        filtered,
        max_attractions=150,
        max_restaurants=25,
        max_hotels=15,
    )

    state["filtered_places"] = diverse
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [
            f"[PlaceRetriever] "
            f"{len(all_places)} total → "
            f"{len(filtered)} filtered → "
            f"{len(diverse)} after capping"
        ]
    )

    return state
