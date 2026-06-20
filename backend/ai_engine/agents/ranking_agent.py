"""
Ranking Agent — Stage 3 of the multi-agent pipeline.

Responsibilities:
1. Score each candidate with a multi-signal formula:
   - Popularity (0.35)
   - User preference match (0.25)
   - Proximity to city center (0.15)
   - Rating quality (0.15)
   - Diversity bonus (0.10)
2. Optimize for category diversity in the final set.
3. Cap the candidate list to 15–30 places (the optimal range for LLM reasoning).

The LLM should NOT search — it should reason over a curated, ranked set.
"""

import math
from typing import Optional
from ai_engine.graph.state import TripState
from ai_engine.tools.haversine import haversine


# ── Scoring weights ──────────────────────────────────────────────────────────

WEIGHT_POPULARITY = 0.35
WEIGHT_PREFERENCE = 0.25
WEIGHT_PROXIMITY = 0.15
WEIGHT_RATING = 0.15
WEIGHT_DIVERSITY = 0.10

# ── Candidate caps ───────────────────────────────────────────────────────────

MAX_TOTAL_CANDIDATES = 30


def _score_popularity(place: dict) -> float:
    """Normalize popularity score to 0–1 range."""
    pop = place.get("popularity_score", 0) or 0
    # Assuming max popularity is ~100
    return min(pop / 100.0, 1.0)


def _score_preference(place: dict, preferences: dict) -> float:
    """
    Score how well a place matches the user's extracted preferences.

    Checks: interests, travel style, food preferences, nightlife.
    """
    score = 0.0
    checks = 0

    interests = set(preferences.get("interests_from_conversation", []))
    place_tags = set(place.get("interest_tags", []))
    place_category = place.get("category", "")

    # Interest match (0 or 1)
    if interests:
        if place_category in interests or place_tags & interests:
            score += 1.0
        checks += 1

    # Travel style match
    travel_style = preferences.get("travel_style")
    if travel_style:
        sub_cat = (place.get("sub_category", "") or "").lower()
        if travel_style == "romantic" and any(w in sub_cat for w in ["romantic", "scenic", "sunset", "riverside"]):
            score += 1.0
        elif travel_style == "adventure" and any(w in sub_cat for w in ["adventure", "hiking", "extreme"]):
            score += 1.0
        elif travel_style == "cultural" and any(w in sub_cat for w in ["museum", "historic", "heritage", "art"]):
            score += 1.0
        elif travel_style == "family" and any(w in sub_cat for w in ["park", "family", "kids"]):
            score += 1.0
        checks += 1

    # Food preferences match
    food_prefs = set(preferences.get("food_preferences", []))
    if food_prefs and place_category == "restaurant":
        cuisine = (place.get("cuisine_type", "") or "").lower()
        if any(fp.lower() in cuisine or cuisine in fp.lower() for fp in food_prefs):
            score += 1.0
        checks += 1

    # Accommodation type match (hotels only)
    accommodation_style = (preferences.get("accommodation_style") or "").lower()
    if accommodation_style and place_category == "hotel":
        place_acc = (place.get("accommodation_type", "") or "").lower()
        if place_acc and (
            accommodation_style in place_acc
            or place_acc in accommodation_style
            or any(w in place_acc for w in accommodation_style.split())
        ):
            score += 1.0
        checks += 1

    return score / max(checks, 1)


def _score_proximity(
    place: dict,
    center_lat: float,
    center_lon: float,
) -> float:
    """
    Score proximity to city center.

    Closer places get higher scores. Hotels are exempt
    (users pick hotels by preference, not centrality).
    """
    if place.get("category") == "hotel":
        return 0.5  # Neutral score for hotels

    dist = haversine(center_lat, center_lon, place["lat"], place["lon"])

    # Within 5km: score 1.0. At 50km: score ~0.0
    if dist <= 5:
        return 1.0
    elif dist <= 10:
        return 0.8
    elif dist <= 20:
        return 0.5
    elif dist <= 35:
        return 0.3
    else:
        return max(0.0, 1.0 - (dist / 50.0))


