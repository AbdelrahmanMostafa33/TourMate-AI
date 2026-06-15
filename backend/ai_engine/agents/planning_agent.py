import json
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.groq_client import get_planning_llm
from ai_engine.graph.state import TripState
from ai_engine.tools.places_tool import get_places_for_city
from ai_engine.profiling.behavioral_profile import profile_to_text

PLANNER_SYSTEM_PROMPT = """
You are the Planning Agent for TourMate AI. Your goal is to create a raw, multi-day travel itinerary based on the user's request and their behavioral profile.

You will be provided with:
1. User message: The raw request from the user.
2. User profile: A summary of the user's travel preferences.
3. Available places: A list of points of interest (POIs) in the destination city.

Your task:
- Create a day-by-day itinerary for the requested duration.
- Each day should have 3-5 stops.
- Select places from the provided "Available places" list that best match the user's interests.
- Respond ONLY with a valid JSON object.

JSON schema:
{{
  "destination": string,
  "duration_days": integer,
  "days": [
    {{
      "day_number": integer,
      "theme": string,
      "stops": [
        {{
          "name": string,
          "category": string,
          "lat": float,
          "lon": float,
          "description": string,
          "estimated_duration_minutes": integer
        }}
      ]
    }}
  ]
}}
"""


async def run_planning_agent(state: TripState) -> TripState:
    """
    Implementation of the Planning Agent.
    """
    user_message = state.get("user_message", "")
    profile = state.get("profile")
    city = state.get("destination_city", "Cairo")
    interests = profile.get("interests", []) if profile else []

    # Get places for the city
    available_places = get_places_for_city(city, interests=interests)

    profile_summary = profile_to_text(profile) if profile else "No profile available."

    llm = get_planning_llm()

    prompt = f"""
    User Request: {user_message}
    User Profile Summary:
    {profile_summary}

    Available Places in {city}:
    {json.dumps(available_places, indent=2)}

    Generate the itinerary now.
    """

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw_content = response.content.strip().strip("```json").strip("```").strip()
        itinerary = json.loads(raw_content)
        state["draft_itinerary"] = itinerary
        state["planning_attempts"] = state.get("planning_attempts", 0) + 1
    except Exception as e:
        state["error"] = f"Planning Agent failed: {str(e)}"

    return state
