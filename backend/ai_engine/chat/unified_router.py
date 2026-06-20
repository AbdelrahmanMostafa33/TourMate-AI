"""
Unified Router — Single context-aware LLM call with structured output.

Replaces the 3-call pattern (intent parser + clarification + general chat)
with 1 intelligent call that sees full conversation history.

Uses Pydantic models + .with_structured_output() to guarantee valid JSON
from the LLM, eliminating manual JSON parsing and markdown fence stripping.

The router:
1. Sees the full conversation history + current state (slots, phase, itinerary)
2. Extracts any new information from the user's message
3. Decides the action AND generates the response in one shot
"""

from __future__ import annotations

import re
import logging
from typing import Dict, Any, List, Optional, Literal

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from ai_engine.llm_config import invoke_with_fallback
from ai_engine.memory.conversation_state import (
    ConversationState,
    ConversationPhase,
)

logger = logging.getLogger(__name__)


# ── Structured Output Schema (Pydantic) ──────────────────────────────────────

class ExtractedSlots(BaseModel):
    """Travel information extracted from the user's message."""

    destination_city: Optional[str] = Field(
        default=None,
        description="City name if mentioned (e.g. 'Cairo', 'Paris')",
    )
    destination_country: Optional[str] = Field(
        default=None,
        description="Country name if mentioned",
    )
    duration_days: Optional[str] = Field(
        default=None,
        description="Number of days for the trip (e.g. 3)",
    )
    travel_dates: Optional[str] = Field(
        default=None,
        description="Specific dates or time range if mentioned",
    )
    group_size: Optional[str] = Field(
        default=None,
        description="Number of travelers (e.g. 2)",
    )
    special_requests: Optional[str] = Field(
        default=None,
        description="Any special requirements or requests",
    )
    budget_level: Optional[str] = Field(
        default=None,
        description="Budget level: 'budget', 'moderate', or 'luxury'",
    )
    travel_style: Optional[str] = Field(
        default=None,
        description="Travel style: 'romantic', 'adventure', 'family', 'solo', 'cultural', or 'relaxation'",
    )
    pace: Optional[str] = Field(
        default=None,
        description="Pace: 'relaxed', 'moderate', or 'packed'",
    )
    interests: Optional[List[str]] = Field(
        default=None,
        description="List of interests (e.g. ['history', 'food', 'architecture'])",
    )
    food_preferences: Optional[List[str]] = Field(
        default=None,
        description="Food preferences (e.g. ['local cuisine', 'vegetarian'])",
    )
    accommodation_preferences: Optional[List[str]] = Field(
        default=None,
        description="Accommodation preferences (e.g. ['boutique hotel', 'hostel'])",
    )


class RouterOutput(BaseModel):
    """Structured output from the unified router.

    The LLM fills this Pydantic model directly via .with_structured_output(),
    guaranteeing valid output without manual JSON parsing.
    """

    action: Literal["plan_trip", "ask_clarification", "answer_question", "approve_itinerary", "modify_itinerary"] = Field(
        description=(
            "What to do next. One of: "
            "'plan_trip' (all info collected), "
            "'ask_clarification' (need more info), "
            "'answer_question' (user asked a question), "
            "'approve_itinerary' (user approved), "
            "'modify_itinerary' (user wants changes)"
        )
    )
    extracted: ExtractedSlots = Field(
        default_factory=ExtractedSlots,
        description="Any travel information extracted from the user's message",
    )
    response: str = Field(
        description="Your natural conversational response to the user"
    )


# ── RouterResult (return type, uses dicts for flexibility) ────────────────────

class RouterResult:
    """Final output from route_message — uses plain dicts for extracted slots."""

    __slots__ = ("action", "extracted", "response")

    def __init__(self, action: str, extracted: Dict[str, Any], response: str):
        self.action = action
        self.extracted = extracted
        self.response = response


# ── Router Prompt ────────────────────────────────────────────────────────────

