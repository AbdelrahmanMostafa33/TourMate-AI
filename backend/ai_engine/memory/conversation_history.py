# ai_engine/memory/conversation_history.py

"""
ConversationHistory: builds LLM-ready context from ConversationState.

This module provides utilities to:
    - Format the session's message history into LangChain messages
    - Build system prompts enriched with conversation context
    - Generate slot-filling prompts for missing trip information
    - Create itinerary review prompts with the current plan

These helpers are used by conversation_agent.py to inject conversation state
into LLM calls without duplicating logic.
"""

from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from ai_engine.memory.conversation_state import ConversationPhase, ConversationState


# ── System Prompt Templates ───────────────────────────────────────────────────

_GREETING_PROMPT = """\
You are TourMate AI, a friendly travel planning assistant.
The user just connected.  Greet them warmly and ask how you can help
with their travel plans.  Keep it to 1-2 sentences.
"""

_SLOT_FILLING_PROMPT = """\
You are TourMate AI, a friendly travel planning assistant.

You are currently collecting trip information from the user.

{slot_context}

Generate exactly ONE friendly, natural-sounding question to ask the user
for the missing information.  Do not list options.  Do not use bullet points.
Keep it to one or two sentences maximum.

If you already have all required information (destination and duration),
say something like "I have everything I need!" and move on.
"""

_PLAN_GENERATION_PROMPT = """\
You are TourMate AI.  The user has provided all trip details and the
itinerary is being generated.  Tell them briefly that you're working
on their personalized plan (1 sentence).  Do NOT fabricate an itinerary.
"""

_ITINERARY_REVIEW_PROMPT = """\
You are TourMate AI, a friendly travel planning assistant.

The user's itinerary has been generated.  Present it to them and ask
if they'd like any changes.  Be enthusiastic but concise.

{itinerary_context}
"""

_GENERAL_CHAT_PROMPT = """\
You are TourMate AI, a knowledgeable and friendly travel assistant.
Answer the user's travel-related question concisely and helpfully
in 2-4 sentences.  If the question is unrelated to travel, gently
redirect to travel topics.  Do not offer to generate an itinerary
unless the user asks for one.
"""


# ── Message Builders ──────────────────────────────────────────────────────────

def build_messages_for_phase(
    state: ConversationState,
    user_message: str,
) -> List[BaseMessage]:
    """
    Build a list of LangChain messages appropriate for the current phase.

    This is the main entry point for converting session state into LLM input.
    It selects the right system prompt based on the phase, injects the
    conversation context, and includes the user's message.

    Args:
        state:       The current ConversationState.
        user_message: The latest user message text.

    Returns:
        List of LangChain BaseMessage objects ready for LLM.invoke().
    """
    messages: List[BaseMessage] = []

    # ── System message (phase-specific) ──────────────────────────────────────
    system_content = _build_system_prompt(state)
    messages.append(SystemMessage(content=system_content))

    # ── Recent conversation history ──────────────────────────────────────────
    # Include the last few messages so the LLM has conversational context.
    recent = state.history[-6:]  # last 6 messages (3 turns)
    for msg in recent:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    # ── Current user message ─────────────────────────────────────────────────
    messages.append(HumanMessage(content=user_message))

    return messages


def build_clarification_messages(
    missing_fields: List[str],
    history: Optional[List[dict]] = None,
) -> List[BaseMessage]:
    """
    Build messages for generating a clarifying question.

    Args:
        missing_fields: List of field names still needed.
        history:        Optional recent message history dicts.

    Returns:
        List of LangChain messages.
    """
    missing_str = " and ".join(missing_fields) if missing_fields else "destination and duration"

    messages: List[BaseMessage] = [
        SystemMessage(content=_SLOT_FILLING_PROMPT.format(
            slot_context=f"Missing fields: {missing_str}"
        )),
    ]

    # Add history context if provided
    if history:
        for msg in history[-4:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content="Generate the clarifying question now."))
    return messages