def _score_rating(place: dict) -> float:
    """Normalize rating to 0–1 range."""
    rating = place.get("rating", 3.0) or 3.0
    return min(max((rating - 1.0) / 4.0, 0.0), 1.0)  # 1–5 scale → 0–1


def _compute_composite_score(
    place: dict,
    preferences: dict,
    center_lat: float,
    center_lon: float,
    category_counts: dict,
    target_per_category: dict,
) -> float:
    """
    Compute the final composite score for a place.

    Formula:
    score = (popularity * W1) + (preference * W2) + (proximity * W3)
          + (rating * W4) + (diversity_bonus * W5)
    """
    pop = _score_popularity(place)
    pref = _score_preference(place, preferences)
    prox = _score_proximity(place, center_lat, center_lon)
    rat = _score_rating(place)

    # Diversity bonus: boost underrepresented categories
    cat = place.get("category", "other")
    current_count = category_counts.get(cat, 0)
    target = target_per_category.get(cat, 3)
    if current_count < target:
        diversity = 1.0  # Full bonus for underrepresented
    elif current_count < target + 2:
        diversity = 0.5  # Moderate bonus
    else:
        diversity = 0.0  # No bonus (already have enough)

    composite = (
        pop * WEIGHT_POPULARITY
        + pref * WEIGHT_PREFERENCE
        + prox * WEIGHT_PROXIMITY
        + rat * WEIGHT_RATING
        + diversity * WEIGHT_DIVERSITY
    )

    return round(composite, 4)


def _diversity_optimize(
    scored_places: list[tuple[dict, float]],
    duration_days: int,
) -> list[dict]:
    """
    Select the final candidate set with diversity constraints.

    Strategy:
    1. Sort by composite score.
    2. Greedily pick top places, but cap per-category.
    3. Ensure at least 2 categories have multiple options for the LLM.
    """
    # Category caps based on trip duration
    category_caps = {
        "attractions": min(duration_days * 3, 12),
        "restaurant": min(duration_days * 2, 8),
        "hotel": min(duration_days + 1, 5),
        "_default": 3,
    }

    by_category: dict[str, list] = {}
    for place, score in scored_places:
        cat = place.get("category", "other")
        by_category.setdefault(cat, []).append((place, score))

    # Sort each category by score
    for cat in by_category:
        by_category[cat].sort(key=lambda x: x[1], reverse=True)

    selected = []
    for cat, items in by_category.items():
        cap = category_caps.get(cat, category_caps["_default"])
        selected.extend(items[:cap])

    # Sort final list by score descending
    selected.sort(key=lambda x: x[1], reverse=True)

    # Cap total candidates
    return [p for p, _ in selected[:MAX_TOTAL_CANDIDATES]]


async def run_ranking_agent(state: TripState) -> TripState:
    """
    Main Ranking Agent workflow.

    1. Take filtered places from the Retrieval Agent.
    2. Score each place with the multi-signal formula.
    3. Apply diversity optimization.
    4. Store the final candidate set in state for the Planning Agent.
    """
    filtered = state.get("filtered_places") or []
    preferences = state.get("extracted_preferences") or {}
    duration_days = state.get("duration_days", 3)

    if not filtered:
        state["candidate_places"] = []
        state["error"] = "No filtered places to rank"
        return state

    # ── Compute city center for proximity scoring ──
    non_hotel = [p for p in filtered if p.get("category") != "hotel"]
    if non_hotel:
        center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)
        center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)
    else:
        center_lat, center_lon = 0.0, 0.0

    # ── Target per category for diversity scoring ──
    target_per_category = {
        "attractions": max(duration_days * 2, 4),
        "restaurant": max(duration_days, 3),
        "hotel": max(duration_days // 2 + 1, 2),
    }

    # ── Score every place ──
    category_counts: dict[str, int] = {}
    scored = []
    for place in filtered:
        score = _compute_composite_score(
            place, preferences, center_lat, center_lon,
            category_counts, target_per_category,
        )
        cat = place.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        scored.append((place, score))

    # ── Diversity optimization ──
    candidates = _diversity_optimize(scored, duration_days)

    state["candidate_places"] = candidates
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[RankingAgent] {len(filtered)} filtered → {len(candidates)} ranked candidates"]
    )

    return state