ROUTER_SYSTEM_PROMPT = """You are TourMate AI, a travel planning assistant having a conversation with a user.

## Conversation History
{conversation_history}

## Current State
- Phase: {phase}
- Destination: {destination}
- Duration: {duration}
- Budget: {budget}
- Style: {style}
- Interests: {interests}
- Food: {food}
- Accommodation: {accommodation}
- Still missing: {missing_fields}
{itinerary_context}

## Current Message
The user just said: "{user_message}"

## Instructions
1. **Extract ONLY from the Current Message above** — do NOT extract information from the Conversation History. The history is for context only.
2. Extract any travel information from the user's message into the "extracted" field
3. NEVER ask for information they already provided — check the Current State above
4. Always acknowledge what the user said before asking for more
   - Good: "Cairo! Great choice. How many days are you thinking?"
   - Bad: "Please provide your destination and duration."
5. Ask for ONE thing at a time, not everything at once
6. If ALL required info is collected (destination + duration + budget + style + interests + food + accommodation), set action to "plan_trip"
7. If they ask a travel question, answer it naturally and helpfully
8. If they approve an itinerary, confirm it warmly
9. If they request changes to an itinerary, acknowledge and set action to "modify_itinerary"
10. Be warm but concise — no filler words like "I understand", "Certainly!", "Of course!"
11. Respond in the same language the user writes in

## Normalization Rules (MUST follow)
- **Budget**: Always normalize to one of: 'budget', 'moderate', or 'luxury'
  - 'medium', 'mid-range', 'average', 'mid' → 'moderate'
  - 'cheap', 'low', 'economy', 'affordable' → 'budget'
  - 'high-end', 'expensive', 'luxurious', 'premium', '5-star' → 'luxury'
- **Style**: Always normalize to one of: 'romantic', 'adventure', 'family', 'solo', 'cultural', or 'relaxation'
  - 'history', 'museums', 'heritage' → 'cultural'
  - 'chill', 'rest', 'beach' → 'relaxation'
  - 'hiking', 'outdoor', 'active' → 'adventure'
- **Pace**: Always normalize to one of: 'relaxed', 'moderate', or 'packed'
  - 'slow', 'easy', 'leisurely' → 'relaxed'
  - 'busy', 'intense', 'full' → 'packed'
  - 'mixed', 'flexible', 'varied' → 'moderate'

## Important Rules
- **NEVER change travel_style based on interests.** If the user says "I like history", extract interests: ['history'] — do NOT set travel_style to 'cultural'. travel_style is ONLY set when the user explicitly describes their travel STYLE (e.g. 'I want a solo trip', 'cultural travel', 'relaxation'). The style normalization mappings (history→cultural, chill→relaxation, etc.) ONLY apply when the user is describing their travel style, NOT when they are listing interests.
- **Duration**: Return as a string of the number (e.g. '3', '5', '7')

## Extraction Rules
- **Food preferences**: Extract from phrases like 'local food', 'local cuisine', 'street food', 'traditional dishes', 'seafood', 'vegetarian', 'vegan', 'halal', 'kosher', etc.
  - 'I love local food' → food_preferences: ['local cuisine']
  - 'I want to try street food' → food_preferences: ['street food']
- **Interests**: Extract from phrases like 'history', 'architecture', 'art', 'shopping', 'nightlife', 'nature', 'photography', etc.
  - 'I love history and architecture' → interests: ['history', 'architecture']
- **Accommodation**: Extract from phrases like 'boutique hotel', 'hostel', ' Airbnb', 'resort', 'budget hotel', etc.
- **If the user sends a greeting or casual message with no new travel info (e.g. 'hello', 'hi', 'how are you'), do NOT extract any slots — leave extracted empty.**"""


# ── Context Building ─────────────────────────────────────────────────────────

def _build_conversation_history(state: ConversationState, max_messages: int = 10) -> str:
    """Build a text summary of recent conversation for the LLM prompt."""
    recent = state.history[-max_messages:]
    if not recent:
        return "(No previous messages — this is the start of the conversation)"

    lines = []
    for msg in recent:
        role = "User" if msg.role == "user" else "TourMate"
        content = msg.content[:400]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _build_itinerary_summary(state: ConversationState) -> str:
    """Build a concise itinerary summary for review phase."""
    if not state.itinerary:
        return ""

    days = state.itinerary.get("days", [])
    lines = [f"\n## Current Itinerary: {len(days)} days planned"]

    for day in days:
        day_num = day.get("day_number", "?")
        theme = day.get("theme", "")
        stops = day.get("stops", [])
        stop_names = [s.get("name", "?") for s in stops[:4]]
        lines.append(f"Day {day_num}: {theme} — {', '.join(stop_names)}")

    hotels = state.itinerary.get("accommodation_suggestions", [])
    if hotels:
        hotel_names = [h.get("name", "?") for h in hotels[:3]]
        lines.append(f"Hotels: {', '.join(hotel_names)}")

    return "\n".join(lines)


