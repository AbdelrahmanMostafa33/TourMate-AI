# ai/chat/intent_parser.py

import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.llm_client import get_fast_llm
from ai_engine.graph.state import TripState


INTENT_SYSTEM_PROMPT = """
You are a travel intent classifier for TourMate AI.
Given a user message, respond ONLY with a valid JSON object — no prose, no markdown, no code fences.

JSON schema:
{
  "intent_type": "plan_trip" | "needs_clarification" | "general_chat",
  "destination_city": string | null,
  "destination_country": string | null,
  "duration_days": integer | null,
  "travel_dates": string | null,
  "group_size": integer | null,
  "special_requests": string | null,
  "budget_level": "budget" | "moderate" | "luxury" | null,
  "travel_style": "romantic" | "adventure" | "family" | "solo" | "cultural" | "relaxation" | null,
  "pace": "relaxed" | "moderate" | "packed" | null,
  "interests": list[string] | null,
  "food_preferences": list[string] | null,
  "accommodation_preferences": list[string] | null,
  "missing_fields": list[string]
}

Rules — read carefully:

1. intent_type = "plan_trip"
   ONLY when the user clearly wants an itinerary AND both destination AND duration are present.
   Example: "Plan me a 3-day trip to Cairo" → plan_trip

2. intent_type = "needs_clarification"
   When the message is clearly a travel/trip request BUT is missing destination or duration.
   Example: "I want to travel somewhere nice" → needs_clarification (destination missing)
   Example: "I want to visit Cairo" → needs_clarification (duration missing)
   Example: "Plan me a trip" → needs_clarification (both missing)

3. intent_type = "general_chat"
   For questions, greetings, opinions, or anything NOT a trip planning request.
   Example: "What's the best time to visit Egypt?" → general_chat
   Example: "Hello!" → general_chat
   Example: "Is Cairo safe?" → general_chat

4. missing_fields must list every absent required field from: "destination", "duration".
   Only include a field if the intent_type is "needs_clarification".

5. Profile fields: Extract these from the user message if mentioned:
   - budget_level: "cheap/budget-friendly" → "budget", "moderate/average" → "moderate", "luxury/5-star/premium" → "luxury"
   - travel_style: "romantic/love" → "romantic", "adventure/hiking" → "adventure", "kids/family" → "family", "solo/alone" → "solo", "museums/history" → "cultural", "relax/chill" → "relaxation"
   - pace: "see everything/packed" → "packed", "balanced" → "moderate", "relax/unhurried" → "relaxed"
   - interests: Extract interest tags like ["history", "food", "art", "nature", "shopping", "nightlife", "photography"]
   - food_preferences: Extract like ["local cuisine", "fine dining", "street food", "vegetarian", "vegan"]
   - accommodation_preferences: Extract like ["hotel", "boutique hotel", "hostel", "airbnb", "resort"]
   - All profile fields are null if not mentioned by the user.
"""


def parse_intent(user_message: str) -> dict:
    """
    Sends user_message to Llama 3.1 8B and returns a parsed intent dict.
    Falls back to a safe default if the LLM response is malformed.
    """
    llm = get_fast_llm()

    messages = [
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response = llm.invoke(messages)
        # Strip markdown fences if the model adds them despite instructions
        raw = response.content.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except (json.JSONDecodeError, AttributeError):
        # Safe fallback — treat as general chat
        return {
            "intent_type": "general_chat",
            "destination_city": None,
            "destination_country": None,
            "duration_days": None,
            "travel_dates": None,
            "group_size": None,
            "special_requests": None,
            "missing_fields": [],
        }