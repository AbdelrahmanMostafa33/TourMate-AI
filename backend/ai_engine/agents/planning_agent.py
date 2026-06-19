"""
Planning Agent — Stage 4 of the multi-agent pipeline.

The LLM's job is to REASON, not search. It receives:
1. User request + profile summary
2. Pre-ranked candidate places (15–30 from Ranking Agent)

It produces a structured day-by-day itinerary choosing from candidates.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.llm_client import get_planning_llm
from ai_engine.graph.state import TripState
from ai_engine.profiling.behavioral_profile import profile_to_text


# System prompt that defines the Planning Agent's role, rules,
# and the exact JSON schema expected from the LLM.
PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Create a structured, multi-day travel itinerary.

You will receive:
1. User request
2. User profile summary
3. Pre-filtered candidate places (already ranked by relevance by upstream agents)

Rules:
- 3-5 stops per day
- Mix categories: don't stack 3 restaurants in a row
- Prefer higher `score` places when interest overlap is equal
- For each stop, copy `id`, `name`, `lat`, `lon` exactly as given
- Hotels are NOT tour stops — they go in `accommodation_suggestions` at the top level
- Pick 2-3 hotels from the hotel candidates, covering different price ranges
- Alternate indoor and outdoor attractions
- Keep total walking time reasonable (check distances between consecutive stops)
- Do not exceed 8 hours of activities per day
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


def _trim_for_prompt(place: dict) -> dict:
    """
    Reduce a place record to only the information needed
    by the LLM for itinerary planning.
    """
    return {
        "id": place["id"],
        "name": place["name"],
        "category": place["category"],
        "sub_category": place.get("sub_category", ""),
        "lat": place["lat"],
        "lon": place["lon"],
        "rating": place.get("rating", 0),
        "score": round(place.get("popularity_score", 0), 1),
    }


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

    # Initialize itinerary-planning LLM.
    llm = get_planning_llm()

    # Construct the user prompt.
    prompt = f"""
User Request: {user_message}
Trip Duration: {duration_days} days
User Profile: {profile_summary}

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