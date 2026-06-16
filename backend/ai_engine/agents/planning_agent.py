import json
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.llm_client import get_planning_llm
from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city
from ai_engine.tools.haversine import haversine
from ai_engine.profiling.behavioral_profile import profile_to_text

# System prompt that defines the Planning Agent's role, rules,
# and the exact JSON schema expected from the LLM.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured, multi-day travel itinerary.

You will receive:
1. User request
2. User profile summary
3. Pre-filtered candidate places (already ranked by relevance)

Rules:
- 3-5 stops per day
- Mix categories: don't stack 3 restaurants in a row
- Prefer higher `score` places when interest overlap is equal
- For each stop, copy `id`, `name`, `lat`, `lon` exactly as given
- Hotels are NOT tour stops — they go in `accommodation_suggestions` at the top level
- Pick 2-3 hotels from the hotel candidates, covering different price ranges
- Output ONLY valid JSON, no preamble

JSON schema:
{
  "destination": string,
  "duration_days": integer,
  "accommodation_suggestions": [
    {
      "id": string,
      "name": string,
      "sub_category": string,
      "lat": float,
      "lon": float,
      "why_recommended": string,
      "rating": float
    }
  ],
  "days": [
    {
      "day_number": integer,
      "theme": string,
      "stops": [
        {
          "id": string,
          "name": string,
          "category": string,
          "sub_category": string,
          "lat": float,
          "lon": float,
          "why_recommended": string,
          "estimated_duration_minutes": integer,
          "suggested_time_of_day": "morning" | "afternoon" | "evening"
        }
      ]
    }
  ]
}
"""


def _score_place(
    place: dict,
    user_interests: list[str],
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
) -> float:
    """
    Compute a composite relevance score for a place before sending it
    to the LLM.

    Score components:
    - Interest overlap with user preferences
    - User rating
    - Popularity score
    - Proximity bonus (closer to destination center = higher score)

    Higher score = more likely to be included in candidate set.
    """
    interest_tags = set(place.get("interest_tags", []))
    user_tags = set(user_interests)

    # Count matching interest tags between user and place.
    tag_overlap = len(interest_tags & user_tags)

    # Use fallback values if data is missing.
    rating = place.get("rating", 3.0) or 3.0
    popularity = place.get("popularity_score", 0) or 0

    # Base weighted scoring formula.
    score = (tag_overlap * 3.0) + (rating * 1.5) + (popularity * 0.02)

    # Proximity bonus: prefer places closer to the destination center.
    # Hotels are excluded from proximity scoring since they can be
    # anywhere in the city — users pick hotels based on preference,
    # not centrality.
    if center_lat is not None and center_lon is not None:
        if place.get("category") != "hotel":
            dist_km = haversine(center_lat, center_lon, place["lat"], place["lon"])
            # Bonus: up to +5 points for places within 10 km of center.
            # Penalizes: -0.3 points per km beyond 15 km.
            if dist_km <= 10:
                score += 5.0
            elif dist_km <= 15:
                score += 3.0
            else:
                score -= (dist_km - 15) * 0.3

    return score


def _select_candidates(
    places: list[dict],
    user_interests: list[str],
    duration_days: int,
    max_per_category: dict = None,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
) -> list[dict]:
    """
    Select a balanced subset of places for the LLM.

    Purpose:
    - Reduce prompt size.
    - Keep only the most relevant places.
    - Maintain category diversity (attractions, restaurants, hotels).
    - Prefer places closer to the destination center.

    The LLM receives only these candidates and chooses the final itinerary.
    """
    if max_per_category is None:
        # Buffer allows the LLM to have multiple choices
        # for each itinerary slot.
        # Keep total candidates under ~15 to stay within the
        # LLM token limit.
        max_per_category = {
            "attractions": duration_days * 4,
            "restaurant": duration_days * 2,

            # Hotel candidates are intentionally limited because
            # only a few accommodation suggestions are needed.
            "hotel": duration_days + 1,

            # Default cap for any unlisted category.
            "_default": duration_days + 1,
        }

    # Score every place based on relevance + proximity.
    scored = [(p, _score_place(p, user_interests, center_lat, center_lon)) for p in places]

    # Highest-scoring places first.
    scored.sort(key=lambda x: x[1], reverse=True)

    # Group selected places by category.
    by_category: dict[str, list] = {}

    for place, score in scored:
        cat = place.get("category", "other")

        if cat not in by_category:
            by_category[cat] = []

        # Maximum allowed places for this category.
        cap = max_per_category.get(cat, max_per_category.get("_default", duration_days + 1))

        # Keep only top places up to the category cap.
        if len(by_category[cat]) < cap:
            by_category[cat].append((place, score))

    # Flatten grouped results into a single candidate list.
    candidates = []
    for cat, items in by_category.items():
        candidates.extend(items)

    # Return only place objects, discard score values.
    return [p for p, _ in candidates]


def _trim_for_prompt(place: dict) -> dict:
    """
    Reduce a place record to only the information needed
    by the LLM for itinerary planning.

    This helps:
    - Reduce token usage.
    - Keep prompts focused.
    - Improve model efficiency.
    """
    return {
        "id": place["id"],
        "name": place["name"],
        "category": place["category"],
        "sub_category": place.get("sub_category", ""),
        "lat": place["lat"],
        "lon": place["lon"],
        "rating": place.get("rating", 0),

        # Popularity score exposed to LLM as "score"
        # for ranking decisions.
        "score": round(place.get("popularity_score", 0), 1),
    }


async def run_planning_agent(state: TripState) -> TripState:
    """
    Main Planning Agent workflow.

    Responsibilities:
    1. Load trip context from state.
    2. Retrieve candidate places.
    3. Pre-filter and rank places.
    4. Send planning request to the LLM.
    5. Parse returned itinerary.
    6. Enrich selected places with full metadata.
    7. Store final draft itinerary back into state.
    """

    # Extract trip information from workflow state.
    user_message = state.get("user_message", "")
    profile = state.get("profile")
    city = state.get("destination_city")
    duration_days = state.get("duration_days", 3)

    # Extract user interests from behavioral profile.
    interests = profile.get("interests", []) if profile else []

    # Retrieve all available places for the destination city.
    available_places = get_places_for_city(city, interests=interests)

    # -------------------------------------------------------------
    # Compute destination center for proximity scoring.
    # Use the centroid of all non-hotel places as the "center" of
    # the destination. This ensures candidate places are geographically
    # clustered, preventing the LLM from picking stops on opposite
    # sides of the city.
    # -------------------------------------------------------------
    non_hotel = [p for p in available_places if p.get("category") != "hotel"]
    if non_hotel:
        center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)
        center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)
    else:
        center_lat = None
        center_lon = None

    # -------------------------------------------------------------
    # Stage 1: Candidate Selection
    # -------------------------------------------------------------
    # Reduce the full dataset to a manageable set of relevant places.
    candidates = _select_candidates(
        available_places,
        interests,
        duration_days,
        center_lat=center_lat,
        center_lon=center_lon,
    )

    # Trim place objects to essential planning information.
    trimmed = [_trim_for_prompt(p) for p in candidates]

    # Convert behavioral profile into a text summary for the LLM.
    profile_summary = (
        profile_to_text(profile)
        if profile
        else "No profile available."
    )

    # Initialize itinerary-planning LLM.
    llm = get_planning_llm()

    # Construct the user prompt.
    prompt = f"""
