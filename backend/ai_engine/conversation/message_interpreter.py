"""
Message Interpreter — Single context-aware LLM call with structured output.

Replaces the 3-call pattern (intent parser + clarification + general chat)
with 1 intelligent call that sees full conversation history.

Uses Pydantic models + .with_structured_output() to guarantee valid JSON
from the LLM, eliminating manual JSON parsing and markdown fence stripping.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, Literal

from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from ai_engine.llm import invoke_with_fallback
from ai_engine.conversation.conversation_state import (
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
    special_requests: Optional[List[str]] = Field(
        default=None,
        description="Any special requirements or requests (e.g. ['add Grand Egyptian Museum'])",
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
        description=(
            "Accommodation preferences using natural language that maps to accommodation types. "
            "Use terms containing one of these keywords: 'hotel' (standard), 'hostel' (budget/shared), "
            "'resort' (all-inclusive/beach), 'luxury'/'boutique'/'palace' (high-end). "
            "Examples: ['boutique hotel'], ['hostel'], ['beach resort'], ['luxury hotel']"
        ),
    )


class InterpreterOutput(BaseModel):
    """Structured output from the message interpreter."""

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

## IMPORTANT: Disambiguation
The 'Last question asked about' field tells you which slot you were asking about in your previous response.
If the user gives a short single-word answer, they are almost certainly answering THAT specific question —
extract it into the corresponding field, NOT into other fields.

Examples:
- If last question was 'pace' and user says 'mixed' → pace: 'mixed', NOT food_preferences
- If last question was 'budget_level' and user says 'high' → budget_level: 'high', NOT interests
- If last question was 'interests' and user says 'nature' → interests: ['nature'], NOT pace

## Action Priority (highest to lowest — pick the FIRST that matches)

1. **(HIGHEST) modify_itinerary** — If phase is "itinerary_review" and the user asks to add, remove, change, swap, update, or modify ANYTHING in their itinerary, ALWAYS use this action. This takes priority over every other rule, including plan_trip.

2. **approve_itinerary** — If the user approves, confirms, or says the itinerary looks good.

3. **answer_question** — If the user asks a general travel question (e.g. "what's the best time to visit?", "how far is the museum from the hotel?").

4. **plan_trip** — Only when the user provides destination + duration for a NEW trip. If there's already an itinerary shown in the Current State above, do NOT use this — use modify_itinerary instead.

5. **(LOWEST) ask_clarification** — When more information is needed.

## General Instructions
1. Extract any travel information from the user's message into the "extracted" field
2. NEVER ask for information they already provided — check the Current State above
3. Always acknowledge what the user said before asking for more
4. If destination or duration is missing, ask for ONE thing at a time — start with destination, then duration.
5. NEVER ask about budget, pace, style, interests, food, accommodation, traveler count, dates, or traveler group — those are all handled by smart defaults.
6. Be warm but concise — no filler words
7. Respond in the same language the user writes in
8. NEVER confirm or ask "Is that correct?" — if the user provides a clear answer, accept it immediately.
"""


# ── Context Building ─────────────────────────────────────────────────────────

def _build_itinerary_summary(state: ConversationState) -> str:
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
    return _ACTION_ALIASES.get(action.lower().strip(), "answer_question")


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_extracted_dict(extracted: ExtractedSlots) -> dict:
    raw = extracted.model_dump()
    raw["duration_days"] = _coerce_int(raw.get("duration_days"))
    raw["group_size"] = _coerce_int(raw.get("group_size"))
    raw = {k: v for k, v in raw.items() if v is not None}
    normalized = normalize_extracted_slots(raw)
    return normalized


# ── Main Interpreter Function ───────────────────────────────────────────────

@traced(name="message_interpreter", tags=["conversation", "interpreter"], metadata={"component": "message_interpreter"})
async def interpret_message(state: ConversationState, user_message: str) -> InterpretationResult:
    """Single context-aware LLM call with structured output."""
    slots = state.slots
    missing = slots.missing_required()
    missing_str = ", ".join(missing) if missing else "none — all info collected!"

    itinerary_context = ""
    if state.phase == ConversationPhase.ITINERARY_REVIEW:
        itinerary_context = _build_itinerary_summary(state)

    system_prompt = INTERPRETER_SYSTEM_PROMPT.format(
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
    )

    # Build messages with proper HumanMessage/AIMessage turns
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]

    # Add conversation history as proper message turns (last 10 messages)
    for msg in state.history[-10:]:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
        # Skip system messages

    # Add the user's current message as a HumanMessage
    messages.append(HumanMessage(content=user_message))

    interpreter_output: Optional[InterpreterOutput] = None
    try:
        interpreter_output = await invoke_with_fallback("router", messages, structured_output=InterpreterOutput)
    except Exception as e:
        logger.error("Message interpreter LLM failed: %s", e)
        interpreter_output = None

    if interpreter_output:
        action = _normalize_action(interpreter_output.action)
        extracted = _build_extracted_dict(interpreter_output.extracted)
        response_text = interpreter_output.response
    else:
        logger.error("Message interpreter LLM failed after all retries")
        extracted = {}
        action = "answer_question"
        response_text = (
            "I understood your request, but I'm having trouble "
            "processing it on my end. Could you please rephrase that?"
        )

    # Safety override: if user is in itinerary_review phase and the LLM
    # chose something other than modify_itinerary, check if the message
    # sounds like a modification request.
    if state.phase == ConversationPhase.ITINERARY_REVIEW and action != "modify_itinerary":
        msg_lower = user_message.lower()
        modification_keywords = ["add ", "remove ", "delete ", "change ", "swap ", "switch ", "replace ", "update ", "modify ", "insert ", "include ", "exclude ", "put ", "drop ", "take out", "get rid of"]
        if any(kw in msg_lower for kw in modification_keywords):
            logger.info(
                "[Interpreter] Safety override: '%s' → modify_itinerary (phase=%s, action=%s)",
                user_message[:60], state.phase.value, action,
            )
            action = "modify_itinerary"

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
