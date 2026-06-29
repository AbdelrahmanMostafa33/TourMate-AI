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
        description=(
            "REQUIRED: City name ONLY. The system ONLY supports specific cities. "
            "NEVER accept a country name (e.g. 'Egypt', 'France', 'USA') as a city. "
            "Valid examples: 'Cairo', 'Luxor', 'Aswan', 'Paris'. "
            "If the user gives a country name, set this to null and ask for a specific city."
        ),
    )
    destination_country: Optional[str] = Field(
        default=None,
        description="Country name — fill this only if the user explicitly mentions a country",
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
    selected_hotel_name: Optional[str] = Field(
        default=None,
        description=(
            "When the user picks a specific hotel during hotel_selection phase, "
            "extract the hotel name or number they referenced (e.g. 'Marriott', "
            "'the first one', 'hotel 2'). Only used for select_hotel action."
        ),
    )
    selected_hotel_number: Optional[int] = Field(
        default=None,
        description=(
            "The 1-based index of the hotel the user chose, if they specified "
            "by number (e.g. 'hotel 2' → 2). Only used for select_hotel action."
        ),
    )

    # ── Flight Related ──────────────────────────────────────────────
    origin_city: Optional[str] = Field(
        default=None,
        description=(
            "The city the user will fly FROM (origin). "
            "Only used during FLIGHT_SELECTION phase (e.g. 'Cairo', 'London')."
        ),
    )
    selected_flight_number: Optional[int] = Field(
        default=None,
        description=(
            "The 1-based index of the flight the user chose from the search results. "
            "Only used for select_flight action (e.g. 'the first one' → 1, 'flight 2' → 2)."
        ),
    )
    cabin_class: Optional[str] = Field(
        default=None,
        description=(
            "The cabin class the user wants for flights. "
            "Only used during FLIGHT_SELECTION phase. "
            "Valid values: 'ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST'. "
            "Extract when user says things like 'first class', 'business class', 'economy'."
        ),
    )
    is_round_trip: Optional[bool] = Field(
        default=None,
        description=(
            "Whether the user wants a round-trip (both departure and return). "
            "Only used during FLIGHT_SELECTION phase. "
            "Set to true if user says 'round trip', 'return', 'both ways'. "
            "Set to false if user says 'one-way', 'one way'. Leave null if not specified."
        ),
    )
    return_date: Optional[str] = Field(
        default=None,
        description=(
            "The return date for a round-trip flight (ISO format or natural language). "
            "Only used during FLIGHT_SELECTION phase when is_round_trip is true. "
            "Extract when user says 'returning on July 30', 'come back August 1'."
        ),
    )


class InterpreterOutput(BaseModel):
    """Structured output from the message interpreter."""

    action: Literal["plan_trip", "ask_clarification", "answer_question", "approve_itinerary", "modify_itinerary", "select_hotel", "search_flights", "select_flight"] = Field(
        description=(
            "What to do next. One of: "
            "'plan_trip' (all info collected), "
            "'ask_clarification' (need more info), "
            "'answer_question' (user asked a question), "
            "'approve_itinerary' (user approved), "
            "'modify_itinerary' (user wants changes), "
            "'select_hotel' (user is choosing a hotel from options presented), "
            "'search_flights' (user wants to search/see flights during FLIGHT_SELECTION phase), "
            "'select_flight' (user picked a specific flight from the options)"
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
- City: {destination}
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

2. **approve_itinerary** — If the user approves, confirms, or says the itinerary looks good. ALSO used during hotel_selection phase when the user says "looks good", "approve", or "they all look good" to accept the default (first) hotel. ALSO used during flight_selection phase when the user says "skip flights", "no flights", "go to hotels", "I don't need flights", or simply "approve".

3. **select_hotel** — ONLY during hotel_selection phase. If the user picks a specific hotel (by number like "hotel 2" or by name like "the Marriott"), use this action. Extract the hotel name or number into selected_hotel_name / selected_hotel_number.

4. **search_flights** — ONLY during flight_selection phase. If the user provides an origin city (e.g. "from Cairo") or wants to see/search flights, use this action. Extract the origin_city if mentioned.

5. **select_flight** — ONLY during flight_selection phase. If the user picks a specific flight by number (e.g. "flight 2", "the first one", "option 3"), use this action. Extract selected_flight_number (1-based).

6. **plan_trip** — Only when ALL required info (city + duration + interests) is collected. If there's already an itinerary shown in the Current State above, do NOT use this — use modify_itinerary instead.

7. **(LOWEST) ask_clarification** — When more information is needed.

## General Instructions
1. Extract any travel information from the user's message into the "extracted" field
2. NEVER ask for information they already provided — check the Current State above
3. Always acknowledge what the user said before asking for more
4. If the city or duration is missing, ask for ONE thing at a time — start with the city, then duration.
   Ask for a SPECIFIC city name (e.g. "Cairo", "Luxor").
   CRITICAL: The system has data ONLY for cities, NOT for countries.
   - If the user says "Egypt", "France", or any country → do NOT set destination_city.
     Instead, reply: "Which city in that country?" and leave destination_city as null.
   - If the user says "Cairo" → set destination_city = "Cairo" and proceed.
   - If the user says a city name in another country → that's fine as long as it's a city.

5. **Interest question**: After the city + duration are both set, ask about their interests.
   Tell them they can:
   - Type their interests (e.g. "history, food, art")
   - Upload a photo showing what they like (the system will analyse it)
   - Say "no preference" / "surprise me" to skip (interests will be left empty)
   If interests are already provided (from a previous turn or from an image), do NOT ask again.

6. NEVER ask about budget, pace, style, food, accommodation, traveler count, dates, or traveler group — those are all handled by smart defaults.
7. Be warm but concise — no filler words
8. Respond in the same language the user writes in
9. NEVER confirm or ask "Is that correct?" — if the user provides a clear answer, accept it immediately.
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

    # In HOTEL_SELECTION phase, show hotels with numbers so the user can pick
    hotels = state.itinerary.get("accommodation_suggestions", [])
    if hotels and state.phase == ConversationPhase.HOTEL_SELECTION:
        lines.append("\n## Available Hotels (choose one):")
        for i, h in enumerate(hotels, 1):
            name = h.get("name", "?")
            rating = h.get("rating", 0)
            acc_type = h.get("accommodation_type", "")
            lines.append(f"  {i}. {name} ({acc_type}, rating={rating})")
        lines.append("\nThe user must pick a hotel (by number or name). If they say 'looks good' or 'approve', select the first hotel (number 1).")
    elif hotels:
        hotel_names = [h.get("name", "?") for h in hotels[:3]]
        lines.append(f"Hotels: {', '.join(hotel_names)}")

    # In FLIGHT_SELECTION phase, show flight search results if available
    if state.phase == ConversationPhase.FLIGHT_SELECTION:
        slots = state.slots
        if slots.flight_search_results and not slots.selected_flight_offer:
            lines.append("\n## Available Flights (choose one):")
            for i, f in enumerate(slots.flight_search_results[:5], 1):
                airline = f.get("airline_name", f.get("airline_code", "?"))
                flight_num = f.get("flight_number", "?")
                depart = f.get("departure_at_formatted", "")
                arrival = f.get("arrival_at_formatted", "")
                price = f.get("total_price", "?")
                currency = f.get("currency", "")
                origin = f.get("origin_iata", "")
                dest = f.get("destination_iata", "")
                lines.append(f"  {i}. {airline} {flight_num}: {origin}→{dest}, {depart}→{arrival}, {price} {currency}")
            lines.append("\nThe user can pick a flight by number (e.g. 'flight 2') or name (e.g. 'the Emirates one').")
        elif not slots.origin_city:
            lines.append("\nAsk the user where they will be flying FROM (origin city).")
        elif not slots.flight_search_results:
            lines.append("\nAsk the user if they want to search for flights for this trip.")
        else:
            lines.append("\nA flight has been selected. Ask if the user wants to proceed, or if they'd like to see different options.")

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
    "select_hotel": "select_hotel",
    "hotel_selection": "select_hotel",
    "pick_hotel": "select_hotel",
    "choose_hotel": "select_hotel",
    "modify_itinerary": "modify_itinerary",
    "modify": "modify_itinerary",
    "change": "modify_itinerary",
    "update": "modify_itinerary",
    "search_flights": "search_flights",
    "search_flight": "search_flights",
    "show_flights": "search_flights",
    "find_flights": "search_flights",
    "look_for_flights": "search_flights",
    "select_flight": "select_flight",
    "pick_flight": "select_flight",
    "choose_flight": "select_flight",
    "book_flight": "select_flight",
    "take_flight": "select_flight",
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
    raw["selected_flight_number"] = _coerce_int(raw.get("selected_flight_number"))
    raw = {k: v for k, v in raw.items() if v is not None}
    # Keep select_hotel fields even if they are the only extracted fields
    normalized = normalize_extracted_slots(raw)
    if extracted.selected_hotel_name:
        normalized["selected_hotel_name"] = extracted.selected_hotel_name
    if extracted.selected_hotel_number is not None:
        normalized["selected_hotel_number"] = extracted.selected_hotel_number
    # Flight fields
    if extracted.origin_city:
        normalized["origin_city"] = extracted.origin_city
    if extracted.selected_flight_number is not None:
        normalized["selected_flight_number"] = extracted.selected_flight_number
    if extracted.cabin_class:
        normalized["cabin_class"] = extracted.cabin_class
    if extracted.is_round_trip is not None:
        normalized["is_round_trip"] = extracted.is_round_trip
    if extracted.return_date:
        normalized["return_date"] = extracted.return_date
    return normalized


# ── Main Interpreter Function ───────────────────────────────────────────────

@traced(name="message_interpreter", tags=["conversation", "interpreter"], metadata={"component": "message_interpreter"})
async def interpret_message(state: ConversationState, user_message: str) -> InterpretationResult:
    """Single context-aware LLM call with structured output."""
    slots = state.slots
    missing = slots.missing_required()
    missing_str = ", ".join(missing) if missing else "none — all info collected!"

    itinerary_context = ""
    if state.phase in (ConversationPhase.ITINERARY_REVIEW, ConversationPhase.FLIGHT_SELECTION, ConversationPhase.HOTEL_SELECTION):
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

    # Safety override: if user is in hotel_selection phase and the LLM
    # chose something other than select_hotel, check if the message
    # sounds like they're picking a hotel.
    if state.phase == ConversationPhase.HOTEL_SELECTION and action != "select_hotel":
        msg_lower = user_message.lower()
        hotel_keywords = ["hotel", "pick ", "choose ", "select ", "i'll take",
                         "i want ", "number ", "first one", "second one", "third one",
                         "looks good", "go with", "stay at"]
        if any(kw in msg_lower for kw in hotel_keywords):
            logger.info(
                "[Interpreter] Safety override: '%s' → select_hotel (phase=%s, action=%s)",
                user_message[:60], state.phase.value, action,
            )
            action = "select_hotel"

    # Safety override: if user is in flight_selection phase and the LLM
    # chose something other than flight or approve actions, check if the
    # message sounds like a flight query.
    if state.phase == ConversationPhase.FLIGHT_SELECTION and action not in ("search_flights", "select_flight", "approve_itinerary"):
        msg_lower = user_message.lower()
        flight_keywords = ["fly", "flight", "from ", "airport", "book", "ticket", "plane", "class"]
        number_keywords = ["first", "second", "third", "1st", "2nd", "3rd", "pick ", "choose ", "i'll take", "i want ", "number ", "option"]
        if any(kw in msg_lower for kw in flight_keywords):
            logger.info(
                "[Interpreter] Safety override: '%s' → search_flights (phase=%s, action=%s)",
                user_message[:60], state.phase.value, action,
            )
            action = "search_flights"
        elif any(kw in msg_lower for kw in number_keywords):
            logger.info(
                "[Interpreter] Safety override: '%s' → select_flight (phase=%s, action=%s)",
                user_message[:60], state.phase.value, action,
            )
            action = "select_flight"

        # If the user provided a travel_date, round-trip flag, or return_date,
        # route back to search_flights so _handle_search_flights can use them.
        if extracted.get("travel_dates") or extracted.get("is_round_trip") is not None or extracted.get("return_date"):
            logger.info(
                "[Interpreter] Safety override: '%s' → search_flights (phase=%s)",
                user_message[:60], state.phase.value,
            )
            action = "search_flights"

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
            # Only force plan_trip if interests are meaningfully provided
            # (non-empty list). The LLM's structured output may return `[]`
            # as a default for Optional[List[str]] fields, which should NOT
            # be treated as "interests provided."
            extracted_interests = extracted.get("interests")
            state_interests = state.slots.interests
            interests_ok = (
                bool(extracted_interests)              # user actively provided interests this turn
                or state_interests is not None          # already handled in a previous turn
            )
            if interests_ok and action not in ("approve_itinerary", "modify_itinerary"):
                action = "plan_trip"

    return InterpretationResult(
        action=action,
        extracted=extracted,
        response=response_text,
    )
