"""
Hotel Agent — post-optimization accommodation selection.

Placed AFTER the Route Optimizer so hotels are chosen based on actual
stop locations (daily centroids) rather than guessed before routing.

Hybrid approach:
  1. **Rule-based scoring**: preference match + proximity to daily
     centroids + rating → composite score
  2. **LLM selection**: top candidates + itinerary context sent to
     a focused LLM that picks 2-3 hotels and writes why_recommended
"""

from typing import List

from langchain_core.messages import SystemMessage, HumanMessage

from ai_engine.llm import invoke_with_fallback
from ai_engine.graph.state import TripState
from ai_engine.schemas.planning_schema import AccommodationSuggestion
from ai_engine.tools.haversine import haversine
from pydantic import BaseModel, Field


# ── Hotel Selection Output Schema ───────────────────────────────────────────


class HotelSelection(BaseModel):
    """Structured output: selected hotels for the itinerary."""
    accommodation_suggestions: List[AccommodationSuggestion] = Field(
        default_factory=list,
        description="2-3 selected hotel recommendations",
    )


# ── Scoring Weights ──────────────────────────────────────────────────────────

WEIGHT_PREFERENCE = 0.35  # accommodation_type matches user preference
WEIGHT_PROXIMITY   = 0.40  # proximity to daily centroids
WEIGHT_RATING      = 0.25  # hotel rating

# ── LLM Prompt ───────────────────────────────────────────────────────────────

HOTEL_SYSTEM_PROMPT = """\
You are the Hotel Selection Agent for TourMate AI. Your job: choose 2–3 hotels
for the user's trip and write a short why_recommended for each.

You will receive:
1. Itinerary summary — days with themes and the approximate location centroids
2. Candidate hotels — pre-scored for preference match, proximity, and rating
3. User preferences — accommodation type, budget, travel style

Rules:
- Pick 2–3 hotels that collectively offer variety (e.g. one near Day 1's
  centroid, one near Day 2's centroid, or different vibes/locations).
- Prefer hotels whose accommodation_type matches the user's preference.
- If multiple hotels match, favor higher-rated ones.
- Every hotel MUST have a why_recommended (1–2 sentences explaining
  why it fits this itinerary and user).
- Only pick from the candidate hotels listed — do NOT invent hotels.

Output schema is enforced automatically — fill all fields.
"""


# ── Proximity Scoring ────────────────────────────────────────────────────────


def _compute_daily_centroids(itinerary: dict) -> list[dict]:
    """Compute the geographic centroid of each day's stops.

    Returns a list of dicts: [{day_number, centroid_lat, centroid_lon, n_stops}]
    """
    centroids = []
    for day in itinerary.get("days", []):
        stops = day.get("stops", [])
        if not stops:
            continue
        lat_sum = sum(s.get("lat", 0) for s in stops)
        lon_sum = sum(s.get("lon", 0) for s in stops)
        n = len(stops)
        centroids.append({
            "day_number": day.get("day_number"),
            "centroid_lat": lat_sum / n,
            "centroid_lon": lon_sum / n,
            "n_stops": n,
        })
    return centroids


def _score_preference_match(hotel: dict, preferences: List[str]) -> float:
    """Score how well the hotel's accommodation_type matches user preferences."""
    hotel_type = (hotel.get("accommodation_type") or "").lower().strip()
    if not hotel_type or not preferences:
        return 0.5  # neutral

    for pref in preferences:
        pref_lower = pref.lower().strip()
        if pref_lower in hotel_type or hotel_type in pref_lower:
            return 1.0
    return 0.0


def _score_proximity_to_centroids(
    hotel: dict,
    centroids: list[dict],
) -> float:
    """Score hotel proximity as the weighted inverse of distance to centroids.

    Closer to more stops = higher score.
    Returns 0–1.
    """
    if not centroids:
        return 0.5

    total_stops = sum(c["n_stops"] for c in centroids)
    weighted_dist = 0.0
    for c in centroids:
        dist = haversine(
            hotel["lat"], hotel["lon"],
            c["centroid_lat"], c["centroid_lon"],
        )
        weight = c["n_stops"] / total_stops
        # Inverse: 10 km → ~0.8, 50 km → ~0.0
        proximity = max(0.0, 1.0 - (dist / 50.0))
        weighted_dist += weight * proximity

    return weighted_dist


def _score_rating(hotel: dict) -> float:
    """Normalize hotel rating (1–5) → 0–1."""
    rating = hotel.get("rating", 3.0) or 3.0
    return min(max((rating - 1.0) / 4.0, 0.0), 1.0)


def _compute_hotel_composite(
    hotel: dict,
    centroids: list[dict],
    preferences: List[str],
) -> float:
    """Compute composite score for a hotel candidate."""
    pref_score = _score_preference_match(hotel, preferences)
    prox_score = _score_proximity_to_centroids(hotel, centroids)
    rating_score = _score_rating(hotel)

    composite = (
        pref_score * WEIGHT_PREFERENCE
        + prox_score * WEIGHT_PROXIMITY
        + rating_score * WEIGHT_RATING
    )
    return round(composite, 4)


