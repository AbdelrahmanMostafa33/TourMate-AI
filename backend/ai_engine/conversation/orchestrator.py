# backend/ai_engine/conversation/orchestrator.py
"""Chat orchestrator with Redis-backed session management.

Uses a message interpreter that replaces the previous 3-call pattern (intent parser +
clarification + general chat) with a single intelligent call that sees
full conversation history and current state.
"""

import asyncio
import contextlib
import copy
import logging
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Optional, Iterator

from ai_engine.constants import PLAN_GENERATION_TIMEOUT_MINUTES

logger = logging.getLogger(__name__)

_MAX_USER_LOCKS = 512
_user_locks: OrderedDict[str, asyncio.Lock] = OrderedDict()

# Core routing LLM that decides what the user wants (plan, clarify, chat, etc.)
from ai_engine.conversation.message_interpreter import interpret_message

# Conversation state machine + slot tracking (memory of user preferences)
from ai_engine.conversation.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
)

# Redis session manager (load/save conversation state per user/session)
from ai_engine.conversation.redis_memory import get_session_manager

# LangGraph-based itinerary generation pipeline
from ai_engine.graph.graph_builder import trip_graph

# Itinerary Modifier Agent — surgically edits existing itineraries
from ai_engine.agents.itinerary_modifier_agent import run_itinerary_modifier

# Edit Classifier — routes modification requests to the correct workflow
from ai_engine.agents.edit_classifier_agent import (
    classify_edit,
    is_preference_edit,
    is_regenerate_edit,
    is_surgical_edit,
)

# Preference Reranker Agent — interprets vibe changes and re-ranks candidates
from ai_engine.agents.preference_reranker_agent import (
    apply_preference_adjustments,
    interpret_preference_adjustment,
)

# Pool management — coverage metrics and DB refresh decisions
from ai_engine.services.pool_manager import (
    merge_pool_enrichment,
    needs_database_query,
)
from ai_engine.tools.slot_normalizer import _ACCOMMODATION_KEYWORDS, map_accommodation_to_type
from ai_engine.tools.places_tool import get_places_for_city

# Direct agent imports for re-ranking (skip retrieval, go straight to rank→plan→optimize→validate)
from ai_engine.services.candidate_scorer import score_candidates
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.services.route_optimizer import optimize_route, optimize_itinerary_days
from ai_engine.services.itinerary_validator import validate_itinerary

# Image analysis pipeline for travel-related images
from ai_engine.vision.image_analyzer import analyze_travel_image

# Fusion logic: merges image signals into user travel profile
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile

# Typed vision features model
from ai_engine.schemas.vision_schema import VisionFeatures

# Profile loaders (real backend vs fallback mock profile)
from ai_engine.tools.profile_tool import load_trip_profile, load_mock_profile

# LangSmith tracing
from ai_engine.observability import traced

# Agent metrics (latency / error tracking per pipeline step)
from ai_engine.evaluation.agent_metrics import agent_metrics

# Token tracker (reset at the start of each pipeline run)
from ai_engine.llm import token_tracker

# Explainability (human-readable explanations of pipeline decisions)
from ai_engine.evaluation.explainability import format_full_explanation


# ── Shared Wrapper ────────────────────────────────────────────────────────────


@contextlib.contextmanager
def _track_pipeline_metrics() -> Iterator[None]:
    """Reset agent_metrics + token_tracker on entry, print the summary on exit.

    Wraps every pipeline entry point so metrics are always properly
    initialized and logged, even if the pipeline raises an exception.
    """
    agent_metrics.reset()
    token_tracker.reset()  # isolate per-run token data
    try:
        yield
    finally:
        agent_metrics.print_summary()


# ── Shared Core ────────────────────────────────────────────────────────────────