def build_general_chat_messages(
    user_message: str,
    history: Optional[List[dict]] = None,
    image_context: Optional[str] = None,
) -> List[BaseMessage]:
    """
    Build messages for general travel chat.

    Args:
        user_message: The user's latest message.
        history:      Optional recent message history dicts.
        image_context: Optional context string from image analysis.

    Returns:
        List of LangChain messages.
    """
    messages: List[BaseMessage] = [
        SystemMessage(content=_GENERAL_CHAT_PROMPT),
    ]

    # Add history
    if history:
        for msg in history[-4:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    # Build enriched message
    enriched = user_message
    if image_context:
        enriched = f"{user_message}\n\n{image_context}"

    messages.append(HumanMessage(content=enriched))
    return messages


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_system_prompt(state: ConversationState) -> str:
    """Build the appropriate system prompt for the current phase."""
    phase = state.phase

    if phase == ConversationPhase.GREETING:
        return _GREETING_PROMPT

    elif phase == ConversationPhase.SLOT_FILLING:
        slot_context = _format_slot_context(state)
        return _SLOT_FILLING_PROMPT.format(slot_context=slot_context)

    elif phase == ConversationPhase.PLAN_GENERATION:
        return _PLAN_GENERATION_PROMPT

    elif phase == ConversationPhase.ITINERARY_REVIEW:
        itinerary_context = _format_itinerary_context(state)
        return _ITINERARY_REVIEW_PROMPT.format(itinerary_context=itinerary_context)

    elif phase == ConversationPhase.COMPLETED:
        return (
            "You are TourMate AI.  The user has approved their itinerary.  "
            "Be friendly and wish them a great trip!  If they want to plan "
            "another trip, guide them to start a new conversation."
        )

    else:
        return _GENERAL_CHAT_PROMPT


def _format_slot_context(state: ConversationState) -> str:
    """Format the collected and missing slots into a readable context string."""
    lines = []

    collected = []
    if state.slots.destination_city:
        collected.append(f"destination: {state.slots.destination_city}")
    if state.slots.destination_country:
        collected.append(f"country: {state.slots.destination_country}")
    if state.slots.duration_days:
        collected.append(f"duration: {state.slots.duration_days} days")
    if state.slots.travel_dates:
        collected.append(f"dates: {state.slots.travel_dates}")
    if state.slots.group_size:
        collected.append(f"group size: {state.slots.group_size}")
    if state.slots.traveler_group_type:
        collected.append(f"traveler group: {state.slots.traveler_group_type}")
    if state.slots.special_requests:
        collected.append(f"special requests: {state.slots.special_requests}")

    if collected:
        lines.append("Collected so far:")
        for c in collected:
            lines.append(f"  - {c}")

    missing = state.slots.missing_required()
    if missing:
        lines.append(f"\nStill need: {', '.join(missing)}")
    else:
        lines.append("\nAll required information collected!")

    return "\n".join(lines)


def _format_itinerary_context(state: ConversationState) -> str:
    """Format the current itinerary for the LLM prompt."""
    if not state.itinerary:
        return "(Itinerary is being generated...)"

    # Summarize the itinerary for the prompt
    lines = []
    days = state.itinerary.get("days", [])
    for day in days:
        day_num = day.get("day_number", "?")
        stops = day.get("stops", [])
        lines.append(f"Day {day_num}: {len(stops)} activities")
        for stop in stops[:3]:  # Show first 3 stops per day
            name = stop.get("name", "Unknown")
            time = stop.get("start_time", "")
            lines.append(f"  - {time} {name}" if time else f"  - {name}")
        if len(stops) > 3:
            lines.append(f"  ... and {len(stops) - 3} more")

    return "\n".join(lines) if lines else "(No itinerary details available)"


def get_missing_fields_from_state(state: ConversationState) -> List[str]:
    """
    Extract missing required fields from the conversation state.

    This is used by the slot-filling logic to determine what
    to ask the user next.
    """
    return state.slots.missing_required()