# ── Main Agent Function ──────────────────────────────────────────────────────


async def run_hotel_selection(state: TripState) -> TripState:
    """Run the Hotel Agent — select 2-3 hotels based on optimized itinerary.

    Reads from ``state["optimized_itinerary"]`` and ``state["candidate_places"]``,
    writes to ``state["draft_itinerary"]["accommodation_suggestions"]``.

    Args:
        state: LangGraph workflow state (post-optimization).

    Returns:
        State with ``accommodation_suggestions`` populated on the itinerary.
    """
    itinerary = state.get("optimized_itinerary") or state.get("draft_itinerary")
    if not itinerary:
        print("[HotelAgent] No itinerary to select hotels for")
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + ["[HotelAgent] No itinerary — skipping hotel selection"]
        )
        return state

    # ── Hotel candidates ─────────────────────────────────────────────────
    candidates = state.get("candidate_places") or []
    hotel_candidates = [
        p for p in candidates
        if p.get("category") == "hotel" and p.get("id")
    ]

    if not hotel_candidates:
        print("[HotelAgent] No hotel candidates available")
        itinerary["accommodation_suggestions"] = []
        state["agent_messages"] = (
            state.get("agent_messages", [])
            + ["[HotelAgent] No hotel candidates — accommodation left empty"]
        )
        return state

    # ── User preferences ─────────────────────────────────────────────────
    profile = state.get("profile") or {}
    pref_list: list[str] = profile.get("accommodation_preferences") or []
    budget = profile.get("budget_level") or ""
    style = profile.get("travel_style") or ""

    # ── Filter by accommodation type when user has a specific preference ──
    # Rather than just scoring preferred types higher, we EXCLUDE non-matching
    # types so the user's explicit request (e.g. "hostels instead of hotels")
    # is honored even when hotels have higher proximity or rating scores.
    if pref_list:
        canonical_pref = pref_list[0].lower().strip()
        before = len(hotel_candidates)
        hotel_candidates = [
            p for p in hotel_candidates
            if canonical_pref in (p.get("accommodation_type") or "").lower()
            or (p.get("accommodation_type") or "").lower() in canonical_pref
        ]
        after = len(hotel_candidates)
        if after == 0:
            print(f"[HotelAgent] No candidates matching preference '{canonical_pref}' in current pool — re-querying database")
            # Re-query database for specific accommodation type
            from ai_engine.tools.places_tool import get_places_for_city
            city = itinerary.get("destination", "")
            if city:
                all_places = await get_places_for_city(city)
                if all_places:
                    hotel_candidates = [
                        p for p in all_places
                        if p.get("category") == "hotel" 
                        and p.get("id")
                        and (
                            canonical_pref in (p.get("accommodation_type") or "").lower()
                            or (p.get("accommodation_type") or "").lower() in canonical_pref
                        )
                    ]
                    after = len(hotel_candidates)
                    if after > 0:
                        print(f"[HotelAgent] Re-queried database: found {after} hotels matching '{canonical_pref}'")
                    else:
                        print(f"[HotelAgent] No hotels matching '{canonical_pref}' found in database — falling back to all hotels")
                        hotel_candidates = [
                            p for p in candidates
                            if p.get("category") == "hotel" and p.get("id")
                        ]
        else:
            print(f"[HotelAgent] Filtered to {after}/{before} candidates matching '{canonical_pref}'")

    # ── Daily centroids ──────────────────────────────────────────────────
    centroids = _compute_daily_centroids(itinerary)
    print(f"[HotelAgent] Computing centroids for {len(centroids)} days")

    # ── Score each hotel ──────────────────────────────────────────────────
    scored_hotels = []
    for hotel in hotel_candidates:
        composite = _compute_hotel_composite(hotel, centroids, pref_list)
        scored_hotels.append((hotel, composite))

    scored_hotels.sort(key=lambda x: x[1], reverse=True)

    # Take top 6 for LLM consideration
    top_candidates = scored_hotels[:6]

    # ── If we have very few candidates, skip LLM and use rules directly ──
    # This saves an LLM call when there's little to choose between.
    SKIP_LLM_THRESHOLD = 3
    if len(top_candidates) <= SKIP_LLM_THRESHOLD:
        selected = []
        for hotel, score in top_candidates:
            acc_type = hotel.get("accommodation_type", "")
            acc_display = acc_type.capitalize() if acc_type else "Accommodation"
            selected.append({
                "id": hotel["id"],
                "name": hotel["name"],
                "sub_category": hotel.get("sub_category", ""),
                "accommodation_type": acc_type,
                "lat": hotel["lat"],
                "lon": hotel["lon"],
                "why_recommended": (
                    f"This {acc_display} is highly-rated and conveniently "
                    f"located near your daily route."
                ),
                "rating": hotel.get("rating", 0),
                "amenities": hotel.get("amenities", []),
            })
        print(
            f"[HotelAgent] Rule-based selection ({len(selected)} candidates): "
            f"{[h['name'] for h in selected]}"
        )
    else:
        # ── LLM-based selection ──────────────────────────────────────────
        selected = await _llm_select_hotels(
            itinerary=itinerary,
            centroids=centroids,
            top_candidates=top_candidates,
            preferences=pref_list,
            budget=budget,
            style=style,
        )

    # ── Hydrate with full metadata ───────────────────────────────────────
    place_index = {p["id"]: p for p in hotel_candidates}
    for hotel in selected:
        full = place_index.get(hotel["id"])
        if full:
            hotel.setdefault("accommodation_type", full.get("accommodation_type", ""))
            hotel.setdefault("amenities", full.get("amenities", []))
            hotel.setdefault("photos", (full.get("photos") or [])[:1])
            hotel.setdefault("address", full.get("address"))
            hotel.setdefault("maps_link", full.get("maps_link"))
            hotel.setdefault("category", "hotel")

    # ── Store on itinerary ──────────────────────────────────────────────
    itinerary["accommodation_suggestions"] = selected

    print(
        f"[HotelAgent] Selected {len(selected)} hotels from {len(hotel_candidates)} candidates: "
        f"{[h['name'] for h in selected]}"
    )
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[HotelAgent] {len(selected)}/{len(hotel_candidates)} hotels selected"]
    )

    return state