@traced(name="process_message", tags=["conversation", "routing"], metadata={"component": "orchestrator"})
async def _process_message(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    image_features: Optional[VisionFeatures],
    token: Optional[str],
) -> dict:
    """Core routing logic shared by handle_chat and handle_chat_stream."""
    try:
        return await _process_message_inner(user_id, state, effective_message, image_features, token)
    except Exception:
        logger.exception("[ConversationAgent] Unexpected error processing message for user %s", user_id)
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
    image_features: Optional[VisionFeatures],
    token: Optional[str],
) -> dict:
    """Inner routing logic — wrapped by _process_message for error safety."""

    # ── CASE 1: System is currently generating itinerary ──────────────────
    if state.phase == ConversationPhase.PLAN_GENERATION:
        if state.plan_started_at:
            started = datetime.fromisoformat(state.plan_started_at)
            elapsed = datetime.now(timezone.utc) - started
            if elapsed > timedelta(minutes=PLAN_GENERATION_TIMEOUT_MINUTES):
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
        state.add_user_message(effective_message)
        if response.get("message"):
            state.add_assistant_message(response["message"])
        return response

    # ── STEP 1: Call message interpreter ──────────────────────────────────
    router_result = await interpret_message(state, effective_message)
    state.slots.merge(router_result.extracted)
    state.add_user_message(effective_message, metadata={"action": router_result.action})

    # ── STEP 2: Fuse image features into slots if available ───────────────
    image_acknowledgment = None
    if image_features and image_features.confidence != "low":
        inferred_interests = image_features.inferred_interests
        if inferred_interests:
            existing_interests = state.slots.interests or []
            existing_lower = {i.lower() for i in existing_interests}
            for interest in inferred_interests:
                if interest.lower() not in existing_lower:
                    existing_interests.append(interest)
                    existing_lower.add(interest.lower())
            state.slots.interests = existing_interests
            logger.info(
                "[ConversationAgent] Fused image interests into slots: %s",
                inferred_interests,
            )
            image_acknowledgment = f"I noticed your interest in {', '.join(inferred_interests[:3])} from your photo!"

    action = router_result.action

    # ── HANDLE COMPLETED STATE FIRST ──────────────────────────────────────
    if state.phase == ConversationPhase.COMPLETED and action in ("plan_trip", "ask_clarification"):
        state.reset_for_new_trip()
        state.slots.merge(router_result.extracted)
        state.slots.fill_defaults()

        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            state.plan_started_at = datetime.now(timezone.utc).isoformat()
            response = await _handle_plan_trip(
                user_id, effective_message, router_result.extracted, image_features, token, state
            )
        else:
            state.transition_to(ConversationPhase.SLOT_FILLING)
            message = router_result.response
            if image_acknowledgment:
                message = f"{image_acknowledgment} {message}"
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": image_features,
            }

    # ── SAFETY OVERRIDE ────────────────────────────────────────────────────
    elif action == "ask_clarification" and state.slots.is_complete():
        action = "plan_trip"

    if action in ("ask_clarification", "plan_trip") and not state.slots.is_complete():
        missing = state.slots.missing_required()
        if missing:
            state.last_question_field = missing[0]
    else:
        state.last_question_field = None

    response = None

    # ── ACTION: PLAN TRIP ──────────────────────────────────────────────────
    if action == "plan_trip":
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)
        state.slots.fill_defaults()

        if state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            state.plan_started_at = datetime.now(timezone.utc).isoformat()
            response = await _handle_plan_trip(
                user_id, effective_message, router_result.extracted, image_features, token, state
            )
        else:
            if state.phase != ConversationPhase.SLOT_FILLING:
                state.transition_to(ConversationPhase.SLOT_FILLING)
            message = router_result.response
            if image_acknowledgment:
                message = f"{image_acknowledgment} {message}"
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": image_features,
            }

    # ── ACTION: ASK CLARIFICATION ──────────────────────────────────────────
    elif action == "ask_clarification":
        if state.phase == ConversationPhase.GREETING:
            state.transition_to(ConversationPhase.SLOT_FILLING)
        message = router_result.response
        if image_acknowledgment:
            message = f"{image_acknowledgment} {message}"
        response = {
            "response_type": "clarification",
            "message": message,
            "itinerary": None,
            "image_features": image_features,
        }

    # ── ACTION: APPROVE EXISTING ITINERARY ──────────────────────────────────
    elif action == "approve_itinerary":
        state.approve_itinerary(itinerary_id=None)
        response = {
            "response_type": "chat",
            "message": router_result.response,
            "itinerary": None,
            "image_features": None,
        }

    # ── ACTION: MODIFY EXISTING ITINERARY ───────────────────────────────────
    elif action == "modify_itinerary":
        if state.phase == ConversationPhase.ITINERARY_REVIEW:
            response = await _handle_modify_itinerary(
                user_id, state, effective_message, router_result, image_features, token,
            )
        else:
            response = {
                "response_type": "chat",
                "message": router_result.response,
                "itinerary": None,
                "image_features": image_features,
            }

    # ── ACTION: ANSWER A QUESTION ──────────────────────────────────────────
    elif action == "answer_question":
        message = router_result.response
        if image_acknowledgment:
            message = f"{image_acknowledgment} {message}"
        response = {
            "response_type": "chat",
            "message": message,
            "itinerary": state.itinerary if state.phase == ConversationPhase.ITINERARY_REVIEW else None,
            "image_features": image_features,
        }

    # ── DEFAULT ACTION ─────────────────────────────────────────────────────
    else:
        message = router_result.response or "I'm here to help!"
        if image_acknowledgment:
            message = f"{image_acknowledgment} {message}"
        response = {
            "response_type": "chat",
            "message": message,
            "itinerary": None,
            "image_features": image_features,
        }

    if response and response.get("message"):
        state.add_assistant_message(response["message"])

    return response


def _prepare_message(user_message: Optional[str]) -> str:
    effective_message = (user_message or "").strip()
    if not effective_message:
        effective_message = "I uploaded an image for my trip."
    return effective_message


async def _parse_image(image_bytes: Optional[bytes]) -> Optional[VisionFeatures]:
    if image_bytes:
        return await analyze_travel_image(image_bytes)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────


def _get_user_lock(user_id: str) -> asyncio.Lock:
    if user_id in _user_locks:
        _user_locks.move_to_end(user_id)
    else:
        if len(_user_locks) >= _MAX_USER_LOCKS:
            _user_locks.popitem(last=False)
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


@traced(name="handle_chat", tags=["conversation", "entry_point"], metadata={"component": "orchestrator"})
async def handle_chat(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    lock = _get_user_lock(user_id)
    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id)
        effective_message = _prepare_message(user_message)
        image_features = await _parse_image(image_bytes)
        response = await _process_message(user_id, state, effective_message, image_features, token)
        await manager.save(state)
        await manager.extend_ttl(state.session_id)

        if response:
            response["session_id"] = state.session_id
            response["phase"] = state.phase.value

        return response


