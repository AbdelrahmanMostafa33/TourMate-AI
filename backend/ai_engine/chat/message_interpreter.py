"""
Message Interpreter — Single context-aware LLM call with structured output.

Replaces the 3-call pattern (intent parser + clarification + general chat)
with 1 intelligent call that sees full conversation history.

Uses Pydantic models + .with_structured_output() to guarantee valid JSON
from the LLM, eliminating manual JSON parsing and markdown fence stripping.

The interpreter:
1. Sees the full conversation history + current state (slots, phase, itinerary)
2. Extracts any new information from the user's message
3. Decides the action AND generates the response in one shot
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Literal

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from ai_engine.llm_config import invoke_with_fallback
from ai_engine.memory.conversation_state import (
    ConversationState,
    ConversationPhase,
)
from ai_engine.tools.slot_normalizer import normalize_extracted_slots
from ai_engine.observability import traced

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
    traveler_group_type: Optional[str] = Field(
        default=None,
        description="Traveler group type: 'solo', 'couple', 'family', 'friends', or 'business'",
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
        description="Pace: 'relaxed', 'balanced', or 'packed'",
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
        description=(
            "Accommodation preferences using natural language that maps to accommodation types. "
            "Use terms containing one of these keywords: 'hotel' (standard), 'hostel' (budget/shared), "
            "'resort' (all-inclusive/beach), 'luxury'/'boutique'/'palace' (high-end). "
            "Examples: ['boutique hotel'], ['hostel'], ['beach resort'], ['luxury hotel']"
        ),
    )


class InterpreterOutput(BaseModel):
    """Structured output from the message interpreter.

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


# ── InterpretationResult (return type, uses dicts for flexibility) ───────────

class InterpretationResult:
    """Final output from interpret_message — uses plain dicts for extracted slots."""

    __slots__ = ("action", "extracted", "response")

    def __init__(self, action: str, extracted: Dict[str, Any], response: str):
        self.action = action
        self.extracted = extracted
        self.response = response


# ── Interpreter Prompt ──────────────────────────────────────────────────────

INTERPRETER_SYSTEM_PROMPT = """You are TourMate AI, a travel planning assistant having a conversation with a user.

## Conversation History
{conversation_history}

## Current State
- Phase: {phase}
- Destination: {destination}
- Duration: {duration}
- Budget: {budget}
- Style: {style}
- Pace: {pace}
- Interests: {interests}
- Food: {food}
- Accommodation: {accommodation}
- Travel dates: {travel_dates}
- Group size: {group_size}
- Traveler group type: {traveler_group_type}
- Still missing: {missing_fields}
- Last question asked about: {last_question_field}
{itinerary_context}

## Current Message
The user just said: "{user_message}"

## IMPORTANT: Disambiguation
The 'Last question asked about' field tells you which slot you were asking about in your previous response.
If the user gives a short single-word answer, they are almost certainly answering THAT specific question —
extract it into the corresponding field, NOT into other fields.

Examples:
- If last question was 'pace' and user says 'mixed' → pace: 'mixed', NOT food_preferences
- If last question was 'budget_level' and user says 'high' → budget_level: 'high', NOT interests
- If last question was 'interests' and user says 'nature' → interests: ['nature'], NOT pace

## Instructions
1. **Extract ONLY from the Current Message above** — do NOT extract information from the Conversation History. The history is for context only.
2. Extract any travel information from the user's message into the "extracted" field
3. If the user provided their destination + duration → set action to "plan_trip" immediately. Smart defaults will handle everything else.
4. NEVER ask for information they already provided — check the Current State above
5. Always acknowledge what the user said before asking for more
   - Good: "Cairo! Great choice. How many days are you thinking?"
   - Bad: "Please provide your destination and duration."
6. If destination or duration is missing, ask for ONE thing at a time — start with destination, then duration.
7. NEVER ask about budget, pace, style, interests, food, accommodation, traveler count, dates, or traveler group —
   those are all handled by smart defaults. Only ask for destination and duration.
8. If they ask a travel question, answer it naturally and helpfully
9. If they approve an itinerary, confirm it warmly
10. If they request changes to an itinerary, acknowledge and set action to "modify_itinerary"
11. Be warm but concise — no filler words like "I understand", "Certainly!", "Of course!"
12. Respond in the same language the user writes in
13. NEVER confirm or ask "Is that correct?" — if the user provides a clear answer, accept it immediately and move on.

## Extraction Rules
- **Budget**: Extract the raw phrase. A downstream normalizer canonicalizes to 'budget', 'moderate', or 'luxury'.
- **Style**: Extract ONLY when the user explicitly describes their travel STYLE
  (e.g. 'I want a solo trip', 'cultural travel'). Do NOT confuse interests with style —
  'I like history' → interests: ['history'], NOT travel_style: 'cultural'.
- **Pace**: Extract the raw phrase. A downstream normalizer canonicalizes to 'relaxed', 'balanced', or 'packed'.
- **Interests**: Extract ONLY interest CATEGORY keywords — short, single words or
  short phrases describing what the user wants to SEE or DO. Examples of valid
  interests: 'museums', 'history', 'food', 'shopping', 'nature', 'parks', 'art',
  'architecture', 'nightlife', 'beaches', 'photography', 'religion', 'adventure'.
  Do NOT extract: commands or instructions ('remove X', 'swap Y', 'add Z'),
  specific place names ('Al-Azhar Mosque', 'Eiffel Tower'), full sentences,
  or multi-word instructions. If the user says "remove X and add Y and I like
  museums and food" → extract ONLY ['museums', 'food'].
- **Food preferences**: Extract from phrases like 'local food', 'street food', 'vegetarian', etc.
- **Accommodation**: Extract as a phrase containing: 'hotel', 'hostel', 'resort', 'luxury', 'boutique', 'palace'.
  Return as a list with ONE item, e.g. ['boutique hotel'] not ['luxury', 'boutique', 'hotel'].
- **Duration**: Return as a string of the number (e.g. '3', '5', '7')
- **If the user sends a greeting or casual message with no new travel info, do NOT extract any slots — leave extracted empty."""


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
    """Convert Pydantic ExtractedSlots to a plain dict, drop None values,
    coerce duration_days/group_size to int, then apply deterministic
    normalization (budget, pace, style, food, accommodation)."""
    raw = extracted.model_dump()
    raw["duration_days"] = _coerce_int(raw.get("duration_days"))
    raw["group_size"] = _coerce_int(raw.get("group_size"))
    raw = {k: v for k, v in raw.items() if v is not None}

    # Deterministic post-processing — replaces LLM-dependent normalization.
    # The LLM extracts raw values; this step guarantees canonical forms.
    normalized = normalize_extracted_slots(raw)
    return normalized