# ── Regex Fallback Extraction ────────────────────────────────────────────────

_DURATION_PATTERNS = [
    r"(\d+)\s*-?\s*days?",
    r"for\s+(\d+)\s*-?\s*days?",
    r"(\d+)\s*-?\s*nights?",
]

_BUDGET_MAP = {
    # Longer / more specific matches first to avoid partial-word collisions
    "mid-range": "moderate", "mid range": "moderate",
    "high-end": "luxury", "five star": "luxury",
    "affordable": "budget", "average": "moderate",
    "premium": "luxury", "5-star": "luxury",
    "medium": "moderate",
    "moderate": "moderate",
    "luxury": "luxury",
    "budget": "budget",
    "cheap": "budget",
}

_STYLE_MAP = {
    "romantic": "romantic", "adventure": "adventure", "hiking": "adventure",
    "family": "family", "kids": "family", "solo": "solo", "alone": "solo",
    "museums": "cultural", "history": "cultural", "cultural": "cultural",
    "relax": "relaxation", "chill": "relaxation", "relaxation": "relaxation",
}

_DESTINATION_KEYWORDS = {
    "cairo": "cairo", "paris": "paris", "london": "london", "dubai": "dubai",
    "tokyo": "tokyo", "rome": "rome", "istanbul": "istanbul", "bali": "bali",
    "bangkok": "bangkok", "new york": "new york", "barcelona": "barcelona",
    "amsterdam": "amsterdam", "berlin": "berlin", "madrid": "madrid",
    "lisbon": "lisbon", "vienna": "vienna", "prague": "prague",
    "athens": "athens", "marrakech": "marrakech", "singapore": "singapore",
    "sharm el sheikh": "sharm el sheikh", "luxor": "luxor", "aswan": "aswan",
}


def _regex_extract(user_message: str) -> dict:
    """Regex-based extraction as a safety net."""
    msg = user_message.lower().strip()
    result = {}

    for pattern in _DURATION_PATTERNS:
        match = re.search(pattern, msg)
        if match:
            result["duration_days"] = int(match.group(1))
            break

    for keyword, level in _BUDGET_MAP.items():
        if keyword in msg:
            result["budget_level"] = level
            break

    for keyword, style in _STYLE_MAP.items():
        if keyword in msg:
            result["travel_style"] = style
            break

    for keyword, city in _DESTINATION_KEYWORDS.items():
        if keyword in msg:
            result["destination_city"] = city
            break

    return result


def _merge_extracted(llm_extracted: dict, regex_extracted: dict) -> dict:
    """Merge LLM extraction with regex fallback. Regex fills gaps only."""
    merged = dict(llm_extracted)
    for key, value in regex_extracted.items():
        if key in ("interests", "food_preferences", "accommodation_preferences"):
            existing = merged.get(key) or []
            if not isinstance(existing, list):
                existing = []
            if isinstance(value, str):
                items = [v.strip() for v in value.split(",") if v.strip()]
            else:
                items = value
            for v in items:
                if v not in existing:
                    existing.append(v)
            merged[key] = existing if existing else None
        elif merged.get(key) is None:
            if isinstance(value, str) and key in ("interests", "food_preferences", "accommodation_preferences"):
                merged[key] = [v.strip() for v in value.split(",") if v.strip()]
            else:
                merged[key] = value
    return merged


# ── Action Normalization ─────────────────────────────────────────────────────

_ACTION_ALIASES = {
    "plan_trip": "plan_trip",
    "generate_plan": "plan_trip",
    "generate_itinerary": "plan_trip",
    "start_planning": "plan_trip",
    "ask_clarification": "ask_clarification",
    "ask_question": "ask_clarification",
    "clarify": "ask_clarification",
    "answer_question": "answer_question",
    "answer": "answer_question",
    "general_chat": "answer_question",
    "approve_itinerary": "approve_itinerary",
    "approve": "approve_itinerary",
    "confirm": "approve_itinerary",
    "modify_itinerary": "modify_itinerary",
    "modify": "modify_itinerary",
    "change": "modify_itinerary",
    "update": "modify_itinerary",
}


