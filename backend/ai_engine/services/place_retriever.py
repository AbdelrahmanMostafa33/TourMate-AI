"""
Place Retriever — Stage 2 of the multi-agent pipeline.

Responsibilities:
1. Filter places from the database using structured preference criteria.
2. Apply SQL-style filters: city, category, rating, price_level.
3. Return the filtered set to the Candidate Scorer.
4. Hotels are excluded entirely — handled in post-approval HOTEL_SELECTION phase.

This service acts as the bridge between raw place data and the
scoring/relevance layer. It answers: "Which places *could* be relevant?"
The Candidate Scorer then answers: "Which places are *most* relevant?"
"""

import logging
from typing import Optional, List

from pydantic import BaseModel, Field

from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city  # async
from ai_engine.tools.haversine import haversine


logger = logging.getLogger(__name__)


# ── Filter thresholds ────────────────────────────────────────────────────────

MIN_RATING = 3.5

# Minimum rating threshold for places in interest-matching subcategories.
# More lenient than MIN_RATING (3.5) because non-matching attractions are now
# *excluded entirely* when interests exist — so we want to be generous with
# the ones that do match to give the planner enough options.
MIN_RATING_INTEREST_MATCH = 3.0


# Minimum popularity score to include a place (0 = no filter)
MIN_POPULARITY = 0
# Maximum distance from city center in km (None = no limit)
MAX_DISTANCE_KM = 50


# ── Semantic interest-to-subcategory matching prompt ─────────────────────────
#
# Uses a single lightweight LLM call (via the `router` role) to semantically
# match the user's interests against the available place subcategories.
# This replaces the simple keyword-based interest_map and runs BEFORE filtering
# so the retriever can be more lenient with interest-matching places.
#
# This naturally handles:
#   - "hiking" → "nature", "parks"
#   - "photography" → "sightseeing", "nature"
#   - "night" → "nightlife"
#   - "culture" → "museums", "history"

# ── Pydantic structured output for semantic interest-to-subcategory matching ──
#
# Using ``.with_structured_output()`` guarantees valid structured data from
# the LLM via tool calling, eliminating fragile text-format parsing and
# the inconsistency of comma-separated vs newline vs JSON text output.


class SemanticCategoryMatch(BaseModel):
    """
    Structured output for semantic interest-to-subcategory matching.

    The LLM fills ``matched_subcategories`` via tool calling, guaranteeing
    a consistent list format regardless of model or temperature.
    """

    matched_subcategories: List[str] = Field(
        default_factory=list,
        description=(
            "Subcategory names that semantically match one or more user interests. "
            "Only include subcategories from the available list. "
            "Leave empty if no valid match exists."
        ),
    )


_SEMANTIC_MATCH_SYSTEM_PROMPT = """You are the Semantic Category Router for TourMate AI.

## Objective

Given:

1. A list of user interests.
2. A list of available place subcategories.

Return the subcategories that have a strong semantic relationship with one or more user interests.

Your purpose is high-precision filtering, not recommendation.

---

## Matching Principles

Use semantic understanding rather than exact keyword matching.

Consider:

- synonyms
- closely related concepts
- common travel intent
- domain-specific equivalents

Only return a subcategory if the relationship is direct and unambiguous.

If a mapping is uncertain, DO NOT return it.

Precision is more important than recall.

---

## Canonical Mapping Rules

Use the following mappings as authoritative.

history
→ history

architecture
→ history, sightseeing

culture
→ museums, history, religious

art
→ museums

photography
→ sightseeing, nature

urban exploration
→ sightseeing, history, shopping

nature
→ nature

desert
→ nature

wildlife
→ nature

wilderness
→ nature, parks

hiking
→ nature, parks

adventure
→ sports, nature

sports
→ sports

night
→ nightlife

nightlife
→ nightlife

party
→ nightlife, entertainment

music
→ entertainment, nightlife

shopping
→ shopping

sightseeing
→ sightseeing, history

food
→ (no match)

dining
→ (no match)

---

## Explicit Non-Matches

Never infer any of the following:

culture → ✗ nightlife, entertainment, family
history → ✗ nightlife, family
architecture → ✗ entertainment, nightlife, family
adventure → ✗ entertainment, nightlife, family
sightseeing → ✗ nightlife, family
art → ✗ entertainment
food → ✗ attractions
dining → ✗ attractions

---

## Additional Rules

- Never invent new subcategories.
- Only return subcategories that exist in the provided PLACE SUBCATEGORIES list.
- Ignore duplicate user interests.
- Ignore interests that have no valid mapping.
- Return each subcategory at most once.
- If no valid subcategory exists, return an empty list.
"""