async def handle_chat_stream(user_id, user_message, image_bytes=None, token=None, session_id=None, initial_pool_state=None):
    lock = _get_user_lock(user_id)

    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id)

        if initial_pool_state and not state.candidate_places:
            state.hydrate_pool(initial_pool_state)
            await manager.save(state)

        yield {"type": "session", "data": {"session_id": state.session_id, "phase": state.phase.value}}

        effective_message = _prepare_message(user_message)
        image_features = await _parse_image(image_bytes)

        from ai_engine.graph.progress import get_progress_queue, remove_progress_queue

        progress_queue = get_progress_queue(state.session_id)
        pipeline_task = asyncio.create_task(
            _process_message(user_id, state, effective_message, image_features, token)
        )

        is_planning = state.phase == ConversationPhase.PLAN_GENERATION

        if is_planning:
            try:
                while not pipeline_task.done():
                    try:
                        progress = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                        yield {"type": "progress", "data": progress}
                    except asyncio.TimeoutError:
                        continue

                while True:
                    try:
                        progress = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                        yield {"type": "progress", "data": progress}
                    except asyncio.TimeoutError:
                        break
            finally:
                remove_progress_queue(state.session_id)

        response = await pipeline_task
        await manager.save(state)
        await manager.extend_ttl(state.session_id)
        phase_value = state.phase.value

    yield {"type": "phase", "data": {"phase": phase_value}}

    message = response.get("message", "I'm here to help!") if response else "I'm here to help!"
    async for chunk in _stream_text(message):
        yield chunk

    if response and response.get("response_type") == "itinerary" and response.get("itinerary"):
        result_data = {
            "message": response.get("message", ""),
            "itinerary": response["itinerary"],
            "phase": phase_value,
            "session_id": state.session_id,
        }
        if response.get("profile"):
            result_data["profile"] = response["profile"]
        if response.get("explanation"):
            result_data["explanation"] = response["explanation"]
        if response.get("agent_messages"):
            result_data["agent_messages"] = response["agent_messages"]
        if response.get("agent_metrics"):
            result_data["agent_metrics"] = response["agent_metrics"]
        if response.get("validation"):
            result_data["validation"] = response["validation"]
        if response.get("pool_state"):
            result_data["pool_state"] = response["pool_state"]
        yield {"type": "result", "data": result_data}

    yield {"type": "done", "data": None}


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _stream_text(text: str):
    lines = text.split("\n")
    for i, line in enumerate(lines):
        # Preserve leading whitespace for indentation
        leading = len(line) - len(line.lstrip())
        indent = line[:leading]
        words = line.strip().split()
        for j, word in enumerate(words):
            content = (indent if j == 0 else "") + word + " "
            yield {"type": "text", "content": content}
        if i < len(lines) - 1:
            yield {"type": "text", "content": "\n"}


def _build_profile_from_slots(slots: TripSlots, trip_id: str) -> dict:
    from ai_engine.graph.state import TripProfile
    return TripProfile(
        profile_id=None,
        trip_id=trip_id,
        budget_level=slots.budget_level,
        travel_style=slots.travel_style,
        pace=slots.pace,
        interests=slots.interests or [],
        food_preferences=slots.food_preferences or [],
        accommodation_preferences=slots.accommodation_preferences or [],
        generated_at=None,
        updated_at=None,
    )


def _available_pool(state: ConversationState) -> list[dict]:
    """Return the richest place pool available for edits."""
    if state.filtered_places:
        return state.filtered_places
    return state.candidate_places or []


def _apply_adjustments_to_slots(state: ConversationState, adjustments: dict) -> dict:
    """Apply preference adjustments to trip slots and return updated preferences."""
    updated = apply_preference_adjustments(state.slots, adjustments)

    if adjustments.get("budget_level"):
        state.slots.budget_level = adjustments["budget_level"]
    if adjustments.get("travel_style"):
        state.slots.travel_style = adjustments["travel_style"]
    if adjustments.get("pace"):
        state.slots.pace = adjustments["pace"]
    if updated.get("interests") is not None:
        state.slots.interests = updated["interests"]
    if updated.get("food_preferences") is not None:
        state.slots.food_preferences = updated["food_preferences"]
    if updated.get("accommodation_preferences") is not None:
        state.slots.accommodation_preferences = updated["accommodation_preferences"]

    return updated


def _detect_affected_days(original: dict, modified: dict) -> list[int]:
    """Return day numbers whose stop lists changed."""
    affected: list[int] = []
    orig_days = {d.get("day_number"): d for d in original.get("days", []) if d.get("day_number") is not None}
    mod_days = {d.get("day_number"): d for d in modified.get("days", []) if d.get("day_number") is not None}

    for day_num in sorted(set(orig_days) | set(mod_days)):
        orig_ids = [s.get("id") for s in orig_days.get(day_num, {}).get("stops", [])]
        mod_ids = [s.get("id") for s in mod_days.get(day_num, {}).get("stops", [])]
        if orig_ids != mod_ids:
            affected.append(day_num)

    return affected


async def _post_edit_optimize(
    modified: dict,
    original: dict,
    classification: dict | None = None,
) -> dict:
    """Run day-level OSRM optimization after structural delta edits."""
    edit_type = (classification or {}).get("edit_type", "").upper()
    if edit_type in ("RE_THEME", "CHANGE_HOTEL"):
        return modified

    affected = _detect_affected_days(original, modified)
    target_day = (classification or {}).get("target_day")
    if target_day and target_day not in affected:
        affected.append(target_day)

    if not affected and edit_type in (
        "ADD_PLACE", "REPLACE_PLACE", "REORDER", "MOVE_DAY", "REMOVE",
        "SWAP", "ADD", "EXCHANGE", "UNKNOWN",
    ):
        affected = [d.get("day_number") for d in modified.get("days", []) if d.get("day_number") is not None]

    if not affected:
        return modified

    try:
        return await optimize_itinerary_days(modified, day_numbers=affected)
    except Exception as exc:
        logger.warning("[ConversationAgent] Post-edit route optimization failed: %s", exc)
        return modified


