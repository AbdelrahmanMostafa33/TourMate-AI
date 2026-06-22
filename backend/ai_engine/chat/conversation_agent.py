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

# Itinerary Modifier Agent — surgically edits existing itineraries
from ai_engine.agents.itinerary_modifier_agent import run_itinerary_modifier

# Preference Reranker Agent — interprets vibe changes and re-ranks candidates
from ai_engine.agents.preference_reranker_agent import (
    interpret_preference_adjustment,
    apply_preference_adjustments,
)

# Direct agent imports for re-ranking (skip retrieval, go straight to rank→plan→optimize→validate)
from ai_engine.agents.ranking_agent import run_ranking_agent
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.agents.optimization_agent import run_optimization_agent
from ai_engine.agents.validation_agent import run_validation_agent

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

        # Fill smart defaults for any unset non-mandatory slots so
        # downstream agents always see populated values, even if the
        # user only provided destination + duration.
        state.slots.fill_defaults()

        # If required info (destination + duration) is collected → generate itinerary
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

        # Otherwise ask user for missing destination or duration
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

            # ── TRY 3 STRATEGIES IN ORDER ──────────────────────────
            # 1. Mode 2: Surgical modifier (fast) — for specific edits
            # 2. Mode 1: Preference re-ranking (medium) — for vibe changes
            # 3. Full pipeline regeneration (slow) — fallback

            response = await _handle_modify_itinerary(
                user_id, state, effective_message, router_result,
                image_features, token,
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

        # Fill smart defaults for any unset non-mandatory slots
        state.slots.fill_defaults()

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
    # Store assistant message in memory.
    # NOTE: itinerary phase transitions are handled inside _handle_plan_trip,
    # not here, to avoid double set_itinerary calls.
    # ─────────────────────────────────────────────────────────────
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

    During the pipeline execution (which can take 60-90 s), progress
    events are yielded concurrently so the Flutter client can show the
    user what's happening.
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

        # ── Progress queue + concurrent pipeline ────────────────────
        from ai_engine.graph.progress import get_progress_queue, remove_progress_queue

        progress_queue = get_progress_queue(state.session_id)

        # Run the pipeline as a background task so we can yield progress
        # events from the queue while it executes.
        pipeline_task = asyncio.create_task(
            _process_message(user_id, state, effective_message, image_features, token)
        )

        # If this is a plan_trip action (itinerary generation), yield
        # progress events during execution.  For other actions
        # (clarification, chat), just wait for the result.
        is_planning = state.phase == ConversationPhase.PLAN_GENERATION

        if is_planning:
            # Yield progress events while pipeline runs
            try:
                while not pipeline_task.done():
                    try:
                        progress = await asyncio.wait_for(
                            progress_queue.get(), timeout=0.1
                        )
                        yield {"type": "progress", "data": progress}
                    except asyncio.TimeoutError:
                        continue

                # Drain remaining progress events so the client doesn't
                # miss the last agent's "done" event.
                while True:
                    try:
                        progress = await asyncio.wait_for(
                            progress_queue.get(), timeout=0.1
                        )
                        yield {"type": "progress", "data": progress}
                    except asyncio.TimeoutError:
                        break
            finally:
                remove_progress_queue(state.session_id)

        response = await pipeline_task

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

    # ── Yield structured result if this is an itinerary response ──────
    # The route code (websocket_new_chat / process_message_stream) needs
    # this event to extract the itinerary data and persist it to the DB.
    if response and response.get("response_type") == "itinerary" and response.get("itinerary"):
        result_data = {
            "message": response.get("message", ""),
            "itinerary": response["itinerary"],
            "phase": phase_value,
        }
        if response.get("profile"):
            result_data["profile"] = response["profile"]
        yield {
            "type": "result",
            "data": result_data,
        }

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


def _format_itinerary(itinerary: dict) -> str:
    """Convert a structured itinerary dict into a human-readable text message.

    The itinerary is produced by the LangGraph pipeline as a nested dict with
    days, stops, and accommodation suggestions.  This function formats it into
    a readable summary suitable for displaying in chat.
    """
    if not itinerary:
        return "I wasn't able to generate a complete itinerary. Please try again."

    lines = []
    destination = itinerary.get("destination", "your destination")
    days = itinerary.get("days", [])
    hotels = itinerary.get("accommodation_suggestions", [])

    lines.append(f"🌍 Here's your {len(days)}-day itinerary for {destination}!")
    lines.append("")

    for day in days:
        day_num = day.get("day_number", "?")
        theme = day.get("theme", "")
        stops = day.get("stops", [])

        header = f"📅 Day {day_num}"
        if theme:
            header += f" — {theme}"
        lines.append(header)
        lines.append("-" * 40)

        for stop in stops:
            name = stop.get("name", "Unknown")
            time_slot = stop.get("suggested_time_of_day", "")
            duration = stop.get("estimated_duration_minutes", 0)
            why = stop.get("why_recommended", "")
            travel = stop.get("travel_time_to_next_minutes")
            mode = stop.get("transport_mode", "")

            # Time-of-day emoji
            time_emoji = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}.get(time_slot, "📍")
            time_label = time_slot.capitalize() if time_slot else ""

            line = f"  {time_emoji} {name}"
            if time_label:
                line += f" ({time_label})"
            if duration:
                line += f" — {duration} min"
            lines.append(line)

            if why:
                lines.append(f"    💡 {why}")

            # Place details: category, rating, coordinates, address
            cat = stop.get("category", "")
            sub = stop.get("sub_category", "")
            lat = stop.get("lat")
            lon = stop.get("lon")
            rating = stop.get("rating")
            addr = stop.get("address", "")
            details = []
            if cat or sub:
                details.append(f"{cat}/{sub}" if sub else cat)
            if rating:
                details.append(f"{rating}")
            if lat and lon:
                details.append(f"{lat}, {lon}")
            if details:
                lines.append(f"    📍 {', '.join(details)}")
            if addr:
                lines.append(f"    📫 {addr}")

            if travel is not None and travel > 0:
                mode_emoji = "🚶" if mode == "walking" else "🚗"
                lines.append(f"    {mode_emoji} {travel:.0f} min to next stop")

        lines.append("")

    if hotels:
        lines.append("🏨 Accommodation Suggestions:")
        for hotel in hotels:
            name = hotel.get("name", "Unknown")
            acc_type = hotel.get("accommodation_type", "")
            why = hotel.get("why_recommended", "")
            rating = hotel.get("rating", 0)

            line = f"  • {name}"
            if acc_type:
                line += f" ({acc_type})"
            if rating:
                line += f" ⭐ {rating}"
            lines.append(line)
            if why:
                lines.append(f"    💡 {why}")
        lines.append("")

    lines.append("You can ask me to modify any part of this itinerary, or approve it to proceed!")
    return "\n".join(lines)


