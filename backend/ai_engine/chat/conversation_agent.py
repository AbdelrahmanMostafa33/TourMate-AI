# backend/ai_engine/chat/conversation_agent.py
"""Stateful conversation agent with Redis-backed session management.

Uses a unified router that replaces the previous 3-call pattern (intent parser +
clarification + general chat) with a single intelligent call that sees
full conversation history and current state.

The shared routing logic lives in _process_message(), which both the synchronous
(handle_chat) and streaming (handle_chat_stream) entry points delegate to.
"""

import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Optional

from ai_engine.constants import PLAN_GENERATION_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)

# Per-user locks to prevent concurrent state mutations on the same session.
# Bounded LRU dict to avoid unbounded memory growth.
_MAX_USER_LOCKS = 512
_user_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()

# Core routing LLM that decides what the user wants (plan, clarify, chat, etc.)
from ai_engine.chat.unified_router import route_message

# Conversation state machine + slot tracking (memory of user preferences)
from ai_engine.memory.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
)

# Redis session manager (load/save conversation state per user/session)
from ai_engine.memory.redis_memory import get_session_manager

# LangGraph-based itinerary generation pipeline
from ai_engine.graph.graph_builder import trip_graph

# Image analysis pipeline for travel-related images
from ai_engine.vision.image_analyzer import analyze_travel_image

# Fusion logic: merges image signals into user travel profile
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile

# Profile loaders (real backend vs fallback mock profile)
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile

# LangSmith tracing
from ai_engine.observability import traced


# ── Shared Core ────────────────────────────────────────────────────────────────


@traced(name="process_message", tags=["conversation", "routing"], metadata={"component": "conversation_agent"})
async def _process_message(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    image_features: Optional[dict],
    token: Optional[str],
) -> dict:
    """Core routing logic shared by handle_chat and handle_chat_stream.

    This function:
    - Sends message to unified router (LLM decision layer)
    - Updates conversation state + slots
    - Decides next action (plan, clarify, modify, chat, etc.)
    - Triggers itinerary generation when needed
    - DOES NOT persist state (caller handles Redis save)

    Returns a response dict.  On unexpected errors, returns a safe
    fallback response instead of crashing the caller.
    """

    try:
        return await _process_message_inner(user_id, state, effective_message, image_features, token)
    except Exception:
        logger.exception("[ConversationAgent] Unexpected error processing message for user %s", user_id)
        # NOTE: We intentionally do NOT call state.add_assistant_message() here
        # because _process_message_inner may have partially modified state before
        # the error.  The caller (handle_chat) saves whatever state exists.
        return {
            "response_type": "chat",
            "message": "I ran into an unexpected issue. Please try again.",
            "itinerary": None,
            "image_features": None,
        }