def _itinerary_response(
    state: ConversationState,
    modified: dict,
    image_features: Optional[VisionFeatures],
    agent_messages: list[str] | None = None,
    validation: dict | None = None,
) -> dict:
    """Build a standard itinerary response and update conversation state."""
    state.set_itinerary(
        modified,
        candidate_places=state.candidate_places,
        filtered_places=state.filtered_places,
    )
    response = {
        "response_type": "itinerary",
        "message": _format_itinerary(modified),
        "itinerary": modified,
        "image_features": image_features,
        "pool_state": state.get_pool_state(),
    }
    if agent_messages:
        response["agent_messages"] = agent_messages
    if validation:
        response["validation"] = validation
    return response


def _modifier_blocked_response(
    state: ConversationState,
    modifier_note: str,
    image_features: Optional[VisionFeatures],
    agent_messages: list[str] | None = None,
) -> dict:
    """Return the unchanged itinerary with an explicit failure note (no full regen)."""
    msgs = list(agent_messages or [])
    if modifier_note:
        msgs.append(f"[ModifierAgent] {modifier_note}")
    message = _format_itinerary(state.itinerary)
    if modifier_note:
        message += f"\n\n⚠️ I couldn't apply that change: {modifier_note}"
    return {
        "response_type": "itinerary",
        "message": message,
        "itinerary": state.itinerary,
        "image_features": image_features,
        "pool_state": state.get_pool_state(),
        "agent_messages": msgs,
    }


async def _apply_modifier_edit(
    state: ConversationState,
    effective_message: str,
    preferences: dict,
    classification: dict,
    original_itinerary: dict,
    image_features: Optional[VisionFeatures],
    agent_messages: list[str],
) -> dict | None:
    """Run modifier agent; return response dict if handled, else None."""
    modified = await run_itinerary_modifier(
        current_itinerary=original_itinerary,
        modification_request=effective_message,
        available_places=_available_pool(state),
        preferences=preferences,
    )
    modifier_note = modified.pop("_modifier_note", "")
    modifier_applied = _has_real_modifications(modified, original_itinerary)

    if modifier_applied:
        modified = await _post_edit_optimize(modified, original_itinerary, classification)
        trailing_note = modified.pop("_modifier_note", "")
        if trailing_note:
            modifier_note = f"{modifier_note}\n{trailing_note}".strip()
        if modifier_note:
            agent_messages.append(f"[ModifierAgent] {modifier_note}")
        return _itinerary_response(state, modified, image_features, agent_messages)

    if modifier_note and is_surgical_edit(classification):
        return _modifier_blocked_response(state, modifier_note, image_features, agent_messages)

    return None


async def _maybe_enrich_pools(
    state: ConversationState,
    modification_request: str,
    classification: dict | None = None,
) -> bool:
    """Enrich stored pools from DB when category coverage is insufficient."""
    if not state.slots.destination_city:
        return False

    need_db, reason = needs_database_query(
        modification_request,
        state.filtered_places,
        state.candidate_places,
        state.itinerary,
        classification,
    )
    if not need_db or reason not in (
        "missing_category",
        "missing_semantic",
        "insufficient_category",
        "low_coverage",
        "preference_shift",
    ):
        return False

    enriched = await _enrich_candidate_pool_by_category(
        modification_request=modification_request,
        destination_city=state.slots.destination_city,
        existing_pool=_available_pool(state),
    )
    if not enriched:
        return False

    existing_ids = {p.get("id") for p in _available_pool(state) if p.get("id")}
    new_places = [p for p in enriched if p.get("id") not in existing_ids]
    if not new_places:
        return False

    base_filtered = state.filtered_places or state.candidate_places or []
    state.filtered_places = merge_pool_enrichment(base_filtered, new_places)
    state.candidate_places = merge_pool_enrichment(state.candidate_places or [], new_places)
    logger.info(
        "[ConversationAgent] Enriched pools (%s) — filtered=%d candidate=%d",
        reason,
        len(state.filtered_places or []),
        len(state.candidate_places or []),
    )
    return True


def _has_real_modifications(mod: dict, orig: dict) -> bool:
    if mod is orig:
        return False

    orig_stop_ids = [s["id"] for d in orig.get("days", []) for s in d.get("stops", []) if s.get("id")]
    new_stop_ids = [s["id"] for d in mod.get("days", []) for s in d.get("stops", []) if s.get("id")]
    if orig_stop_ids != new_stop_ids:
        return True

    orig_themes = {d.get("day_number"): d.get("theme") for d in orig.get("days", []) if d.get("day_number") is not None}
    new_themes = {d.get("day_number"): d.get("theme") for d in mod.get("days", []) if d.get("day_number") is not None}
    if orig_themes != new_themes:
        return True

    orig_hotel_types = {h.get("accommodation_type") for h in orig.get("accommodation_suggestions", [])}
    new_hotel_types = {h.get("accommodation_type") for h in mod.get("accommodation_suggestions", [])}
    if orig_hotel_types != new_hotel_types:
        return True

    orig_hotel_ids = {h["id"] for h in orig.get("accommodation_suggestions", []) if h.get("id")}
    new_hotel_ids = {h["id"] for h in mod.get("accommodation_suggestions", []) if h.get("id")}
    if orig_hotel_ids != new_hotel_ids:
        return True

    def _stop_signature(itinerary: dict) -> list[tuple]:
        sig = []
        for day in itinerary.get("days", []):
            day_num = day.get("day_number")
            for stop in day.get("stops", []):
                sig.append((
                    day_num,
                    stop.get("id"),
                    stop.get("suggested_time_of_day"),
                ))
        return sig

    if _stop_signature(orig) != _stop_signature(mod):
        return True

    return False