# ── Main Interpreter Function ───────────────────────────────────────────────

@traced(name="message_interpreter", tags=["conversation", "interpreter"], metadata={"component": "message_interpreter"})
async def interpret_message(state: ConversationState, user_message: str) -> InterpretationResult:
    """
    Single context-aware LLM call with structured output.

    Uses .with_structured_output() to guarantee valid JSON from the LLM.
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
    prompt = INTERPRETER_SYSTEM_PROMPT.format(
        conversation_history=history_text,
        phase=state.phase.value,
        destination=slots.destination_city or "not yet provided",
        duration=f"{slots.duration_days} days" if slots.duration_days else "not yet provided",
        budget=slots.budget_level or "not yet provided",
        style=slots.travel_style or "not yet provided",
        pace=slots.pace or "not yet provided",
        interests=", ".join(slots.interests) if slots.interests else "not yet provided",
        food=", ".join(slots.food_preferences) if slots.food_preferences else "not yet provided",
        accommodation=", ".join(slots.accommodation_preferences) if slots.accommodation_preferences else "not yet provided",
        travel_dates=slots.travel_dates or "not yet provided",
        group_size=str(slots.group_size) if slots.group_size else "not yet provided",
        traveler_group_type=slots.traveler_group_type or "not yet provided",
        missing_fields=missing_str,
        last_question_field=state.last_question_field or "(first message, no previous question)",
        itinerary_context=itinerary_context,
        user_message=user_message,
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="Extract information and respond now."),
    ]

    # Call LLM with structured output
    interpreter_output: Optional[InterpreterOutput] = None
    try:
        interpreter_output = await invoke_with_fallback(
            "router", messages, structured_output=InterpreterOutput,
        )
    except Exception as e:
        logger.error("Message interpreter LLM failed: %s", e)
        interpreter_output = None

    # Extract fields
    if interpreter_output:
        action = _normalize_action(interpreter_output.action)
        extracted = _build_extracted_dict(interpreter_output.extracted)
        response_text = interpreter_output.response
    else:
        # LLM failed — return generic response (all 10 keys exhausted)
        logger.error("Message interpreter LLM failed with all keys exhausted")
        extracted = {}
        action = "answer_question"
        response_text = "I'm having trouble connecting to my AI service. Please try again in a moment."

    # If LLM extracted destination + duration from current message,
    # override to plan_trip to trigger itinerary generation.
    if interpreter_output is not None and any([
        interpreter_output.extracted.destination_city,
        interpreter_output.extracted.duration_days,
        interpreter_output.extracted.budget_level,
        interpreter_output.extracted.travel_style,
    ]):
        if extracted.get("destination_city") and extracted.get("duration_days"):
            if action not in ("approve_itinerary", "modify_itinerary"):
                action = "plan_trip"

    return InterpretationResult(
        action=action,
        extracted=extracted,
        response=response_text,
    )