async def _process_message_inner(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    image_features: Optional[dict],
    token: Optional[str],
) -> dict:
    """Inner routing logic — wrapped by _process_message for error safety."""

    # ─────────────────────────────────────────────────────────────
    # CASE 1: System is currently generating itinerary
    # Check for timeout — if pipeline crashed, reset to slot-filling
    # ─────────────────────────────────────────────────────────────
    if state.phase == ConversationPhase.PLAN_GENERATION:

        # Check if PLAN_GENERATION has timed out (pipeline crashed)
        if state.plan_started_at:
            started = datetime.fromisoformat(state.plan_started_at)
            elapsed = datetime.now(timezone.utc) - started
            if elapsed > timedelta(minutes=PLAN_GENERATION_TIMEOUT_MINUTES):
                # Pipeline timed out — reset to slot-filling so user can retry
                state.transition_to(ConversationPhase.SLOT_FILLING)
                state.plan_started_at = None
                response = {
                    "response_type": "clarification",
                    "message": "I ran into an issue generating your itinerary. Let's start fresh — what kind of trip are you thinking of?",
                    "itinerary": None,
                    "image_features": None,
                }
                state.add_user_message(effective_message)
                state.add_assistant_message(response["message"])
                return response

        response = {
            "response_type": "chat",
            "message": "I'm working on your personalized itinerary! It'll be ready shortly.",
            "itinerary": None,
            "image_features": None,
        }

        # Store user message in history
        state.add_user_message(effective_message)

        # Store assistant acknowledgment
        if response.get("message"):
            state.add_assistant_message(response["message"])

        return response

    # ─────────────────────────────────────────────────────────────
    # STEP 1: Call unified router (single LLM decision point)
    # It returns:
    # - action (plan_trip / ask_clarification / etc.)
    # - extracted slots (destination, dates, budget, etc.)
    # - response text
    # ─────────────────────────────────────────────────────────────
    router_result = await route_message(state, effective_message)

    # Merge newly extracted structured data into accumulated slots
    state.slots.merge(router_result.extracted)

    # Store user message with metadata (action chosen by router)
    state.add_user_message(effective_message, metadata={"action": router_result.action})

    # ─────────────────────────────────────────────────────────────
    # SAFETY OVERRIDE:
    # If router says "ask_clarification" BUT we already have all slots,
    # we override to "plan_trip" to avoid blocking itinerary generation
    # ─────────────────────────────────────────────────────────────
    action = router_result.action
    if action == "ask_clarification" and state.slots.is_complete():
        action = "plan_trip"

    # Track which field we're asking about so the next turn can disambiguate
    # short answers (e.g. 'mixed' → pace, not food_preferences)
    if action in ("ask_clarification", "plan_trip") and not state.slots.is_complete():
        missing = state.slots.missing_required()
        if missing:
            state.last_question_field = missing[0]
    else:
        state.last_question_field = None

    response = None

    # ─────────────────────────────────────────────────────────────
    # ACTION: PLAN TRIP
    # Either start itinerary generation or ask for missing info
    # ─────────────────────────────────────────────────────────────
    if action == "plan_trip":

        # Move conversation into slot-filling phase if just started
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)

        # If all required info is collected → generate itinerary
        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            state.plan_started_at = datetime.now(timezone.utc).isoformat()

            response = await _handle_plan_trip(
                user_id,
                effective_message,
                router_result.extracted,
                image_features,
                token,
                state
            )

        # Otherwise ask user for missing details
        else:
            if state.phase != ConversationPhase.SLOT_FILLING:
                state.transition_to(ConversationPhase.SLOT_FILLING)

            response = {
                "response_type": "clarification",
                "message": router_result.response,
                "itinerary": None,
                "image_features": image_features,
            }

    # ─────────────────────────────────────────────────────────────
    # ACTION: ASK CLARIFICATION (missing or ambiguous info)
    # ─────────────────────────────────────────────────────────────
    elif action == "ask_clarification":
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)

        response = {
            "response_type": "clarification",
            "message": router_result.response,
            "itinerary": None,
            "image_features": image_features,
        }

    # ─────────────────────────────────────────────────────────────
    # ACTION: APPROVE EXISTING ITINERARY
    # ─────────────────────────────────────────────────────────────
    elif action == "approve_itinerary":
        state.approve_itinerary(itinerary_id=None)

        response = {
            "response_type": "chat",
            "message": router_result.response,
            "itinerary": None,
            "image_features": None,
        }

    # ─────────────────────────────────────────────────────────────
    # ACTION: MODIFY EXISTING ITINERARY
    # ─────────────────────────────────────────────────────────────
    elif action == "modify_itinerary":

        # Only allow modification during review phase
        if state.phase == ConversationPhase.ITINERARY_REVIEW:

            state.transition_to(ConversationPhase.PLAN_GENERATION)
            state.plan_started_at = datetime.now(timezone.utc).isoformat()

            # Merge modification request into special_requests
            extracted = dict(router_result.extracted)
            extracted["special_requests"] = (
                f"{state.slots.special_requests or ''} | Modification: {effective_message}"
            ).strip(" | ")

            response = await _handle_plan_trip(
                user_id,
                effective_message,
                extracted,
                image_features,
                token,
                state
            )
        else:
            response = {
                "response_type": "chat",
                "message": router_result.response,
                "itinerary": None,
                "image_features": image_features,
            }

    # ─────────────────────────────────────────────────────────────
    # ACTION: ANSWER A QUESTION ABOUT CURRENT CONTEXT
    # ─────────────────────────────────────────────────────────────
    elif action == "answer_question":
        response = {
            "response_type": "chat",
            "message": router_result.response,
            "itinerary": state.itinerary
                if state.phase == ConversationPhase.ITINERARY_REVIEW
                else None,
            "image_features": image_features,
        }

    # ─────────────────────────────────────────────────────────────
    # DEFAULT ACTION: fallback chat response
    # ─────────────────────────────────────────────────────────────
    else:
        response = {
            "response_type": "chat",
            "message": router_result.response or "I'm here to help!",
            "itinerary": None,
            "image_features": image_features,
        }

    # ─────────────────────────────────────────────────────────────
    # HANDLE COMPLETED STATE:
    # If a new trip starts after finishing previous one
    # ─────────────────────────────────────────────────────────────
    if state.phase == ConversationPhase.COMPLETED and action in ("plan_trip", "ask_clarification"):
        state.reset_for_new_trip()

        # Re-apply newly extracted data
        state.slots.merge(router_result.extracted)

        # If enough info → generate new itinerary
        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            state.plan_started_at = datetime.now(timezone.utc).isoformat()

            response = await _handle_plan_trip(
                user_id,
                effective_message,
                router_result.extracted,
                image_features,
                token,
                state
            )
        else:
            state.transition_to(ConversationPhase.SLOT_FILLING)

            response = {
                "response_type": "clarification",
                "message": router_result.response,
                "itinerary": None,
                "image_features": image_features,
            }

    # ─────────────────────────────────────────────────────────────
    # FINAL STATE UPDATES
    # Attach generated itinerary + store assistant message in memory
    # ─────────────────────────────────────────────────────────────
    if response and response.get("itinerary"):
        state.set_itinerary(response["itinerary"])

    if response and response.get("message"):
        state.add_assistant_message(response["message"])

    return response