async def _swap_accommodation_surgically(itinerary: dict, destination_city: str, acc_add: list[str]) -> dict | None:
    if not acc_add:
        logger.warning("[AccommodationSwap] Empty acc_add — nothing to swap")
        return None

    canonical_type = map_accommodation_to_type(acc_add)
    if not canonical_type:
        logger.warning("[AccommodationSwap] Could not map %r to a canonical type", acc_add)
        return None

    all_places = await get_places_for_city(destination_city)
    matching_hotels = [
        p for p in all_places
        if p.get("category") == "hotel"
        and (
            canonical_type in (p.get("accommodation_type") or "").lower()
            or (p.get("accommodation_type") or "").lower() in canonical_type
        )
    ]

    if not matching_hotels:
        logger.warning("[AccommodationSwap] No hotels matching type '%s' found in %s", canonical_type, destination_city)
        return None

    matching_hotels.sort(key=lambda h: h.get("rating", 0) or 0, reverse=True)
    top_hotels = matching_hotels[:5]
    acc_display = canonical_type.capitalize() or "Accommodation"
    for h in top_hotels:
        if not h.get("why_recommended"):
            h["why_recommended"] = (
                f"This {canonical_type} is highly-rated and aligns with your "
                f"preference for {acc_display.lower()} accommodation."
            )

    modified = copy.deepcopy(itinerary)
    modified["accommodation_suggestions"] = top_hotels
    logger.info("[AccommodationSwap] Swapped %d hotels with type '%s' — itinerary stops preserved", len(top_hotels), canonical_type)
    return modified


async def _enrich_candidate_pool_by_category(modification_request: str, destination_city: str, existing_pool: list[dict]) -> list[dict] | None:
    from ai_engine.services.operations import (
        _detect_category_hints,
        filter_places_by_semantics,
    )
    from ai_engine.tools.places_tool import get_places_for_city

    hints = _detect_category_hints(modification_request)
    cats: list[str] = hints.get("category", [])
    subcats: list[str] = hints.get("sub_category", [])
    semantics: list[str] = hints.get("semantic", [])

    if not cats and not subcats and not semantics:
        logger.debug("[EnrichPool] No category hints in '%s'", modification_request[:60])
        return None

    all_places = await get_places_for_city(destination_city)
    if not all_places:
        return None

    matching = []
    for p in all_places:
        if subcats:
            p_sub = (p.get("sub_category") or "").lower()
            if p_sub not in subcats:
                continue
        elif cats:
            p_cat = (p.get("category") or "").lower()
            if p_cat not in cats:
                continue
        matching.append(p)

    if semantics:
        matching = filter_places_by_semantics(matching, semantics)

    if not matching:
        label = ", ".join(semantics or subcats or cats)
        logger.info("[EnrichPool] No places matching '%s' found in %s", label, destination_city)
        return None

    matching.sort(key=lambda p: p.get("rating", 0) or 0, reverse=True)
    matching = matching[:15]
    existing_ids = {p.get("id") for p in existing_pool if p.get("id")}
    new_places = [p for p in matching if p.get("id") not in existing_ids]

    if not new_places:
        logger.info("[EnrichPool] All matching places already in pool")
        return None

    enriched = list(existing_pool) + new_places
    label = ", ".join(subcats or cats)
    logger.info("[EnrichPool] Added %d new '%s' places to pool (total: %d)", len(new_places), label, len(enriched))
    return enriched


def _build_conversation_context(state) -> str:
    lines = []
    for msg in (state.history or []):
        role = msg.role.capitalize()
        content = (msg.content or "")[:150]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _is_accommodation_type_change(modification_request: str) -> str | None:
    """Detect if the user is asking to change accommodation type (e.g. 'resorts instead of hotels').

    Returns the canonical accommodation type string (e.g. 'resort', 'hostel', 'luxury', 'hotel')
    if an accommodation type change is detected, or None otherwise.
    """
    msg_lower = modification_request.lower()

    # Patterns that indicate an accommodation type change:
    # "provide resorts instead of hotels"
    # "switch to resorts"
    # "change to luxury hotels"
    # "use hostels instead"
    # "replace with resorts"
    # "resorts instead"
    # "i want resorts"
    # "give me resorts"

    # Check for "instead of" / "instead" patterns
    has_instead = "instead" in msg_lower
    has_switch = any(kw in msg_lower for kw in ("switch to", "change to", "replace with", "use "))
    has_want = any(kw in msg_lower for kw in ("i want ", "give me ", "provide ", "show me "))

    if not (has_instead or has_switch or has_want):
        return None

    # Extract the accommodation type keyword mentioned
    # Use word-boundary matching and break on FIRST match since
    # _ACCOMMODATION_KEYWORDS lists specific phrases first.
    # This ensures "boutique hotel" → luxury (not overwritten by "hotel").
    matched_type = None
    for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
        if keyword in msg_lower:
            matched_type = acc_type
            break

    if matched_type:
        logger.info(
            "[AccommodationTypeChange] Detected accommodation type change: %s in '%s'",
            matched_type, modification_request[:60],
        )
        return matched_type

    return None


