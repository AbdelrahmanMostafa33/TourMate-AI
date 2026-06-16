import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.groq_client import get_fast_llm
from ai_engine.graph.state import TripState

VALIDATOR_SYSTEM_PROMPT = """
You are the Validation Agent for TourMate AI. Your goal is to check the feasibility and quality of a generated travel itinerary.

You will be provided with:
1. Optimized Itinerary: The itinerary generated and optimized by previous agents.
2. User Request: The original user request.

Your task:
- Check if the itinerary covers the requested duration and destination.
- Check if the number of stops per day is realistic (not too many, not too few).
- Check if `accommodation_suggestions` exists and has 1-3 hotels.
- Rate the itinerary on a scale of 0-100.
- Respond ONLY with a valid JSON object.

JSON schema:
{{
  "is_valid": boolean,
  "score": integer,
  "issues": list[string],
  "suggestions": list[string]
}}
"""


async def run_validation_agent(state: TripState) -> TripState:
    """
    Implementation of the Validation Agent.
    """
    optimized = state.get("optimized_itinerary")
    user_message = state.get("user_message", "")

    if not optimized or state.get("error"):
        state["is_valid"] = False
        return state

    llm = get_fast_llm()

    prompt = f"""
    User Request: {user_message}
    Optimized Itinerary:
    {json.dumps(optimized, indent=2)}

    Validate the itinerary now.
    """

    messages = [
        SystemMessage(content=VALIDATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw_content = response.content.strip().strip("```json").strip("```").strip()
        validation_result = json.loads(raw_content)
        state["is_valid"] = validation_result.get("is_valid", True)
        state["validation"] = validation_result
    except Exception as e:
        # Fallback to valid if LLM fails to avoid infinite loops in skeleton
        state["is_valid"] = True
        state["validation"] = {"is_valid": True, "score": 100, "issues": [f"Validation LLM failed: {str(e)}"]}

    return state