User Request: {user_message}
Trip Duration: {duration_days} days
User Profile: {profile_summary}

Candidate Places in {city} ({len(trimmed)} pre-filtered by relevance to user interests):
{json.dumps(trimmed, indent=2, ensure_ascii=False)}

Generate the itinerary now.
"""

    # LangChain message structure.
    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        # Ask the LLM to generate the itinerary.
        response = llm.invoke(messages)

        # Remove possible markdown code fences around JSON output.
        raw = (
            response.content
            .strip()
            .strip("```json")
            .strip("```")
            .strip()
        )

        # Parse LLM output into Python dictionary.
        itinerary = json.loads(raw)

        # ---------------------------------------------------------
        # Stage 2: Hydration
        # ---------------------------------------------------------
        # The LLM only received trimmed place records.
        # Reattach full metadata for selected places.
        place_index = {
            p["id"]: p
            for p in available_places
        }

        # Enrich itinerary stops.
        for day in itinerary.get("days", []):
            for stop in day.get("stops", []):

                full = place_index.get(stop.get("id"))

                if full:
                    # Add supporting information for UI rendering.
                    stop["photos"] = full.get("photos", [])[:1]
                    stop["address"] = full.get("address")
                    stop["maps_link"] = full.get("maps_link")

        # Enrich accommodation suggestions.
        for hotel in itinerary.get(
            "accommodation_suggestions",
            []
        ):
            full = place_index.get(hotel.get("id"))

            if full:
                hotel["category"] = full.get(
                    "category",
                    "hotel",
                )
                hotel["photos"] = full.get("photos", [])[:1]
                hotel["address"] = full.get("address")
                hotel["maps_link"] = full.get("maps_link")

        # Store successful itinerary in workflow state.
        state["draft_itinerary"] = itinerary

        # Track how many planning attempts have been made.
        state["planning_attempts"] = (
            state.get("planning_attempts", 0) + 1
        )

    except Exception as e:
        # Store failure reason so downstream agents can react.
        state["error"] = (
            f"Planning Agent failed: {str(e)}"
        )

    # Return updated workflow state.
    return state