def _format_itinerary(itinerary: dict) -> str:
    if not itinerary:
        return "I wasn't able to generate a complete itinerary. Please try again."

    lines = []
    destination = itinerary.get("destination", "your destination")
    days = itinerary.get("days", [])
    hotels = itinerary.get("accommodation_suggestions", [])

    lines.append(f"✨ Here's your personalized {len(days)}-day itinerary for {destination}!")
    lines.append("")

    for day in days:
        day_num = day.get("day_number", "?")
        theme = day.get("theme", "")
        stops = day.get("stops", [])

        header = f"🗓 Day {day_num}"
        if theme:
            header += f" — {theme}"
        lines.append(header)

        for idx, stop in enumerate(stops, 1):
            name = stop.get("name", "Unknown")
            time_slot = stop.get("suggested_time_of_day", "")
            duration = stop.get("estimated_duration_minutes", 0)
            why = stop.get("why_recommended", "")
            rating = stop.get("rating")
            cat = stop.get("category", "")

            time_emoji = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}.get(time_slot, "📍")
            time_label = time_slot.capitalize() if time_slot else ""

            parts = [f"  {time_emoji} {name}"]
            if time_label:
                parts.append(f"({time_label})")
            if duration:
                parts.append(f"{duration} min")
            lines.append(" • ".join(parts))

            detail_bits = []
            if cat:
                detail_bits.append(cat.capitalize())
            if rating:
                detail_bits.append(f"⭐ {rating}")
            if detail_bits:
                sep = " · "
                lines.append(f"      {sep.join(detail_bits)}")
            if why:
                lines.append(f"      💡 {why}")

        lines.append("")

    if hotels:
        lines.append("🏨 Where to Stay")
        for hotel in hotels:
            name = hotel.get("name", "Unknown")
            acc_type = hotel.get("accommodation_type", "")
            rating = hotel.get("rating", 0)
            why = hotel.get("why_recommended", "")
            line = f"  • {name}"
            if acc_type:
                line += f" ({acc_type})"
            if rating:
                line += f" ⭐ {rating}"
            lines.append(line)
            if why:
                lines.append(f"      💡 {why}")

    lines.append("")
    lines.append("💡 You can ask me to modify any part of this itinerary, or say 'approve' to save it!")
    return "\n".join(lines)