def _normalize_action(action: str) -> str:
    """Normalize action string to a valid action."""
    return _ACTION_ALIASES.get(action.lower().strip(), "answer_question")


def _coerce_int(value) -> int | None:
    """Coerce a value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_extracted_dict(extracted: ExtractedSlots) -> dict:
    """Convert Pydantic ExtractedSlots to a plain dict, dropping None values.
    Also coerces duration_days and group_size to int."""
    raw = extracted.model_dump()
    raw["duration_days"] = _coerce_int(raw.get("duration_days"))
    raw["group_size"] = _coerce_int(raw.get("group_size"))
    return {k: v for k, v in raw.items() if v is not None}


# ── Main Router Function ─────────────────────────────────────────────────────

async def route_message(state: ConversationState, user_message: str) -> RouterResult:
    """
    Single context-aware LLM call with structured output.

    Uses .with_structured_output() to guarantee valid JSON from the LLM.
    Falls back to regex extraction if the LLM fails.
    """
    # Build context
    history_text = _build_conversation_history(state)
    slots = state.slots
    missing = slots.missing_required()
    missing_str = ", ".join(missing) if missing else "none — all info collected!"

    itinerary_context = ""
    if state.phase == ConversationPhase.ITINERARY_REVIEW:
        itinerary_context = _build_itinerary_summary(state)

    # Build prompt
    prompt = ROUTER_SYSTEM_PROMPT.format(
        conversation_history=history_text,
        phase=state.phase.value,
        destination=slots.destination_city or "not yet provided",
        duration=f"{slots.duration_days} days" if slots.duration_days else "not yet provided",
        budget=slots.budget_level or "not yet provided",
        style=slots.travel_style or "not yet provided",
        interests=", ".join(slots.interests) if slots.interests else "not yet provided",
        food=", ".join(slots.food_preferences) if slots.food_preferences else "not yet provided",
        accommodation=", ".join(slots.accommodation_preferences) if slots.accommodation_preferences else "not yet provided",
        missing_fields=missing_str,
        itinerary_context=itinerary_context,
        user_message=user_message,
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Extract information and respond now."),
    ]

    # Call LLM with structured output
    router_output: Optional[RouterOutput] = None
    try:
        router_output = await invoke_with_fallback(
            "router", messages, structured_output=RouterOutput,
        )
    except Exception as e:
        logger.error("Router LLM failed: %s", e)
        router_output = None

    # Extract fields
    if router_output:
        action = _normalize_action(router_output.action)
        extracted = _build_extracted_dict(router_output.extracted)
        response_text = router_output.response
    else:
        # Fallback: use regex extraction + default response
        action = "answer_question"
        extracted = {}
        response_text = "I'm here to help with your travel plans! Feel free to ask me anything."

    # Apply regex fallback — fills gaps the LLM missed
    regex_result = _regex_extract(user_message)
    extracted = _merge_extracted(extracted, regex_result)

    # Guard: only preserve travel_style if the current message contains
    # an UNAMBIGUOUS style keyword. Words like 'history', 'museums',
    # 'chill' overlap with interests and should NOT trigger style extraction
    # — neither from the LLM nor from the regex fallback.
    UNAMBIGUOUS_STYLE_KEYWORDS = {
        "solo", "alone", "romantic", "adventure", "hiking",
        "family", "kids", "cultural travel", "relaxation trip",
    }
    msg_lower = user_message.lower()
    has_unambiguous_style = any(kw in msg_lower for kw in UNAMBIGUOUS_STYLE_KEYWORDS)
    if not has_unambiguous_style and extracted.get("travel_style"):
        del extracted["travel_style"]

    # If destination + duration are complete AND the current message
    # contributed new info (not just history), override to plan_trip.
    # We check if regex found anything new OR if LLM extracted from current msg.
    has_new_from_message = bool(regex_result) or (
        router_output is not None and any([
            router_output.extracted.destination_city,
            router_output.extracted.duration_days,
            router_output.extracted.budget_level,
            router_output.extracted.travel_style,
        ])
    )
    if has_new_from_message and extracted.get("destination_city") and extracted.get("duration_days"):
        if action not in ("approve_itinerary", "modify_itinerary"):
            action = "plan_trip"

    return RouterResult(
        action=action,
        extracted=extracted,
        response=response_text,
    )