@traced(name="modify_itinerary", tags=["conversation", "modify"], metadata={"component": "conversation_agent"})
async def _handle_modify_itinerary(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[dict],
    token: Optional[str],
) -> dict:
    """
    Handle modification requests with 3 strategies in order of speed:

    1. **Mode 2 — Surgical Modifier** (fastest, ~2-3s):
       LLM edits the itinerary JSON directly. Best for "swap X for Y",
       "remove stop Z", "change hotel".

    2. **Mode 1 — Preference Re-Ranking** (medium, ~10s):
       Interpret the vibe change (e.g. "more entertaining"), adjust
       preference scores, re-rank the existing candidate places pool,
       and re-plan. Skips retrieval — only runs rank→plan→optimize→validate.

    3. **Full Pipeline** (slowest, ~15s+):
       Complete regeneration from scratch. Fallback for complex changes.
    """

    # ── Mode 2: Try the surgical modifier first ─────────────────────────
    preferences = {
        "budget_level": state.slots.budget_level,
        "travel_style": state.slots.travel_style,
        "pace": state.slots.pace,
        "interests": state.slots.interests or [],
        "food_preferences": state.slots.food_preferences or [],
    }
    modified = await run_itinerary_modifier(
        current_itinerary=state.itinerary,
        modification_request=effective_message,
        available_places=state.candidate_places or [],
        preferences=preferences,
    )

    if modified is not state.itinerary and modified.get("days"):
        # Modifier succeeded — use the modified itinerary directly
        modifier_note = modified.get("_modifier_note", "")
        message = _format_itinerary(modified)
        state.set_itinerary(modified, candidate_places=state.candidate_places)

        return {
            "response_type": "itinerary",
            "message": message,
            "itinerary": modified,
            "image_features": image_features,
            "agent_messages": [f"[ModifierAgent] {modifier_note}"] if modifier_note else [],
        }

    # ── Mode 1: Try preference re-ranking for vibe changes ──────────────
    if state.candidate_places and len(state.candidate_places) > 5:
        logger.info(
            "[ConversationAgent] Modifier unchanged — trying preference re-ranking "
            "(candidate_places: %d)",
            len(state.candidate_places),
        )

        # 1. Interpret the vibe change
        adjustments = await interpret_preference_adjustment(
            effective_message,
            current_preferences=preferences,
        )

        if adjustments:
            # 2. Apply adjustments
            reranked = await _rerank_and_replan(
                user_id=user_id,
                state=state,
                adjustments=adjustments,
                effective_message=effective_message,
                image_features=image_features,
                token=token,
            )

            if reranked:
                # Success — update state and return
                state.set_itinerary(
                    reranked["itinerary"],
                    candidate_places=reranked.get("candidate_places") or state.candidate_places,
                )

                return {
                    "response_type": "itinerary",
                    "message": _format_itinerary(reranked["itinerary"]),
                    "itinerary": reranked["itinerary"],
                    "image_features": image_features,
                    "agent_messages": reranked.get("agent_messages", []),
                    "validation": reranked.get("validation"),
                }

        logger.info(
            "[ConversationAgent] Preference re-ranking failed or no adjustments — "
            "falling back to full pipeline"
        )

    # ── Mode 3: Full pipeline regeneration ─────────────────────────────
    logger.info(
        "[ConversationAgent] Falling back to full pipeline regeneration"
    )
    state.transition_to(ConversationPhase.PLAN_GENERATION)
    state.plan_started_at = datetime.now(timezone.utc).isoformat()

    extracted = dict(router_result.extracted)
    extracted["special_requests"] = (
        f"{state.slots.special_requests or ''} | Modification: {effective_message}"
    ).strip(" | ")

    return await _handle_plan_trip(
        user_id,
        effective_message,
        extracted,
        image_features,
        token,
        state,
    )