@traced(name="modify_itinerary", tags=["conversation", "modify"], metadata={"component": "orchestrator"})
async def _handle_modify_itinerary(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[VisionFeatures],
    token: Optional[str],
) -> dict:
    # ── Early check: accommodation type change (e.g. "resorts instead of hotels") ──
    # This intercepts BEFORE the classifier so that accommodation type changes are
    # handled by _swap_accommodation_surgically (which replaces ALL hotels) rather
    # than the modifier agent (which only changes one hotel at a time).
    acc_type_change = _is_accommodation_type_change(effective_message)
    if acc_type_change and state.itinerary and state.slots.destination_city:
        logger.info(
            "[ConversationAgent] Intercepted accommodation type change: %s → '%s'",
            effective_message[:60], acc_type_change,
        )
        # Update slots with new accommodation preference
        state.slots.accommodation_preferences = [acc_type_change]
        surgically_swapped = await _swap_accommodation_surgically(
            itinerary=state.itinerary,
            destination_city=state.slots.destination_city,
            acc_add=[acc_type_change],
        )
        if surgically_swapped:
            return _itinerary_response(
                state,
                surgically_swapped,
                image_features,
                agent_messages=[f"[AccommodationSwap] Updated all accommodations to {acc_type_change} — stops preserved"],
            )

    classification = await classify_edit(effective_message, state.itinerary)
    edit_type = classification.get("edit_type", "UNKNOWN")
    agent_messages = [f"[EditClassifier] {edit_type}: {classification.get('reasoning', '')}"]

    preferences = {
        "budget_level": state.slots.budget_level,
        "travel_style": state.slots.travel_style,
        "pace": state.slots.pace,
        "interests": state.slots.interests or [],
        "food_preferences": state.slots.food_preferences or [],
        "accommodation_preferences": state.slots.accommodation_preferences or [],
    }

    need_db, db_reason = needs_database_query(
        effective_message,
        state.filtered_places,
        state.candidate_places,
        state.itinerary,
        classification,
    )
    if need_db and db_reason == "regenerate_requested":
        logger.info("[ConversationAgent] Classifier requested full regeneration")
        return await _fallback_full_regeneration(
            user_id, state, effective_message, router_result, image_features, token,
            modifier_applied=False,
            accommodations_updated=False,
            show_fallback_note=False,
        )

    # Enrich pool BEFORE preference-shift / modifier paths so category-
    # matching places are available for reranking and delta edits.
    await _maybe_enrich_pools(state, effective_message, classification)

    if need_db and db_reason == "preference_shift":
        adjustments = await interpret_preference_adjustment(effective_message, current_preferences=preferences)
        if adjustments:
            reranked = await _rerank_and_replan(
                user_id=user_id,
                state=state,
                adjustments=adjustments,
                effective_message=effective_message,
            )
            if reranked:
                return _itinerary_response(
                    state,
                    reranked["itinerary"],
                    image_features,
                    agent_messages + reranked.get("agent_messages", []),
                    reranked.get("validation"),
                )

        # Rerank failed — try the modifier agent before full regeneration.
        blocked = await _apply_modifier_edit(
            state, effective_message, preferences, classification,
            state.itinerary, image_features, agent_messages,
        )
        if blocked is not None:
            return blocked

        return await _fallback_full_regeneration(
            user_id, state, effective_message, router_result, image_features, token,
            modifier_applied=False,
            accommodations_updated=False,
            agent_messages=agent_messages,
            show_fallback_note=False,
        )

    if is_preference_edit(classification) and not is_surgical_edit(classification):
        adjustments = await interpret_preference_adjustment(effective_message, current_preferences=preferences)
        if adjustments:
            acc_add = adjustments.get("accommodation_preferences_add") or []
            acc_remove = adjustments.get("accommodation_preferences_remove") or []
            if acc_add or acc_remove:
                _apply_adjustments_to_slots(state, adjustments)
                surgically_swapped = await _swap_accommodation_surgically(
                    itinerary=state.itinerary,
                    destination_city=state.slots.destination_city or "",
                    acc_add=acc_add,
                )
                if surgically_swapped:
                    return _itinerary_response(
                        state,
                        surgically_swapped,
                        image_features,
                        agent_messages + ["[AccommodationSwap] Updated accommodation — stops preserved"],
                    )
            else:
                reranked = await _rerank_and_replan(
                    user_id=user_id,
                    state=state,
                    adjustments=adjustments,
                    effective_message=effective_message,
                )
                if reranked:
                    return _itinerary_response(
                        state,
                        reranked["itinerary"],
                        image_features,
                        agent_messages + reranked.get("agent_messages", []),
                        reranked.get("validation"),
                    )

    if is_surgical_edit(classification) or not is_regenerate_edit(classification):
        blocked = await _apply_modifier_edit(
            state, effective_message, preferences, classification,
            state.itinerary, image_features, agent_messages,
        )
        if blocked is not None:
            return blocked

    if _available_pool(state) and len(_available_pool(state)) > 5:
        adjustments = await interpret_preference_adjustment(effective_message, current_preferences=preferences)
        if adjustments:
            acc_add = adjustments.get("accommodation_preferences_add") or []
            if acc_add or adjustments.get("accommodation_preferences_remove"):
                _apply_adjustments_to_slots(state, adjustments)
                surgically_swapped = await _swap_accommodation_surgically(
                    itinerary=state.itinerary,
                    destination_city=state.slots.destination_city or "",
                    acc_add=acc_add,
                )
                if surgically_swapped:
                    return _itinerary_response(
                        state,
                        surgically_swapped,
                        image_features,
                        agent_messages + ["[AccommodationSwap] Updated accommodation — stops preserved"],
                    )
            else:
                reranked = await _rerank_and_replan(
                    user_id=user_id,
                    state=state,
                    adjustments=adjustments,
                    effective_message=effective_message,
                )
                if reranked:
                    return _itinerary_response(
                        state,
                        reranked["itinerary"],
                        image_features,
                        agent_messages + reranked.get("agent_messages", []),
                        reranked.get("validation"),
                    )

    logger.info("[ConversationAgent] Falling back to full pipeline regeneration")
    return await _fallback_full_regeneration(
        user_id, state, effective_message, router_result, image_features, token,
        modifier_applied=False,
        accommodations_updated=False,
        agent_messages=agent_messages,
    )


async def _fallback_full_regeneration(
    user_id: str,
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[VisionFeatures],
    token: Optional[str],
    modifier_applied: bool,
    accommodations_updated: bool,
    agent_messages: list[str] | None = None,
    show_fallback_note: bool = True,
) -> dict:
    state.transition_to(ConversationPhase.PLAN_GENERATION)
    state.plan_started_at = datetime.now(timezone.utc).isoformat()

    extracted = dict(router_result.extracted)
    # Merge existing special requests (from slots) with the modification prompt
    existing = state.slots.special_requests or []
    if isinstance(existing, str):  # backward compat: old Redis data may be a string
        existing = [existing]
    extracted["special_requests"] = list(existing) + [f"Modification: {effective_message}"]

    result = await _handle_plan_trip(user_id, effective_message, extracted, image_features, token, state)

    if agent_messages:
        result["agent_messages"] = agent_messages + result.get("agent_messages", [])

    if show_fallback_note and not modifier_applied and not accommodations_updated:
        message = result.get("message", "")
        fallback_note = (
            f"\n\n⚠️ Note: I couldn't find a place matching "
            f"\"{effective_message}\" in the available options. "
            "The itinerary above reflects the best available alternatives."
        )
        result["message"] = message + fallback_note

    return result


