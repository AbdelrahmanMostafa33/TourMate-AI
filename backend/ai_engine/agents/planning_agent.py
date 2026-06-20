"""
Planning Agent — Stage 4 of the multi-agent pipeline.

The LLM's job is to REASON, not search. It receives:
1. User request + profile summary
2. Pre-ranked candidate places (15–30 from Ranking Agent)

It produces a structured day-by-day itinerary choosing from candidates.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.graph.state import TripState
from ai_engine.profiling.behavioral_profile import profile_to_text


# System prompt that defines the Planning Agent's role, rules,
# and the exact JSON schema expected from the LLM.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured, multi-day travel itinerary.

You will receive:
1. User request (what the user wants)
2. User profile summary (preferences, interests, scores)
3. Pre-filtered candidate places (already ranked by relevance by upstream agents)

## Scoring Reference
- Each place has a `score` (0–100). Higher = more relevant to the user.
- A score above 80 is excellent; 60–80 is good; below 60 is a weaker match.
- Prefer higher-scored places when choosing between options for the same time slot.

## Planning Rules

### Stops per day
- **2–5 stops per day**. Last day can be lighter with just 2 morning stops.
- Never create empty days or "departure day" entries with no stops.
- If you have fewer candidates than needed, use fewer stops per day rather than padding with low-score places.

### Meal breaks
- **Insert a lunch break between morning and afternoon stops** (12:00–13:30).
- If a stop is a restaurant, place it at a natural meal time (lunch ~12:00, dinner ~18:00–19:00).
- Do NOT schedule 3 consecutive stops without a food break.
- `estimated_duration_minutes` for restaurants: 60–90 min.

### Time-of-day assignment
- **Morning (09:00–12:00)**: Museums, historic sites, walking tours — cooler temperatures, fewer crowds.
- **Afternoon (13:30–17:00)**: Indoor attractions, markets, shopping — avoid midday heat for outdoor sites.
- **Evening (17:00–21:00)**: Restaurants, waterfront walks, cultural shows, rooftop views.
- Avoid scheduling outdoor attractions (parks, pyramids, waterfront) in midday heat (12:00–14:00).

### Category mixing
- Mix categories: don't stack 3 of the same category in a row.
- Alternate indoor and outdoor attractions where possible.
- Use `interest_tags` on each place to verify it matches the user's interests.

### Geographic awareness
- Group nearby stops on the same day to minimize travel time.
- Consecutive stops should ideally be within 5 km of each other.
- Distance heuristic: 0.01° latitude ≈ 1.1 km; 0.01° longitude ≈ 0.9 km at 30°N.
- Place the most important/high-score attraction first in the morning when energy is highest.

### Candidate selection
- For each stop, copy `id`, `name`, `lat`, `lon`, `interest_tags` **exactly** as given — do not invent places.
- Prefer places whose `interest_tags` overlap with the user's interests.
- If a place has no matching `interest_tags`, only include it if the `score` is very high (>85).

### Hotels
- Hotels are NOT tour stops — they go in `accommodation_suggestions` at the top level.
- Pick 2–3 hotels from the hotel candidates, prioritizing those whose `accommodation_type` matches the user's accommodation preference.
- If multiple hotels match, pick the highest-rated ones covering slightly different vibes (e.g. one near pyramids, one downtown).
- Include `accommodation_type` and `amenities` in accommodation_suggestions.

### Output
- Output ONLY valid JSON, no preamble, no markdown fences.
- Every stop MUST have a `why_recommended` explaining why it fits this user (1–2 sentences, reference their interests and the place's score).
- Every accommodation suggestion MUST have a `why_recommended` explaining the choice.

JSON schema:
{
  "destination": string,
  "duration_days": integer,
  "accommodation_suggestions": [
    {
      "id": string,
      "name": string,
      "sub_category": string,
      "accommodation_type": string,
      "lat": float,
      "lon": float,
      "why_recommended": string,
      "rating": float,
      "amenities": [string]
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
          "interest_tags": [string],
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


def _trim_for_prompt(place: dict) -> dict:
    """
    Reduce a place record to only the information needed
    by the LLM for itinerary planning.
    """
    trimmed = {
        "id": place["id"],
        "name": place["name"],
        "category": place["category"],
        "sub_category": place.get("sub_category", ""),
        "interest_tags": place.get("interest_tags", []),
        "lat": place["lat"],
        "lon": place["lon"],
        "rating": place.get("rating", 0),
        "score": round(place.get("popularity_score", 0), 1),
    }
    # Include cuisine_type for restaurants so the LLM can match food preferences
    if place.get("category") == "restaurant" and place.get("cuisine_type"):
        trimmed["cuisine_type"] = place["cuisine_type"]
    # Include accommodation_type and amenities for hotels
    if place.get("category") == "hotel":
        trimmed["accommodation_type"] = place.get("accommodation_type", "")
        trimmed["amenities"] = place.get("amenities", [])
    return trimmed


async def run_planning_agent(state: TripState) -> TripState:
    """
    Main Planning Agent workflow.

    Now receives pre-ranked candidates from the Ranking Agent
    instead of doing its own candidate selection.
    """

    # Extract trip information from workflow state.
    user_message = state.get("user_message", "")
    profile = state.get("profile")
    city = state.get("destination_city")
    duration_days = state.get("duration_days", 3)

    # ---------------------------------------------------------
    # Read pre-ranked candidates from upstream agents.
    # The Retrieval Agent filtered, the Ranking Agent scored
    # and diversity-optimized. The planner just reasons over them.
    # ---------------------------------------------------------
    candidates = state.get("candidate_places") or []

    if not candidates:
        state["error"] = "Planning Agent received no candidate places from Ranking Agent"
        return state

    # Trim place objects to essential planning information.
    trimmed = [_trim_for_prompt(p) for p in candidates]

    # Convert behavioral profile into a text summary for the LLM.
    profile_summary = (
        profile_to_text(profile)
        if profile
        else "No profile available."
    )

    # Build a richer user request from profile context.
    # The raw user_message may be terse (e.g. "resort") — synthesize
    # a meaningful request from the profile so the LLM has context.
    interests = profile.get("interests") or [] if profile else []
    style = profile.get("travel_style") or "" if profile else ""
    food = profile.get("food_preferences") or [] if profile else []
    accommodation = profile.get("accommodation_preferences") or [] if profile else []

    synthesized_request = user_message
    if len(user_message.split()) <= 5 and (interests or style or food):
        # Terse request — enrich with profile context
        msg_lower = user_message.lower()
        parts = []
        if style:
            parts.append(f"{style} style")
        if interests:
            parts.append(f"interested in {', '.join(interests[:3])}")
        if food:
            parts.append(f"loves {', '.join(food[:2])}")
        # Only add accommodation if not already mentioned in user message
        if accommodation and accommodation[0].lower() not in msg_lower:
            parts.append(f"prefers {accommodation[0]}")
        if parts:
            synthesized_request = f"{user_message} ({'; '.join(parts)})"

    # Construct the user prompt.
    prompt = f"""
User Request: {synthesized_request}
Trip Duration: {duration_days} days
User Profile:
{profile_summary}

Candidate Places in {city} ({len(trimmed)} pre-filtered and ranked by relevance):
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
        response = await invoke_with_fallback("planner", messages)

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
        # Hydration: reattach full metadata for selected places.
        # ---------------------------------------------------------
        all_available = state.get("filtered_places") or candidates
        place_index = {p["id"]: p for p in all_available}

        # Enrich itinerary stops.
        for day in itinerary.get("days", []):
            for stop in day.get("stops", []):
                full = place_index.get(stop.get("id"))
                if full:
                    stop["photos"] = full.get("photos", [])[:1]
                    stop["address"] = full.get("address")
                    stop["maps_link"] = full.get("maps_link")

        # Enrich accommodation suggestions.
        for hotel in itinerary.get("accommodation_suggestions", []):
            full = place_index.get(hotel.get("id"))
            if full:
                hotel["category"] = full.get("category", "hotel")
                hotel["accommodation_type"] = full.get("accommodation_type", "")
                hotel["amenities"] = full.get("amenities", [])
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

    return state