# ── LLM Selection ────────────────────────────────────────────────────────────


async def _llm_select_hotels(
    itinerary: dict,
    centroids: list[dict],
    top_candidates: list[tuple[dict, float]],
    preferences: list[str],
    budget: str,
    style: str,
) -> list[dict]:
    """Use LLM to select 2-3 hotels from pre-scored candidates."""
    # Build itinerary context
    days_summary = []
    for day in itinerary.get("days", []):
        centroid = next(
            (c for c in centroids if c["day_number"] == day.get("day_number")),
            None,
        )
        centroid_str = (
            f"~({centroid['centroid_lat']:.3f}, {centroid['centroid_lon']:.3f})"
            if centroid else "unknown"
        )
        stops_list = [s.get("name", "?") for s in day.get("stops", [])]
        days_summary.append(
            f"  Day {day.get('day_number')} — {day.get('theme', '')}\n"
            f"    Centroid: {centroid_str}\n"
            f"    Stops: {', '.join(stops_list[:5])}"
        )

    # Build hotel list
    hotel_lines = []
    for hotel, score in top_candidates:
        acc_type = hotel.get("accommodation_type", "")
        rating = hotel.get("rating", 0)
        lat = hotel.get("lat", 0)
        lon = hotel.get("lon", 0)
        hotel_lines.append(
            f"  • {hotel['name']} (id={hotel['id']})\n"
            f"    Type: {acc_type} | Rating: {rating} | Score: {score:.3f}\n"
            f"    Location: ({lat:.4f}, {lon:.4f})"
        )

    pref_str = ", ".join(preferences) if preferences else "no preference"
    prompt = f"""\
Itinerary Summary:
{chr(10).join(days_summary)}

User Preferences:
  Accommodation: {pref_str}
  Budget: {budget or "not specified"}
  Travel Style: {style or "not specified"}

Scored Hotel Candidates ({len(top_candidates)}):
{chr(10).join(hotel_lines)}

Select 2-3 hotels that best fit this itinerary and user.
Consider: proximity to daily centroids, accommodation type match, rating, and variety.
"""

    messages = [
        SystemMessage(content=HOTEL_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        # Use structured output for reliable parsing
        response: HotelSelection = await invoke_with_fallback(
            "hotel_selector",
            messages,
            structured_output=HotelSelection,
        )

        if response and response.accommodation_suggestions:
            return [
                h.model_dump() for h in response.accommodation_suggestions
            ]

        print("[HotelAgent] LLM returned empty selection — using rule fallback")
    except Exception as exc:
        print(f"[HotelAgent] LLM selection failed ({exc}) — using rule fallback")

    # Fallback: return top 2-3 by composite score
    return [
        {
            "id": hotel["id"],
            "name": hotel["name"],
            "sub_category": hotel.get("sub_category", ""),
            "accommodation_type": hotel.get("accommodation_type", ""),
            "lat": hotel["lat"],
            "lon": hotel["lon"],
            "why_recommended": (
                f"Top-rated {hotel.get('accommodation_type', 'accommodation')} "
                f"with great proximity to your daily route."
            ),
            "rating": hotel.get("rating", 0),
            "amenities": hotel.get("amenities", []),
        }
        for hotel, _ in top_candidates[:3]
    ]