def _prepare_message(user_message: Optional[str]) -> str:
    """Normalize user message to ensure we never pass empty input to LLM."""

    effective_message = (user_message or "").strip()

    # If user sends empty message (e.g. image-only upload)
    # we convert it into a default semantic message
    if not effective_message:
        effective_message = "I uploaded an image for my trip."

    return effective_message


def _parse_image(image_bytes: Optional[bytes]) -> Optional[dict]:
    """Run image understanding pipeline if image is provided."""

    if image_bytes:
        return analyze_travel_image(image_bytes)

    return None


# ── Public API ─────────────────────────────────────────────────────────────────


def _get_user_lock(user_id: str) -> asyncio.Lock:
    """Return (and lazily create) an asyncio.Lock for *user_id*.

    Prevents concurrent state mutations when multiple requests arrive
    for the same user (e.g. rapid double-tap on mobile).  Uses an LRU
    eviction strategy so the dict doesn't grow unbounded.
    """
    if user_id in _user_locks:
        _user_locks.move_to_end(user_id)
    else:
        if len(_user_locks) >= _MAX_USER_LOCKS:
            _user_locks.popitem(last=False)  # evict oldest
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


@traced(
    name="handle_chat",
    tags=["conversation", "entry_point"],
    metadata={"component": "conversation_agent"},
)
async def handle_chat(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Main synchronous chat entry point (stateful, non-streaming).

    Handles a user's message by:
    1. Loading or creating a conversation session.
    2. Preparing the incoming text and image data.
    3. Routing the request through the conversation workflow.
    4. Persisting the updated session state.
    5. Returning the response with session metadata.
    """
    lock = _get_user_lock(user_id)
    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id)

        effective_message = _prepare_message(user_message)
        image_features = _parse_image(image_bytes)

        response = await _process_message(
            user_id, state, effective_message, image_features, token
        )

        await manager.save(state)

        # Extend session TTL on each interaction so active sessions
        # don't expire while the user is still chatting.
        await manager.extend_ttl(state.session_id)

        if response:
            response["session_id"] = state.session_id
            response["phase"] = state.phase.value

        return response


async def handle_chat_stream(user_id, user_message, image_bytes=None, token=None, session_id=None):
    """Streaming entry point (used for WebSocket / token streaming).

    The lock is held only during state processing (route + save + TTL).
    Yielding chunks happens outside the lock so other requests for the
    same user are not blocked while the client consumes the stream.
    """
    lock = _get_user_lock(user_id)

    # ── Process under lock ────────────────────────────────────────────
    # State must be loaded inside the lock so concurrent requests for the
    # same user always see the latest saved state.
    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id)

        # Emit session info so the client can update UI.
        yield {
            "type": "session",
            "data": {
                "session_id": state.session_id,
                "phase": state.phase.value,
            }
        }

        effective_message = _prepare_message(user_message)
        image_features = _parse_image(image_bytes)

        response = await _process_message(
            user_id, state, effective_message, image_features, token
        )

        await manager.save(state)
        await manager.extend_ttl(state.session_id)

        phase_value = state.phase.value

    # ── Yield outside lock ────────────────────────────────────────────
    yield {
        "type": "phase",
        "data": {"phase": phase_value}
    }

    message = response.get("message", "I'm here to help!") if response else "I'm here to help!"
    async for chunk in _stream_text(message):
        yield chunk

    yield {"type": "done", "data": None}


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _stream_text(text: str):
    """Yield word-by-word chunks for streaming responses."""

    for word in text.split():
        yield {"type": "text", "content": word + " "}


def _build_profile_from_slots(slots: TripSlots, trip_id: str) -> dict:
    """Convert collected slot data into a structured TripProfile object."""

    from ai_engine.graph.state import TripProfile

    return TripProfile(
        profile_id=None,
        trip_id=trip_id,

        # Core trip preferences extracted from conversation
        budget_level=slots.budget_level,
        travel_style=slots.travel_style,
        pace=slots.pace,
        interests=slots.interests or [],
        food_preferences=slots.food_preferences or [],
        accommodation_preferences=slots.accommodation_preferences or [],

        # Optional scoring fields (can be computed later)
        luxury_score=None,
        culture_score=None,
        adventure_score=None,
        shopping_score=None,
        family_score=None,

        confidence=None,
        generated_at=None,
        updated_at=None,
    )


def _build_conversation_context(state) -> str:
    """
    Create a compact textual summary of full conversation history.

    This helps downstream AI agents understand full context,
    not just the latest user message.
    """

    lines = []

    # Convert chat history into readable format
    for msg in (state.history or []):
        role = msg.role.capitalize()
        content = (msg.content or "")[:150]  # avoid overly long context
        lines.append(f"{role}: {content}")

    return "\n".join(lines)


@traced(name="plan_trip_pipeline", tags=["conversation", "pipeline"], metadata={"component": "conversation_agent"})
async def _handle_plan_trip(user_id, user_message, extracted, image_features, token=None, state=None):
    """Runs full LangGraph itinerary generation pipeline."""

    # Determine trip identifier
    trip_id = getattr(state, 'trip_id', None) or user_id

    # ─────────────────────────────────────────────────────────────
    # PROFILE SELECTION STRATEGY:
    # 1. If slots are complete → build profile from conversation
    # 2. Else try backend API profile
    # 3. Else fallback mock profile
    # ─────────────────────────────────────────────────────────────
    if state and state.slots.is_complete():
        profile = _build_profile_from_slots(state.slots, trip_id)

        logger.info(
            "[ChatHandler] Built profile from slots: budget=%s, style=%s, pace=%s",
            profile.get('budget_level'), profile.get('travel_style'), profile.get('pace'),
        )

    elif token:
        try:
            profile = await load_trip_profile(trip_id=trip_id, token=token)
        except Exception as e:
            logger.warning("[ChatHandler] Failed to load real profile (%s), falling back to mock", e)
            profile = load_mock_profile(trip_id=trip_id)
    else:
        profile = load_mock_profile(trip_id=trip_id)

    # Enhance profile using image signals (if available and reliable)
    if image_features and image_features.get("confidence") != "low":
        profile = fuse_image_with_profile(profile, image_features)

    # ─────────────────────────────────────────────────────────────
    # Build initial LangGraph state for itinerary generation
    # ─────────────────────────────────────────────────────────────
    s = state.slots if state else None

    initial_state = {
        "user_id": user_id,
        "user_message": user_message,
        "profile": profile,
        "token": token,
        "trip_id": trip_id,

        # Planning pipeline fields
        "extracted_preferences": None,
        "filtered_places": None,
        "candidate_places": None,
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "is_valid": None,
        "validation": None,
        "planning_attempts": 0,
        "next_agent": None,
        "error": None,
        "intent_type": "plan_trip",

        # Core trip parameters (from slots or latest extraction)
        "destination_city": (s.destination_city if s else None) or extracted.get("destination_city"),
        "destination_country": (s.destination_country if s else None) or extracted.get("destination_country"),
        "duration_days": (s.duration_days if s else None) or extracted.get("duration_days"),
        "travel_dates": (s.travel_dates if s else None) or extracted.get("travel_dates"),
        "special_requests": (s.special_requests if s else None) or extracted.get("special_requests"),
        "group_size": (s.group_size if s else None) or extracted.get("group_size"),

        "missing_fields": extracted.get("missing_fields", []),
        "agent_messages": [],
    }

    # Add full conversation history context for better planning quality
    conv_context = _build_conversation_context(state) if state else None
    if conv_context:
        initial_state["conversation_context"] = conv_context

    # Execute LangGraph itinerary pipeline
    result_state = await trip_graph.ainvoke(initial_state)

    return {
        "response_type": "itinerary",
        "message": "Here's your personalized itinerary!",
        "itinerary": result_state.get("optimized_itinerary"),
        "image_features": image_features,
    }