async def _compute_semantic_interest_subcats(
    profile_interests: Optional[list[str]],
    subcategory_names: list[str],
) -> set[str]:
    """
    Use a single lightweight LLM call with structured output to semantically
    match user interests to available place subcategories.

    Uses ``.with_structured_output(SemanticCategoryMatch)`` so the LLM returns
    data via tool calling, guaranteeing a consistent list format regardless
    of model or temperature — eliminating the fragile comma-separated text
    parsing that previously caused format inconsistencies.

    Moved from candidate_scorer.py to run earlier in the pipeline — before
    filtering — so the Place Retriever can be more lenient with places whose
    subcategory matches a user interest.

    Args:
        profile_interests: List of user interest strings (e.g.
            ["nightlife", "food", "socializing"]).
        subcategory_names: List of available subcategory names from the
            place database (e.g. ["history", "museums", "nightlife", ...]).

    Returns:
        Set of subcategory names that semantically match the user's interests.
    """
    if not profile_interests or not subcategory_names:
        return set()

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from ai_engine.llm.invoke import invoke_with_fallback

        interests_str = ", ".join(profile_interests)
        subcats_str = ", ".join(sorted(subcategory_names))
        subcategory_names_set = {s.lower() for s in subcategory_names}

        messages = [
            SystemMessage(content=_SEMANTIC_MATCH_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"User interests: [{interests_str}]\n"
                    f"Available subcategories: [{subcats_str}]\n"
                    "Which subcategories match?"
                )
            ),
        ]

        response = await invoke_with_fallback(
            agent_role="router",
            messages=messages,
            structured_output=SemanticCategoryMatch,
        )

        # Response is a SemanticCategoryMatch object (via tool calling)
        # — no text parsing needed.
        if response and hasattr(response, "matched_subcategories"):
            matched: set[str] = set()
            for name in response.matched_subcategories:
                norm = name.strip().lower()
                if norm in subcategory_names_set:
                    matched.add(norm)
            return matched
        return set()

    except Exception as exc:
        logger.warning("[PlaceRetriever] LLM semantic match failed: %s — falling back to empty set", exc)
        return set()


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
    interest_subcats: Optional[set[str]] = None,
) -> list[dict]:
    """
    Apply structured filtering to a list of candidate places.

    The goal is to remove places that do not match the user's
    Hotels are excluded entirely — they are handled in the post-approval
    ``HOTEL_SELECTION`` phase, independent of the itinerary pipeline.

    ``interest_subcats`` is a pre-computed set of subcategory names that
    semantically match the user's interests (from the lightweight LLM
    call in ``_compute_semantic_interest_subcats``).

    **When ``interest_subcats`` is non-empty:**
    - Restaurants:    pass through with standard rating threshold
    - Attractions:    ONLY those whose ``sub_category`` is in
                      ``interest_subcats`` are kept. Non-matching
                      attractions are **excluded entirely**.

    **When ``interest_subcats`` is empty** (no user interests or LLM
    couldn't match): falls back to the default rating threshold (3.5)
    for all non-hotel places.
    """
    if interest_subcats is None:
        interest_subcats = set()

    center = _compute_city_center(places)
    filtered = []
    for place in places:
        # Skip hotels entirely — they are handled in the post-approval
        # HOTEL_SELECTION phase, independent of the itinerary pipeline.
        if place.get("category") == "hotel":
            continue
        # INTEREST-BASED EXCLUSION
        # When the user has interests that mapped to subcategories,
        # exclude attractions whose subcategory doesn't match entirely.
        # Only interest-relevant places should reach the scorer/planner.
        # Hotels and restaurants are NOT subject to this filter — they
        # have dedicated handling (hotels → Hotel Agent, restaurants
        # always included for food variety).
        sub_category = (place.get("sub_category") or "").lower()
        if (
            interest_subcats
            and place.get("category") != "restaurant"
            and sub_category not in interest_subcats
        ):
            continue

        # RATING FILTER - lenient threshold for interest-matching subcats
        rating = place.get("rating", 0) or 0
        min_rating = MIN_RATING_INTEREST_MATCH if sub_category in interest_subcats else MIN_RATING
        if rating < min_rating:
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
    samples_per_subcategory: int = 8,
) -> list[dict]:
    """
    Cap the number of candidates per category using per-subcategory sampling.

    Hotels are excluded entirely — they are handled independently in the
    post-approval HOTEL_SELECTION phase (like flights).
    """
    restaurants = [p for p in places if p.get("category") == "restaurant"]
    attractions = [
        p for p in places
        if p.get("category") not in ("hotel", "restaurant")
    ]

    restaurants.sort(key=lambda p: p.get("popularity_score", 0) or 0, reverse=True)

    # ── Hotels are excluded from the pipeline entirely.
    # They are handled independently in the post-approval HOTEL_SELECTION
    # phase (modeled after flight selection), so no hotel capping is needed.

    # ── Attractions: per-subcategory sampling (existing logic) ───────────
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
    # Hotels are NOT included — they are handled in the post-approval
    # HOTEL_SELECTION phase, independent of the itinerary pipeline.
    return result


