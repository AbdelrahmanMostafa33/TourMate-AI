# backend/ai_engine/chat/conversation_agent.py
"""Stateful conversation agent with Redis-backed session management.

Uses a unified router that replaces the previous 3-call pattern (intent parser +
clarification + general chat) with a single intelligent call that sees
full conversation history and current state.

The shared routing logic lives in _process_message(), which both the synchronous
(handle_chat) and streaming (handle_chat_stream) entry points delegate to.
"""

from typing import Optional

from ai_engine.chat.unified_router import route_message
from ai_engine.memory.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
)
from ai_engine.memory.redis_memory import get_session_manager
from ai_engine.graph.graph_builder import trip_graph
from ai_engine.vision.image_analyzer import analyze_travel_image
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile


# ── Shared Core ────────────────────────────────────────────────────────────────


async def _process_message(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    image_features: Optional[dict],
    token: Optional[str],
) -> dict:
    """Core routing logic shared by handle_chat and handle_chat_stream.

    Routes the message through the unified router, handles phase transitions,
    and returns a response dict. Does NOT save state — the caller is responsible
    for saving after streaming is complete (if streaming) or immediately.
    """
    # Handle PLAN_GENERATION phase — plan is being generated, acknowledge and wait
    if state.phase == ConversationPhase.PLAN_GENERATION:
        response = {
            "response_type": "chat",
            "message": "I'm working on your personalized itinerary! It'll be ready shortly.",
            "itinerary": None,
            "image_features": None,
        }
        state.add_user_message(effective_message)
        if response.get("message"):
            state.add_assistant_message(response["message"])
        return response

    # Single context-aware LLM call
    router_result = await route_message(state, effective_message)
    state.slots.merge(router_result.extracted)
    state.add_user_message(effective_message, metadata={"action": router_result.action})

    # Post-merge override: if slots are now complete but the router
    # returned ask_clarification (e.g. asking about optional group_size),
    # override to plan_trip so the pipeline triggers.
    action = router_result.action
    if action == "ask_clarification" and state.slots.is_complete():
        action = "plan_trip"

    response = None

    if action == "plan_trip":
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)
        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            response = await _handle_plan_trip(
                user_id, effective_message, router_result.extracted, image_features, token, state
            )
        else:
            if state.phase != ConversationPhase.SLOT_FILLING:
                state.transition_to(ConversationPhase.SLOT_FILLING)
            response = {"response_type": "clarification", "message": router_result.response,
                        "itinerary": None, "image_features": image_features}

    elif action == "ask_clarification":
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)
        response = {"response_type": "clarification", "message": router_result.response,
                    "itinerary": None, "image_features": image_features}

    elif action == "approve_itinerary":
        state.approve_itinerary(itinerary_id=None)
        response = {"response_type": "chat", "message": router_result.response,
                    "itinerary": None, "image_features": None}

    elif action == "modify_itinerary":
        if state.phase == ConversationPhase.ITINERARY_REVIEW:
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            extracted = dict(router_result.extracted)
            extracted["special_requests"] = (
                f"{state.slots.special_requests or ''} | Modification: {effective_message}"
            ).strip(" | ")
            response = await _handle_plan_trip(
                user_id, effective_message, extracted, image_features, token, state
            )
        else:
            response = {"response_type": "chat", "message": router_result.response,
                        "itinerary": None, "image_features": image_features}

    elif action == "answer_question":
        response = {"response_type": "chat", "message": router_result.response,
                    "itinerary": state.itinerary if state.phase == ConversationPhase.ITINERARY_REVIEW else None,
                    "image_features": image_features}
    else:
        response = {"response_type": "chat", "message": router_result.response or "I'm here to help!",
                    "itinerary": None, "image_features": image_features}

    # Handle COMPLETED phase — new trip detection
    if state.phase == ConversationPhase.COMPLETED and action in ("plan_trip", "ask_clarification"):
        state.reset_for_new_trip()
        state.slots.merge(router_result.extracted)
        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            response = await _handle_plan_trip(
                user_id, effective_message, router_result.extracted, image_features, token, state
            )
        else:
            state.transition_to(ConversationPhase.SLOT_FILLING)
            response = {"response_type": "clarification", "message": router_result.response,
                        "itinerary": None, "image_features": image_features}

    # Attach itinerary to state if present
    if response and response.get("itinerary"):
        state.set_itinerary(response["itinerary"])
    if response and response.get("message"):
        state.add_assistant_message(response["message"])

    return response


def _prepare_message(user_message: Optional[str]) -> str:
    """Normalize user message to a non-empty string."""
    effective_message = (user_message or "").strip()
    if not effective_message:
        effective_message = "I uploaded an image for my trip."
    return effective_message


def _parse_image(image_bytes: Optional[bytes]) -> Optional[dict]:
    """Analyze uploaded image bytes into features."""
    if image_bytes:
        return analyze_travel_image(image_bytes)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────


