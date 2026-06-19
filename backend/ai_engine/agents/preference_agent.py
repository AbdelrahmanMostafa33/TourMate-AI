"""
Preference Agent — Stage 1 of the multi-agent pipeline.

Extracts structured travel preferences from:
1. The user's natural language message
2. The loaded behavioral profile (from onboarding quiz)

Outputs a structured dict that downstream agents (Retrieval, Ranking)
use as filter criteria and scoring signals.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from app.external.llm_client import get_fast_llm
from ai_engine.graph.state import TripState, BehavioralProfile
from ai_engine.profiling.behavioral_profile import get_budget_label


PREFERENCE_EXTRACTION_PROMPT = """
You are the Preference Agent for TourMate AI. Your job is to extract
structured travel preferences from the user's message and profile.

You will receive:
1. User message — what the user said
2. User profile — behavioral data from onboarding quiz (may be partial)

Extract and return a JSON object with these fields:

{
  "budget_level": "budget" | "moderate" | "luxury" | null,
  "travel_style": "romantic" | "adventure" | "family" | "business" | "solo" | "cultural" | "relaxation" | null,
  "walking_tolerance": "low" | "medium" | "high" | null,
  "food_preferences": ["local cuisine", "fine dining", ...],
  "accommodation_style": "hotel" | "boutique" | "hostel" | "airbnb" | "resort" | null,
  "nightlife": "low" | "medium" | "high" | null,
  "interests_from_conversation": ["history", "art", ...],
  "pace": "packed" | "balanced" | "relaxed" | null,
  "special_focus": string | null
}

Rules:
- Infer from the user message FIRST. Only fall back to profile if message is unclear.
- If the user says "romantic" → travel_style = "romantic"
- If the user says "budget-friendly" or "cheap" → budget_level = "budget"
- If the user says "luxury" or "5-star" → budget_level = "luxury"
- If the user says "I love walking" → walking_tolerance = "high"
- If no signal exists for a field, set it to null (don't guess)
- special_focus is any unusual request (e.g., "kid-friendly", "accessible", "photo spots")
- Respond ONLY with valid JSON, no preamble
"""


def _build_profile_context(profile: BehavioralProfile) -> str:
    """Convert behavioral profile into context text for the LLM."""
    lines = []

    if profile.get("persona_name"):
        lines.append(f"Persona: {profile['persona_name']}")

    budget_label = get_budget_label(profile.get("budget_level"))
    lines.append(f"Budget tendency: {budget_label}")

    if profile.get("interests"):
        lines.append(f"Stated interests: {', '.join(profile['interests'])}")

    if profile.get("dining_preferences"):
        lines.append(f"Dining preferences: {', '.join(profile['dining_preferences'])}")

    if profile.get("accommodation_styles"):
        lines.append(f"Accommodation preferences: {', '.join(profile['accommodation_styles'])}")

    if profile.get("travel_companion"):
        lines.append(f"Travel companion: {profile['travel_companion']}")

    if profile.get("adventure_relaxing") is not None:
        val = profile["adventure_relaxing"]
        style = "adventurous" if val >= 60 else ("relaxed" if val <= 40 else "balanced")
        lines.append(f"Activity style: {style}")

    if profile.get("early_night") is not None:
        val = profile["early_night"]
        rhythm = "nightlife-oriented" if val >= 60 else ("early bird" if val <= 40 else "moderate")
        lines.append(f"Day rhythm: {rhythm}")

    return "\n".join(lines) if lines else "No profile data available."


def _merge_preferences(
    llm_extracted: dict,
    profile: BehavioralProfile,
) -> dict:
    """
    Merge LLM-extracted preferences with profile data.

    LLM extraction takes priority (it has the real-time conversation context).
    Profile fills in gaps where the user didn't mention anything.
    """
    merged = {
        "budget_level": llm_extracted.get("budget_level"),
        "travel_style": llm_extracted.get("travel_style"),
        "walking_tolerance": llm_extracted.get("walking_tolerance"),
        "food_preferences": llm_extracted.get("food_preferences") or [],
        "accommodation_style": llm_extracted.get("accommodation_style"),
        "nightlife": llm_extracted.get("nightlife"),
        "interests_from_conversation": llm_extracted.get("interests_from_conversation") or [],
        "pace": llm_extracted.get("pace"),
        "special_focus": llm_extracted.get("special_focus"),
    }

    # Fill from profile if LLM didn't extract these
    if not merged["budget_level"] and profile.get("budget_level") is not None:
        merged["budget_level"] = get_budget_label(profile["budget_level"])

    if not merged["food_preferences"] and profile.get("dining_preferences"):
        merged["food_preferences"] = profile["dining_preferences"]

    if not merged["accommodation_style"] and profile.get("accommodation_styles"):
        # Take the first preference as the primary style
        merged["accommodation_style"] = profile["accommodation_styles"][0]

    if not merged["interests_from_conversation"] and profile.get("interests"):
        merged["interests_from_conversation"] = profile["interests"]

    # Derive walking tolerance from adventure_relaxing slider if not set
    if not merged["walking_tolerance"] and profile.get("adventure_relaxing") is not None:
        val = profile["adventure_relaxing"]
        merged["walking_tolerance"] = "high" if val >= 60 else ("low" if val <= 30 else "medium")

    # Derive pace from adventure_relaxing
    if not merged["pace"] and profile.get("adventure_relaxing") is not None:
        val = profile["adventure_relaxing"]
        merged["pace"] = "packed" if val >= 65 else ("relaxed" if val <= 35 else "balanced")

    # Derive nightlife from early_night slider
    if not merged["nightlife"] and profile.get("early_night") is not None:
        val = profile["early_night"]
        merged["nightlife"] = "high" if val >= 65 else ("low" if val <= 35 else "medium")

    return merged


async def run_preference_agent(state: TripState) -> TripState:
    """
    Main Preference Agent workflow.

    1. Extracts preferences from user message via LLM.
    2. Merges with behavioral profile data.
    3. Stores structured preferences in state for downstream agents.
    """
    user_message = state.get("user_message", "")
    profile = state.get("profile") or {}
    destination = state.get("destination_city", "")

    # Build profile context for the LLM
    profile_context = _build_profile_context(profile)

    llm = get_fast_llm()

    prompt = f"""User Message: "{user_message}"
Destination: {destination or 'not specified'}

User Profile Context:
{profile_context}

Extract structured preferences now."""

    messages = [
        SystemMessage(content=PREFERENCE_EXTRACTION_PROMPT),
        HumanMessage(content=prompt),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip().strip("```json").strip("```").strip()
        llm_preferences = json.loads(raw)
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        # Fallback: empty extraction, will rely purely on profile
        llm_preferences = {}
        print(f"[PreferenceAgent] LLM extraction failed ({e}), using profile only")

    # Merge LLM extraction with profile data
    merged = _merge_preferences(llm_preferences, profile)

    state["extracted_preferences"] = merged
    return state