async def retrieve_places(state: TripState) -> TripState:
    """
    Main Place Retriever workflow.

    The Place Retriever is responsible for finding candidate places
    that match the user's trip requirements before itinerary planning.

    Workflow:
    1. Load all available places for the destination.
    2. Run lightweight LLM semantic match to map user interests to subcategories.
    3. Apply preference-based filtering (using the matched subcategories for
       more lenient rating thresholds on interest-relevant places).
    4. Ensure a balanced mix of place categories.
    5. Store the resulting candidates + matched subcategories for the Candidate Scorer.
    """
    city = state.get("destination_city", "")
    duration_days = state.get("duration_days") or 3
    preferences = state.get("profile") or {}

    all_places = await get_places_for_city(city)
    if not all_places:
        state["filtered_places"] = []
        state["error"] = f"No places found for city: {city}"
        return state

    # ── Semantic interest-to-subcategory matching ──────────────────────
    # Run BEFORE filtering so the retriever can **exclude** non-matching
    # attractions entirely (not just apply a higher rating threshold).
    # The result is stored in state so the Candidate Scorer can reuse it
    # without a duplicate LLM call.
    profile_interests = preferences.get("interests") if preferences else None
    interest_subcats: set[str] = set()
    if profile_interests:
        subcat_names = sorted({
            (p.get("sub_category") or "").lower() or "other"
            for p in all_places
        })
        if subcat_names:
            interest_subcats = await _compute_semantic_interest_subcats(
                profile_interests, subcat_names,
            )
            logger.info(
                "[PlaceRetriever] LLM semantic interest→subcat: %d/%d subcats matched "
                "(interests=%s)",
                len(interest_subcats), len(subcat_names),
                profile_interests,
            )
    state["matched_interest_subcats"] = interest_subcats

    filtered = _apply_filters(all_places, preferences, city, interest_subcats)

    diverse = _cap_candidates(
        filtered,
        max_attractions=150,
        max_restaurants=25,
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