async def handle_chat(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Stateful entry point — single context-aware LLM call via unified router."""
    manager = await get_session_manager()
    state = await manager.resume_or_create(user_id, session_id)

    effective_message = _prepare_message(user_message)
    image_features = _parse_image(image_bytes)

    response = await _process_message(user_id, state, effective_message, image_features, token)

    await manager.save(state)
    if response:
        response["session_id"] = state.session_id
        response["phase"] = state.phase.value
    return response


async def handle_chat_stream(user_id, user_message, image_bytes=None, token=None, session_id=None):
    """Streaming variant — yields chunks for WebSocket delivery."""
    manager = await get_session_manager()
    state = await manager.resume_or_create(user_id, session_id)
    yield {"type": "session", "data": {"session_id": state.session_id, "phase": state.phase.value}}

    effective_message = _prepare_message(user_message)
    image_features = _parse_image(image_bytes)

    response = await _process_message(user_id, state, effective_message, image_features, token)

    await manager.save(state)

    message = response.get("message", "I'm here to help!") if response else "I'm here to help!"
    async for chunk in _stream_text(message):
        yield chunk

    yield {"type": "done", "data": None}


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _stream_text(text: str):
    """Yield word-by-word chunks for streaming."""
    for word in text.split():
        yield {"type": "text", "content": word + " "}


def _build_profile_from_slots(slots: TripSlots, trip_id: str) -> dict:
    """Build a TripProfile from collected slot data."""
    from ai_engine.graph.state import TripProfile
    return TripProfile(
        profile_id=None, trip_id=trip_id,
        budget_level=slots.budget_level, travel_style=slots.travel_style, pace=slots.pace,
        interests=slots.interests or [], food_preferences=slots.food_preferences or [],
        accommodation_preferences=slots.accommodation_preferences or [],
        luxury_score=None, culture_score=None, adventure_score=None, shopping_score=None,
        family_score=None, confidence=None, generated_at=None, updated_at=None,
    )


def _build_conversation_context(state) -> str:
    """
    Build a conversation context summary from ConversationState history.

    This gives downstream agents (preference, planning) the full picture
    of what the user said across all turns, not just the last message.
    """
    lines = []
    for msg in (state.history or []):
        role = msg.role.capitalize()
        content = (msg.content or "")[:150]  # truncate long messages
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def _handle_plan_trip(user_id, user_message, extracted, image_features, token=None, state=None):
    """Invokes the full LangGraph pipeline for itinerary generation."""
    trip_id = getattr(state, 'trip_id', None) or user_id
    if state and state.slots.is_complete():
        profile = _build_profile_from_slots(state.slots, trip_id)
        print(f"[ChatHandler] Built profile from slots: budget={profile.get('budget_level')}, style={profile.get('travel_style')}, pace={profile.get('pace')}")
    elif token:
        try:
            profile = await load_trip_profile(trip_id=trip_id, token=token)
        except Exception as e:
            print(f"[ChatHandler] Failed to load real profile ({e}), falling back to mock")
            profile = load_mock_profile(trip_id=trip_id)
    else:
        profile = load_mock_profile(trip_id=trip_id)

    if image_features and image_features.get("confidence") != "low":
        profile = fuse_image_with_profile(profile, image_features)

    # Use accumulated slots from state (all turns) as the source,
    # falling back to the current message's extracted dict for new values.
    s = state.slots if state else None
    initial_state = {
        "user_id": user_id, "user_message": user_message, "profile": profile,
        "token": token, "trip_id": trip_id, "extracted_preferences": None,
        "filtered_places": None, "candidate_places": None,
        "draft_itinerary": None, "optimized_itinerary": None,
        "is_valid": None, "validation": None, "planning_attempts": 0,
        "next_agent": None, "error": None, "intent_type": "plan_trip",
        "destination_city": (s.destination_city if s else None) or extracted.get("destination_city"),
        "destination_country": (s.destination_country if s else None) or extracted.get("destination_country"),
        "duration_days": (s.duration_days if s else None) or extracted.get("duration_days"),
        "travel_dates": (s.travel_dates if s else None) or extracted.get("travel_dates"),
        "special_requests": (s.special_requests if s else None) or extracted.get("special_requests"),
        "group_size": (s.group_size if s else None) or extracted.get("group_size"),
        "missing_fields": extracted.get("missing_fields", []),
        "agent_messages": [],
    }

    # Build conversation context from history so downstream agents
    # (preference, planning) have full context, not just the last message.
    conv_context = _build_conversation_context(state) if state else None
    if conv_context:
        initial_state["conversation_context"] = conv_context

    result_state = await trip_graph.ainvoke(initial_state)
    return {
        "response_type": "itinerary", "message": "Here's your personalized itinerary!",
        "itinerary": result_state.get("optimized_itinerary"), "image_features": image_features,
    }