@traced(name="rerank_and_replan", tags=["conversation", "rerank"], metadata={"component": "conversation_agent"})
async def _rerank_and_replan(
    user_id: str,
    state: ConversationState,
    adjustments: dict,
    effective_message: str,
    image_features: Optional[dict] = None,
    token: Optional[str] = None,
) -> dict | None:
    """
    Re-rank the existing candidate places with adjusted preferences, then
    re-run planner → optimizer → validator.  Skips retrieval entirely.

    This is Mode 1 of the editing system.
    """
    try:
        # 1. Build adjusted extracted_preferences for the ranking agent
        adjusted_prefs = apply_preference_adjustments(state.slots, adjustments)

        # 2. Build a TripState-compatible dict with the existing pool
        rerank_state = {
            "filtered_places": state.candidate_places,
            "extracted_preferences": adjusted_prefs,
            "duration_days": state.slots.duration_days or 3,
            "destination_city": state.slots.destination_city or "",
            "destination_country": state.slots.destination_country,
            "profile": _build_profile_from_slots(state.slots, user_id),
            "user_message": effective_message,
            "conversation_context": _build_conversation_context(state),
            "candidate_places": None,  # will be set by ranking agent
            "draft_itinerary": None,
            "optimized_itinerary": None,
            "is_valid": None,
            "validation": None,
            "error": None,
            "planning_attempts": 0,
            "agent_messages": [],
        }

        # 3. Run ranking agent with adjusted preferences
        rerank_state = await run_ranking_agent(rerank_state)

        if rerank_state.get("error") or not rerank_state.get("candidate_places"):
            logger.warning(
                "[RerankReplan] Ranking failed: %s",
                rerank_state.get("error", "no candidates"),
            )
            return None

        # 4. Run planning agent
        rerank_state = await run_planning_agent(rerank_state)

        if rerank_state.get("error") or not rerank_state.get("draft_itinerary"):
            logger.warning(
                "[RerankReplan] Planning failed: %s",
                rerank_state.get("error", "no draft"),
            )
            return None

        # 5. Run optimizer
        rerank_state = await run_optimization_agent(rerank_state)

        # 6. Run validator
        rerank_state = await run_validation_agent(rerank_state)

        # 7. Check result
        optimized = rerank_state.get("optimized_itinerary")
        is_valid = rerank_state.get("is_valid")

        if not optimized or not is_valid:
            logger.warning("[RerankReplan] Validation failed or no optimized itinerary")
            return None

        logger.info(
            "[RerankReplan] Success: %d days, %d total stops, valid=%s",
            len(optimized.get("days", [])),
            sum(len(d.get("stops", [])) for d in optimized.get("days", [])),
            is_valid,
        )

        return {
            "itinerary": optimized,
            "candidate_places": rerank_state.get("candidate_places"),
            "agent_messages": rerank_state.get("agent_messages", []),
            "validation": rerank_state.get("validation"),
        }

    except Exception as e:
        logger.exception("[RerankReplan] Unexpected error: %s", e)
        return None


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

    # Build a rich trip summary for downstream agents (validator, planner)
    # Instead of passing only the last user message (e.g. "street food"),
    # combine it with all collected trip preferences so the validator
    # can make quality judgments against the full user request.
    rich_user_message = user_message
    if s and (s.interests or s.food_preferences or s.accommodation_preferences or s.travel_style or s.budget_level):
        context_parts = []
        if s.destination_city:
            context_parts.append(f"{s.duration_days or '?'}-day trip to {s.destination_city}")
        if s.budget_level:
            context_parts.append(f"budget: {s.budget_level}")
        if s.travel_style:
            context_parts.append(f"style: {s.travel_style}")
        if s.pace:
            context_parts.append(f"pace: {s.pace}")
        if s.interests:
            context_parts.append(f"interests: {', '.join(s.interests)}")
        if s.food_preferences:
            context_parts.append(f"food: {', '.join(s.food_preferences)}")
        if s.accommodation_preferences:
            context_parts.append(f"accommodation: {', '.join(s.accommodation_preferences)}")
        if s.travel_dates:
            context_parts.append(f"dates: {s.travel_dates}")
        if s.group_size:
            context_parts.append(f"travelers: {s.group_size}")
        if s.traveler_group_type:
            context_parts.append(f"group: {s.traveler_group_type}")
        context_str = " | ".join(context_parts)
        rich_user_message = f"{user_message} | Trip context: {context_str}"

    initial_state = {
        "user_id": user_id,
        "user_message": rich_user_message,
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

        # Progress reporting key (used by graph nodes to push progress)
        "progress_queue_key": state.session_id if state else None,

        # Core trip parameters (from slots or latest extraction)
        "destination_city": (s.destination_city if s else None) or extracted.get("destination_city"),
        "destination_country": (s.destination_country if s else None) or extracted.get("destination_country"),
        "duration_days": (s.duration_days if s else None) or extracted.get("duration_days"),
        "travel_dates": (s.travel_dates if s else None) or extracted.get("travel_dates"),
        "special_requests": (s.special_requests if s else None) or extracted.get("special_requests"),
        "group_size": (s.group_size if s else None) or extracted.get("group_size"),
        "traveler_group_type": (s.traveler_group_type if s else None) or extracted.get("traveler_group_type"),

        "missing_fields": extracted.get("missing_fields", []),
        "agent_messages": [],
    }

    # Add full conversation history context for better planning quality
    conv_context = _build_conversation_context(state) if state else None
    if conv_context:
        initial_state["conversation_context"] = conv_context

    # Execute LangGraph itinerary pipeline
    result_state = await trip_graph.ainvoke(initial_state)

    optimized = result_state.get("optimized_itinerary")
    pipeline_error = result_state.get("error")
    is_valid = result_state.get("is_valid")

    # Build the message: show the itinerary only if it passed validation.
    # If optimized exists but is_valid is False, the pipeline retried and
    # the stale value from the first pass is hanging around — show the error.
    if optimized and is_valid:
        message = _format_itinerary(optimized)
    elif pipeline_error:
        message = f"I ran into an issue generating your itinerary: {pipeline_error}. Please try again."
    elif optimized:
        message = "The itinerary didn't pass quality checks. I'm generating a new version — one moment please."
    else:
        message = "I wasn't able to generate a complete itinerary. Please try again."

    # Store candidate_places from the pipeline for future modifier use
    candidate_places = result_state.get("candidate_places") or result_state.get("filtered_places")

    # Only set the itinerary if it passed validation.
    # Otherwise go back to slot filling so the user can retry.
    if state and optimized and is_valid:
        state.set_itinerary(optimized, candidate_places=candidate_places)
    elif state:
        # Pipeline failed — go back to slot filling so user can retry
        state.transition_to(ConversationPhase.SLOT_FILLING)
        state.plan_started_at = None

    # ── Build profile data for DB persistence ───────────────────────────
    # The profile is built from conversation slots and should be persisted
    # to the trip_profiles table when the trip is created.
    profile_dict = None
    if state and state.slots.is_complete():
        p = _build_profile_from_slots(state.slots, trip_id)
        profile_dict = dict(p)

    return {
        "response_type": "itinerary",
        "message": message,
        "itinerary": optimized,
        "profile": profile_dict,
        "image_features": image_features,
        "agent_messages": result_state.get("agent_messages", []),
        "validation": result_state.get("validation"),
    }