@traced(name="rerank_and_replan", tags=["conversation", "rerank"], metadata={"component": "orchestrator"})
async def _rerank_and_replan(
    user_id: str,
    state: ConversationState,
    adjustments: dict,
    effective_message: str,
    image_features: Optional[VisionFeatures] = None,
    token: Optional[str] = None,
) -> dict | None:
    try:
        with _track_pipeline_metrics():
            updated_prefs = _apply_adjustments_to_slots(state, adjustments)
            profile = dict(_build_profile_from_slots(state.slots, user_id))
            for key in (
                "budget_level",
                "travel_style",
                "pace",
                "interests",
                "food_preferences",
                "accommodation_preferences",
            ):
                if updated_prefs.get(key) is not None:
                    profile[key] = updated_prefs[key]

            rerank_pool = state.filtered_places or state.candidate_places or []
            rerank_state = {
                "filtered_places": rerank_pool,
                "duration_days": state.slots.duration_days or 3,
                "destination_city": state.slots.destination_city or "",
                "destination_country": state.slots.destination_country,
                "profile": profile,
                "user_message": effective_message,
                "conversation_context": _build_conversation_context(state),
                "candidate_places": None,
                "draft_itinerary": None,
                "optimized_itinerary": None,
                "is_valid": None,
                "validation": None,
                "error": None,
                "planning_attempts": 0,
                "agent_messages": [],
            }

            rerank_state = await score_candidates(rerank_state)
            if rerank_state.get("error") or not rerank_state.get("candidate_places"):
                logger.warning("[RerankReplan] Ranking failed: %s", rerank_state.get("error", "no candidates"))
                return None

            rerank_state = await run_planning_agent(rerank_state)
            if rerank_state.get("error") or not rerank_state.get("draft_itinerary"):
                logger.warning("[RerankReplan] Planning failed: %s", rerank_state.get("error", "no draft"))
                return None

            rerank_state = await optimize_route(rerank_state)
            rerank_state = await validate_itinerary(rerank_state)

            optimized = rerank_state.get("optimized_itinerary")
            is_valid = rerank_state.get("is_valid")
            if not optimized or not is_valid:
                logger.warning("[RerankReplan] Validation failed or no optimized itinerary")
                return None

            logger.info("[RerankReplan] Success: %d days, %d total stops, valid=%s",
                        len(optimized.get("days", [])),
                        sum(len(d.get("stops", [])) for d in optimized.get("days", [])),
                        is_valid)
            return {
                "itinerary": optimized,
                "candidate_places": rerank_state.get("candidate_places"),
                "filtered_places": rerank_pool,
                "agent_messages": rerank_state.get("agent_messages", []),
                "validation": rerank_state.get("validation"),
                "agent_metrics": agent_metrics.get_summary(),
            }

    except Exception as e:
        logger.exception("[RerankReplan] Unexpected error: %s", e)
        return None


@traced(name="plan_trip_pipeline", tags=["conversation", "pipeline"], metadata={"component": "orchestrator"})
async def _handle_plan_trip(user_id, user_message, extracted, image_features, token=None, state=None):
    with _track_pipeline_metrics():
        trip_id = getattr(state, 'trip_id', None) or user_id

        if state and state.slots.is_complete():
            profile = _build_profile_from_slots(state.slots, trip_id)
            logger.info("[ChatHandler] Built profile from slots: budget=%s, style=%s, pace=%s",
                        profile.get('budget_level'), profile.get('travel_style'), profile.get('pace'))
        elif token:
            try:
                profile = await load_trip_profile(trip_id=trip_id, token=token)
            except Exception as e:
                logger.warning("[ChatHandler] Failed to load real profile (%s), falling back to mock", e)
                profile = load_mock_profile(trip_id=trip_id)
        else:
            profile = load_mock_profile(trip_id=trip_id)

        if image_features and image_features.confidence != "low":
            profile = fuse_image_with_profile(profile, image_features)

        s = state.slots if state else None

        rich_user_message = user_message
        if s and (s.interests or s.food_preferences or s.accommodation_preferences or s.travel_style or s.budget_level):
            context_parts = []
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
            "progress_queue_key": state.session_id if state else None,
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

        conv_context = _build_conversation_context(state) if state else None
        if conv_context:
            initial_state["conversation_context"] = conv_context

        result_state = await trip_graph.ainvoke(initial_state)
        optimized = result_state.get("optimized_itinerary")
        pipeline_error = result_state.get("error")
        is_valid = result_state.get("is_valid")

        if optimized and is_valid:
            message = _format_itinerary(optimized)
        elif pipeline_error:
            message = f"I ran into an issue generating your itinerary: {pipeline_error}. Please try again."
        elif optimized:
            message = "The itinerary didn't pass quality checks. I'm generating a new version — one moment please."
        else:
            message = "I wasn't able to generate a complete itinerary. Please try again."

        candidate_places = result_state.get("candidate_places") or result_state.get("filtered_places")
        filtered_places = result_state.get("filtered_places")

        if state and optimized and is_valid:
            state.set_itinerary(
                optimized,
                candidate_places=candidate_places,
                filtered_places=filtered_places,
            )
        elif state:
            state.transition_to(ConversationPhase.SLOT_FILLING)
            state.plan_started_at = None

        profile_dict = None
        if state and state.slots.is_complete():
            p = _build_profile_from_slots(state.slots, trip_id)
            profile_dict = dict(p)

        # Build human-readable explanation from pipeline outputs
        validation_data = result_state.get("validation")
        explanation = format_full_explanation(
            itinerary=optimized,
            validation=validation_data,
            metrics=validation_data.get("metrics") if validation_data else None,
            profile=result_state.get("profile"),
            agent_messages=result_state.get("agent_messages", []),
        )

        # Log and attach agent performance metrics
        agent_metrics_summary = agent_metrics.get_summary()

        return {
            "response_type": "itinerary",
            "message": message,
            "itinerary": optimized,
            "profile": profile_dict,
            "image_features": image_features,
            "agent_messages": result_state.get("agent_messages", []),
            "validation": validation_data,
            "explanation": explanation,
            "agent_metrics": agent_metrics_summary,
            "pool_state": state.get_pool_state() if state else None,
        }
