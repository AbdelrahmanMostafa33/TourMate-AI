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

from typing import Optional
from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city  # async
from ai_engine.tools.haversine import haversine


# ── Filter thresholds ────────────────────────────────────────────────────────

MIN_RATING = 3.5
# Minimum popularity score to include a place (0 = no filter)
MIN_POPULARITY = 0
# Maximum distance from city center in km (None = no limit)
MAX_DISTANCE_KM = 50


def _compute_city_center(places: list[dict]) -> Optional[tuple[float, float]]:
    """
    Compute the geographic center (centroid) of all non-hotel places.

    The centroid is calculated by averaging the latitude and longitude
    of every place that is NOT categorized as a hotel. This can be used
    as a representative "city center" for planning activities while
    ignoring accommodation locations.

    Returns:
        (latitude, longitude) tuple if non-hotel places exist.
        None if the list contains only hotels or is empty.
    """

    # Filter out hotels because accommodation locations should not
    # influence the activity center of the itinerary.
    non_hotel = [p for p in places if p.get("category") != "hotel"]

    # If there are no attractions/restaurants/etc.,
    # we cannot compute a meaningful center.
    if not non_hotel:
        return None

    # Compute the average latitude of all non-hotel places.
    # This gives the north-south center point.
    center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)

    # Compute the average longitude of all non-hotel places.
    # This gives the east-west center point.
    center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)

    # Return the computed geographic centroid as (latitude, longitude).
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

    Filtering steps:
    1. Hotels are filtered by accommodation preference.
    2. Restaurants always pass (every trip needs food).
    3. Non-hotel, non-restaurant places must satisfy a minimum rating.
    4. They must be within a maximum distance from the
       computed city/activity center.

    Note: Interest-based relevance is NOT filtered here. All places
    that pass rating + distance are kept. The Ranking Agent scores
    preferences as a soft signal (25% weight) so matching places
    naturally rank higher without eliminating complementary options
    like restaurants, landmarks, or parks that a history-lover still
    needs to eat at and visit.

    Returns:
        A filtered list of places suitable for itinerary generation.
    """

    # Compute the geographic center of activity locations.
    # This is later used to eliminate places that are too far away.
    center = _compute_city_center(places)

    # Determine the user's preferred accommodation type.
    # Priority:
    # 1. Structured enum value (accommodation_type)
    # 2. Raw extracted text (accommodation_style)
    # Example values:
    # "hotel", "hostel", "resort", "boutique hotel"
    accommodation_type = (
        preferences.get("accommodation_type")
        or (preferences.get("accommodation_style") or "").lower()
    )

    # Store places that pass all filtering criteria.
    filtered = []

    # Evaluate each candidate place independently.
    for place in places:

        # ==========================================================
        # HOTEL FILTERING
        # ==========================================================
        # Hotels are always considered separately because they
        # should not be filtered by interests or distance.
        if place.get("category") == "hotel":

            # If the user specified an accommodation preference,
            # verify that the hotel's type matches.
            if accommodation_type:

                # Normalize hotel's accommodation type.
                place_acc = (place.get("accommodation_type") or "").lower()

                # Accept partial matches in either direction.
                #
                # Examples:
                # User: "hotel"
                # Place: "boutique hotel"
                #
                # User: "resort"
                # Place: "luxury resort"
                #
                # User: "boutique hotel"
                # Place: "hotel"
                if not (
                    accommodation_type in place_acc
                    or place_acc in accommodation_type
                ):
                    continue

            # Hotel passed filtering.
            filtered.append(place)
            continue

        # ==========================================================
        # RATING FILTER
        # ==========================================================
        # Remove places with ratings below the minimum threshold.
        rating = place.get("rating", 0) or 0

        if rating < MIN_RATING:
            continue

        # ==========================================================
        # DISTANCE FILTER
        # ==========================================================
        # Keep attractions reasonably close to the activity center.
        if center and MAX_DISTANCE_KM:

            # Calculate great-circle distance between
            # city center and current place.
            dist = haversine(
                center[0],
                center[1],
                place["lat"],
                place["lon"]
            )

            # Skip places that are too far away.
            if dist > MAX_DISTANCE_KM:
                continue

        # ==========================================================
        # PLACE PASSED ALL FILTERS
        # ==========================================================
        filtered.append(place)

    # Return the final filtered candidate set.
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

    The Retrieval Agent is responsible for finding candidate places
    that match the user's trip requirements before itinerary planning.

    Workflow:
    1. Load all available places for the destination.
    2. Apply preference-based filtering.
    3. Ensure a balanced mix of place categories.
    4. Store the resulting candidates for the Ranking Agent.

    Returns:
        Updated TripState containing filtered candidate places.
    """

    # ==========================================================
    # Extract required information from the shared TripState.
    # These values were produced by previous agents in the pipeline.
    # ==========================================================

    # Destination city for which places should be retrieved.
    city = state.get("destination_city", "")

    # Number of travel days.
    # Default to 3 if not specified.
    duration_days = state.get("duration_days") or 3

    # User preferences extracted from conversation.
    # Examples:
    # {
    #     "accommodation_type": "hotel",
    #     "interests_from_conversation": ["museum", "food"]
    # }
    preferences = state.get("extracted_preferences") or {}

    # ==========================================================
    # STAGE 1: Retrieve all available places.
    # ==========================================================
    #
    # Query the place database for the destination city.
    # Interest-based filtering is handled downstream by the Ranking Agent.
    #
    all_places = await get_places_for_city(city)

    # If no places exist for the destination,
    # terminate early and record an error.
    if not all_places:
        state["filtered_places"] = []
        state["error"] = f"No places found for city: {city}"
        return state

    # ==========================================================
    # STAGE 2: Apply structured filtering.
    # ==========================================================
    #
    # This removes places that do not satisfy:
    # - accommodation preferences
    # - minimum rating
    # - maximum distance
    # - interest relevance
    #
    filtered = _apply_filters(
        all_places,
        preferences,
        city
    )

    # ==========================================================
    # STAGE 3: Ensure category diversity.
    # ==========================================================
    #
    # Avoid returning only one type of place.
    #
    # Example:
    # Instead of:
    #   15 museums
    #
    # Return:
    #   museums
    #   restaurants
    #   parks
    #   shopping
    #   landmarks
    #
    # The duration influences how many places are needed.
    #
    diverse = _ensure_diversity(
        filtered,
        duration_days
    )

    # ==========================================================
    # Store the final candidate set.
    # ==========================================================
    #
    # These places will become input for the Ranking Agent,
    # which scores and orders them.
    #
    state["filtered_places"] = diverse

    # Record diagnostic information for debugging
    # and agent execution tracing.
    #
    # Example:
    # [RetrievalAgent] 250 total → 80 filtered → 45 after diversity
    #
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [
            f"[RetrievalAgent] "
            f"{len(all_places)} total → "
            f"{len(filtered)} filtered → "
            f"{len(diverse)} after diversity"
        ]
    )

    # Return updated state for the next LangGraph agent.
    return state
