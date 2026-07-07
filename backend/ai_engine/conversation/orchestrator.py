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
import re
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Iterator, Dict

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

# ── Numbered emoji for hotel selection ────────────────────────────────────
_HOTEL_NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

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

# Direct agent imports for re-ranking (skip retrieval, go straight to rank→plan→optimize→hotel→validate)
from ai_engine.services.candidate_scorer import score_candidates
from ai_engine.agents.planning_agent import run_planning_agent
from ai_engine.agents.hotel_selection_agent import (
    search_hotels_for_trip as hs_search_hotels,
    format_hotel_options as hs_format_options,
    extract_hotel_selection as hs_extract_selection,
)
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
from ai_engine.observability import traced, update_trace_metadata

# Agent metrics (latency / error tracking per pipeline step)
from ai_engine.evaluation.agent_metrics import agent_metrics

# Token tracker (reset at the start of each pipeline run)
from ai_engine.llm import token_tracker

# Explainability (human-readable explanations of pipeline decisions)
from ai_engine.evaluation.explainability import format_full_explanation

# Flight Selection Agent — conversational flight search
from ai_engine.agents.flight_selection_agent import (
    search_flights_for_trip,
    format_flight_options,
    extract_flight_selection,
)

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


def _log_itinerary_presence(
    response: dict | None,
    *,
    phase: str,
    source: str,
    user_id: str = "",
) -> None:
    """Log whether the itinerary is included or excluded in a response.

    Logs at INFO level with structured fields so log-parsing tools can
    filter and aggregate itinerary-inclusion patterns across phases.
    """
    if not response:
        logger.info(
            "[ItineraryLog] source=%s response=None — no response to inspect",
            source,
        )
        return

    itinerary_present = response.get("itinerary") is not None
    itinerary_is_dict = isinstance(response.get("itinerary"), dict)
    response_type = response.get("response_type", "?")
    action = response.get("action", "")
    has_ui = bool(response.get("ui"))

    if itinerary_is_dict:
        reason = "itinerary_present"
        days = len(response["itinerary"].get("days", []))
        stops = sum(len(d.get("stops", [])) for d in response["itinerary"].get("days", []))
        detail = f"days={days} stops={stops}"
    else:
        reason = "itinerary_absent"
        detail = "(key is None or missing)"

    logger.info(
        "[ItineraryLog] source=%s phase=%s response_type=%s action=%s "
        "itinerary_present=%s itinerary_is_dict=%s has_ui=%s reason=%s %s",
        source,
        phase,
        response_type,
        action or "-",
        itinerary_present,
        itinerary_is_dict,
        has_ui,
        reason,
        detail,
    )

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
    # Attach conversation history to LangSmith trace for visibility
    try:
        if state and hasattr(state, 'history') and state.history:
            summary = [
                {"role": m.role, "content_snippet": (m.content or "")[:120]}
                for m in state.history[-10:]
            ]
            update_trace_metadata({
                "conversation_history": summary,
                "phase": state.phase.value if state else "",
                "turn_count": state.turn_count,
            })
    except Exception:
        pass
    try:
        response = await _process_message_inner(user_id, state, effective_message, image_features, token)
        _log_itinerary_presence(
            response,
            phase=state.phase.value if state else "?",
            source="process_message",
            user_id=user_id,
        )
        return response
    except Exception:
        logger.exception("[ConversationAgent] Unexpected error processing message for user %s", user_id)
        error_response = {
            "response_type": "chat",
            "message": "I ran into an unexpected issue. Please try again.",
            "itinerary": None,
            "image_features": None,
        }
        _log_itinerary_presence(
            error_response,
            phase=state.phase.value if state else "?",
            source="process_message_error",
            user_id=user_id,
        )
        return error_response

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


    # ── CASE 2: IMAGE_REVIEW phase — user responding to image analysis ──
    if state.phase == ConversationPhase.IMAGE_REVIEW:
        # User uploaded another image — replace pending and show new review
        if image_features and image_features.confidence != "low":
            state.pending_image_features = image_features.model_dump()
            message = _build_image_review_message(image_features)
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": image_features,
            }
            state.add_user_message(effective_message, metadata={"action": "image_review"})
            state.add_assistant_message(response["message"])
            return response

        msg_lower = effective_message.lower().strip()

        # ── Check for confirmation ────────────────────────────────────────
        confirmation_keywords = (
            "yes", "yeah", "yep", "sure", "ok", "okay",
            "plan it", "plan", "go ahead", "let's do it", "let's go",
            "sounds good", "looks good", "that sounds good", "that looks good",
            "proceed", "continue", "correct", "right", "agree", "i agree",
            "make it", "do it", "perfect", "absolutely", "definitely",
        )
        rejection_keywords = (
            "no", "nope", "nah", "never mind", "forget it", "forget",
            "no thanks", "no thank you", "not really", "not interested",
            "start over", "reset", "cancel", "skip",
        )

        is_confirmed = any(
            msg_lower == kw or msg_lower.startswith(kw + " ") or msg_lower.startswith(kw + ",")
            or msg_lower.startswith(kw + ".") or msg_lower == kw + "!"
            for kw in confirmation_keywords
        )
        is_rejected = any(
            msg_lower == kw or msg_lower.startswith(kw + " ") or msg_lower.startswith(kw + ",")
            or msg_lower.startswith(kw + ".") or msg_lower == kw + "!"
            for kw in rejection_keywords
        )

        if is_confirmed:
            # User confirmed — fuse pending features into slots
            pending = state.pending_image_features
            if pending:
                _fuse_pending_image_features(state, pending)
                logger.info(
                    "[ConversationAgent] User confirmed image preferences — fused into slots"
                )
            state.pending_image_features = None

            # ── Check what slots are already filled ──────────────────────
            city = state.slots.destination_city
            duration = state.slots.duration_days
            state.slots.fill_defaults()

            if state.slots.is_complete():
                # All slots are filled — proceed directly to plan generation
                state.transition_to(ConversationPhase.PLAN_GENERATION)
                state.plan_started_at = datetime.now(timezone.utc).isoformat()
                response = await _handle_plan_trip(
                    user_id, effective_message, {}, image_features, token, state
                )
                state.add_user_message(effective_message, metadata={"action": "confirm_image"})
                # Enrich with preference data for the pre-itinerary message
                if response and response.get("itinerary") and isinstance(response.get("itinerary"), dict):
                    _prefs = _build_preference_summary(state.slots)
                    if _prefs:
                        response["preference_summary"] = _prefs

                if response and response.get("message"):
                    state.add_assistant_message(response["message"])
                return response

            state.transition_to(ConversationPhase.SLOT_FILLING)

            if not city:
                message = (
                    "Great! I've noted your preferences from the photo. "
                    "Now, where would you like to go? I can plan a trip to cities like "
                    "Cairo, Luxor, Aswan, or anywhere else you're interested in."
                )
            elif not duration:
                message = (
                    "Great! I've noted your preferences from the photo, and "
                    "I see you're interested in visiting " + str(city) + ". "
                    "How many days would you like for your trip?"
                )
            else:
                missing = state.slots.missing_required()
                msg_parts = ["Great! I've noted your preferences from the photo."]
                msg_parts.append(" Let's plan your trip to " + str(city))
                if duration:
                    day_word = "day" + ("s" if duration != 1 else "")
                    msg_parts.append(" for " + str(duration) + " " + day_word)
                msg_parts.append("!")
                msg_parts.append(" Just a few more details: " + ", ".join(missing) + ".")
                message = "".join(msg_parts)
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": None,
            }
            state.add_user_message(effective_message, metadata={"action": "confirm_image"})
            state.add_assistant_message(response["message"])
            return response

        elif is_rejected:
            # User declined — discard image features and start fresh
            state.pending_image_features = None
            state.transition_to(ConversationPhase.SLOT_FILLING)
            logger.info(
                "[ConversationAgent] User declined image preferences — starting fresh"
            )

            message = (
                "No problem! Let's start fresh. "
                "Where would you like to go? I can plan a trip to cities like "
                "Cairo, Luxor, Aswan, or anywhere else you're interested in."
            )
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": None,
            }
            state.add_user_message(effective_message, metadata={"action": "reject_image"})
            state.add_assistant_message(response["message"])
            return response

        # ── Unclear response — ask again ──────────────────────────────────
        pending = state.pending_image_features
        if pending:
            message = _build_image_review_retry_message(pending)
        else:
            message = (
                "I'm not sure what you meant. Would you like me to plan a trip "
                "based on your photo? Just say 'yes' or 'no thanks'."
            )
        response = {
            "response_type": "clarification",
            "message": message,
            "itinerary": None,
            "image_features": None,
        }
        state.add_user_message(effective_message, metadata={"action": "image_review"})
        state.add_assistant_message(response["message"])
        return response

    # ── Fresh image upload in early phase → show review (intercept before interpreter) ──
    if (image_features and image_features.confidence != "low"
        and state.phase in (ConversationPhase.GREETING, ConversationPhase.SLOT_FILLING)):
        state.pending_image_features = image_features.model_dump()
        state.transition_to(ConversationPhase.IMAGE_REVIEW)
        message = _build_image_review_message(image_features)
        response = {
            "response_type": "clarification",
            "message": message,
            "itinerary": None,
            "image_features": image_features,
        }
        state.add_user_message(effective_message, metadata={"action": "image_uploaded"})
        state.add_assistant_message(response["message"])
        return response


    # ── STEP 1: Call message interpreter ──────────────────────────────────
    router_result = await interpret_message(state, effective_message)
    state.slots.merge(router_result.extracted)
    state.add_user_message(effective_message, metadata={"action": router_result.action})

    # ── Guard: clear hallucinated interests ────────────────────────────────
    # The LLM sometimes manufactures default interests (e.g. ["history",
    # "sightseeing"]) when the user only provides a destination + duration.
    # If the user's message doesn't mention any of the extracted interests,
    # the interests are likely hallucinated — clear them back to None so
    # the downstream safety check (which guards against None) catches it.
    # Only check current-turn extraction (router_result.extracted), NOT
    # state.slots.interests which includes interests from prior turns.
    # CRITICAL: Only run this guard during GREETING/SLOT_FILLING where interests
    # haven't been confirmed yet. Once past those phases, interests have been
    # used to generate the itinerary and must NOT be cleared.
    if state.phase in (ConversationPhase.GREETING, ConversationPhase.SLOT_FILLING):
        extracted_interests = router_result.extracted.get("interests")
        if extracted_interests and effective_message:
            msg_lower = effective_message.lower()
            user_mentioned = any(
                interest.lower() in msg_lower
                for interest in extracted_interests
            )
            if not user_mentioned:
                logger.info(
                    "[ConversationAgent] Cleared hallucinated interests=%s "
                    "from message: %.60s",
                    extracted_interests, effective_message,
                )
                state.slots.interests = None

    # ── STEP 2: Fuse image features into slots if available ───────────────
    image_acknowledgment = None
    if image_features and image_features.confidence != "low":
        img_interests = image_features.interests
        if img_interests:
            existing_interests = state.slots.interests or []
            existing_lower = {i.lower() for i in existing_interests}
            for interest in img_interests:
                if interest.lower() not in existing_lower:
                    existing_interests.append(interest)
                    existing_lower.add(interest.lower())
            state.slots.interests = existing_interests
            logger.info(
                "[ConversationAgent] Fused image interests into slots: %s",
                img_interests,
            )
            image_acknowledgment = f"I noticed your interest in {', '.join(img_interests[:3])} from your photo!"

    action = router_result.action

    logger.info(
        "[DIAG][action_routing] user=%s phase=%s action=%s dest=%s turn=%d message=%.80s",
        user_id, state.phase.value, action,
        state.slots.destination_city, state.turn_count,
        effective_message,
    )

    # ── HANDLE COMPLETED STATE — terminal (one conversation = one trip) ──
    if state.phase == ConversationPhase.COMPLETED:
        if action == "answer_question":
            # Allow answering general questions about the finalized trip
            message = router_result.response
            if image_acknowledgment:
                message = f"{image_acknowledgment} {message}"
            response = {
                "response_type": "chat",
                "message": message,
                "itinerary": state.itinerary,
                "image_features": image_features,
            }
            if response.get("message"):
                state.add_assistant_message(response["message"])
            return response

        # Block all other actions — one conversation, one trip only
        logger.info("[ConversationAgent] Blocked action '%s' in COMPLETED phase (terminal)", action)
        response = {
            "response_type": "chat",
            "message": "Your trip has been finalized! I can answer questions about your trip, but I cannot make changes or start a new trip in this conversation.",
            "itinerary": state.itinerary,
            "image_features": image_features,
        }
        if response.get("message"):
            state.add_assistant_message(response["message"])
        return response

    # ── SAFETY OVERRIDE ────────────────────────────────────────────────────
    # Flight change requests can arrive after flight selection has moved on.
    # The interpreter may route these as hotel picks, itinerary edits, or booking
    # choices depending on the current phase. Detect the cheap intent here and
    # send the user back through the existing flight search path.
    flight_change = None
    if state.phase in (
        ConversationPhase.FLIGHT_SELECTION,
        ConversationPhase.HOTEL_SELECTION,
        ConversationPhase.BOOKING,
    ):
        flight_change = _is_flight_change_request(
            effective_message,
            router_result.extracted,
        )

    if flight_change:
        logger.info(
            "[FlightChangeRequest] Intercepted during phase=%s updates=%s",
            state.phase.value, flight_change,
        )
        state.transition_to(ConversationPhase.FLIGHT_SELECTION)
        state.slots.selected_flight_offer = None
        _apply_flight_change_updates(state, flight_change)

        response = await _handle_search_flights(
            state, effective_message, router_result, image_features,
        )
        acknowledgement = _flight_change_acknowledgment(flight_change)
        if response.get("message"):
            response["message"] = f"{acknowledgement}\n\n{response['message']}"
        if response.get("message"):
            state.add_assistant_message(response["message"])
        return response

    if action == "ask_clarification" and state.slots.is_complete():
        action = "plan_trip"

    # ── BOOKING phase: route "1" / "2" / pay / do it later → approve ────
    if state.phase == ConversationPhase.BOOKING and action != "approve_itinerary":
        msg_lower = effective_message.lower()
        booking_keywords = ["1", "2", "pay", "do it later", "skip", "later",
                          "not now", "book later", "pay later"]
        if any(kw in msg_lower for kw in booking_keywords):
            logger.info(
                "[ConversationAgent] Booking phase override: '%s' → approve_itinerary",
                effective_message[:60],
            )
            action = "approve_itinerary"

    # Safety net: if LLM misroutes approve/confirm during review phases,
    # force the correct action so the user isn't asked about interests.
    if state.phase in (ConversationPhase.ITINERARY_REVIEW, ConversationPhase.FLIGHT_SELECTION, ConversationPhase.HOTEL_SELECTION) and action not in ("approve_itinerary", "modify_itinerary"):
        msg_lower = effective_message.lower().strip()
        approve_keywords = ["approve", "confirm", "looks good", "they all look good",
                           "looks great", "i approve", "i confirm", "looks perfect",
                           "all good"]
        if any(msg_lower == kw or msg_lower.startswith(kw + " ") or msg_lower.startswith(kw + ".")
               or msg_lower == kw + "!" or msg_lower.startswith(kw + ",")
               for kw in approve_keywords):
            logger.info(
                "[ConversationAgent] Itinerary review override: '%s' => approve_itinerary "
                "(was %s, phase=%s)",
                effective_message[:60], action, state.phase.value,
            )
            action = "approve_itinerary"

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

        # ── Safety check: ask for interests before planning ─────────────
        # The LLM sometimes chooses "plan_trip" even when interests are
        # still None (not provided).  Before filling defaults and proceeding
        # to plan generation, check if interests are genuinely missing.
        if state.slots.interests is None:
            logger.info(
                "[ConversationAgent] Interests missing despite plan_trip action — "
                "redirecting to ask_clarification"
            )
            state.transition_to(ConversationPhase.SLOT_FILLING)
            state.last_question_field = "interests"
            city = state.slots.destination_city or "your destination"
            duration = f"{state.slots.duration_days}-day" if state.slots.duration_days else ""
            message = (
                f"Great, a {duration} trip to {city}! What are you interested in? "
                f"You can tell me things like history, food, museums, shopping, "
                f"or anything you enjoy. Or say 'surprise me' and I'll plan a well-rounded trip!"
            )
            if image_acknowledgment:
                message = f"{image_acknowledgment} {message}"
            response = {
                "response_type": "clarification",
                "message": message,
                "itinerary": None,
                "image_features": image_features,
            }
            if response.get("message"):
                state.add_assistant_message(response["message"])
            return response

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

    # ── ACTION: SELECT HOTEL (during hotel_selection phase) ───────────────
    elif action == "select_hotel" and state.phase == ConversationPhase.HOTEL_SELECTION:
        response = await _handle_select_hotel(
            state, effective_message, router_result, image_features,
        )

    # ── ACTION: APPROVE EXISTING ITINERARY ──────────────────────────────────
    elif action == "approve_itinerary":
        # Check accommodation type change FIRST, regardless of phase,
        # so it's applied whether we go to FLIGHT_SELECTION or HOTEL_SELECTION.
        acc_type_change, star_class_change = _is_accommodation_type_change(
        effective_message,
        current_preferences=state.slots.accommodation_preferences,
    ) or (None, None)
        if acc_type_change or star_class_change is not None:
            logger.info(
                "[ConversationAgent] Accommodation type change '%s' intercepted during approval (deferred to _run_hotel_selection_and_present)",
                acc_type_change,
            )

        # ── If in BOOKING phase, user approves → proceed to COMPLETED ──
        if state.phase == ConversationPhase.BOOKING:
            state.transition_to(ConversationPhase.COMPLETED)
            booking_data = _build_booking_data(state)
            flight_booking = None
            has_offer = state.slots.selected_flight_offer is not None
            logger.info(
                "[ApproveBooking] selected_flight_offer present=%s",
                has_offer,
            )
            if state.slots.selected_flight_offer:
                selected = state.slots.selected_flight_offer
                flight_booking = {
                    "selected_offer": selected,
                    "origin_city": state.slots.origin_city,
                    "destination_city": state.slots.destination_city,
                    "airline": selected.get("airline_name", selected.get("airline_code", "")),
                    "flight_number": selected.get("flight_number", ""),
                    "total_price": selected.get("total_price", 0),
                    "currency": selected.get("currency", ""),
                    "raw_offer": selected.get("raw_offer"),
                    "trip_id": state.trip_id,
                    "is_round_trip": bool(state.slots.is_round_trip),
                }
            final_message = _format_itinerary(state.itinerary, approved=True)
            response = {
                "response_type": "booking_confirmed",
                "message": final_message + "\n\n💳 You can now proceed to payment through the app.",
                "itinerary": state.itinerary,
                "booking_data": booking_data,
                "flight_booking": flight_booking,
                "image_features": image_features,
                "action": "approve_itinerary",
            }

        # ── If already in HOTEL_SELECTION ──────────────────────────────
        elif state.phase == ConversationPhase.HOTEL_SELECTION:
            # If the user asked for an accommodation type change (e.g. "provide resorts"),
            # re-run hotel selection with the new preference instead of finalizing.
            if acc_type_change or star_class_change is not None:
                logger.info(
                    "[ConversationAgent] Re-running hotel selection with type '%s'",
                    acc_type_change,
                )
                response = await _run_hotel_selection_and_present(
                    state, effective_message, image_features,
                    acc_type_change=acc_type_change,
                    star_class_change=star_class_change,
                )
            else:
                hotels = (state.itinerary or {}).get("accommodation_suggestions", [])
                if hotels:
                    state.itinerary["selected_hotel"] = hotels[0]
                state.approve_itinerary(itinerary_id=None)
                if state.itinerary and state.itinerary.get("accommodation_suggestions"):
                    final_message = _format_itinerary(state.itinerary, approved=True)
                    response = {
                        "response_type": "itinerary",
                        "message": final_message,
                        "itinerary": state.itinerary,
                        "image_features": None,
                        "action": "approve_itinerary",
                        "ui": {"actions": ["replace_itinerary_card"]},
                    }
                else:
                    response = {
                        "response_type": "chat",
                        "message": router_result.response,
                        "itinerary": None,
                        "image_features": None,
                    }

        # ── If in FLIGHT_SELECTION, "approve" means skip flights → show hotels ──
        elif state.phase == ConversationPhase.FLIGHT_SELECTION:
            # User is done with flights (or doesn't want them), proceed to hotels
            response = await _run_hotel_selection_and_present(
                state, effective_message, image_features,
            )

        # ── First-time approval: ask about flights before hotels ──
        else:
            state.transition_to(ConversationPhase.FLIGHT_SELECTION)
            message = (
                f"✅ Your stops look great! Before we find you a place to stay, "
                f"would you like to book a flight for this trip? "
                f"Where will you be flying from?"
            )
            response = {
                "response_type": "chat",
                "message": message,
                "itinerary": state.itinerary,
                "image_features": image_features,
                "action": "approve_itinerary",
            }

    # ── ACTION: SEARCH FLIGHTS (during flight_selection phase) ─────────────
    elif action == "search_flights" and state.phase == ConversationPhase.FLIGHT_SELECTION:
        response = await _handle_search_flights(
            state, effective_message, router_result, image_features,
        )

    # ── ACTION: SELECT FLIGHT (during flight_selection phase) ──────────────
    elif action == "select_flight" and state.phase == ConversationPhase.FLIGHT_SELECTION:
        response = await _handle_select_flight(
            state, effective_message, router_result, image_features,
        )

    # ── ACTION: MODIFY EXISTING ITINERARY ───────────────────────────────────
    elif action == "modify_itinerary":
        if state.phase == ConversationPhase.ITINERARY_REVIEW:
            response = await _handle_modify_itinerary(
                user_id, state, effective_message, router_result, image_features, token,
            )
        elif state.phase == ConversationPhase.HOTEL_SELECTION:
            # During hotel selection, accommodation type changes (e.g. "provide resorts")
            # should re-run hotel selection, not return the full itinerary.
            acc_type_change, star_class_change = _is_accommodation_type_change(
                    effective_message,
                    current_preferences=state.slots.accommodation_preferences,
                ) or (None, None)
            if acc_type_change or star_class_change is not None:
                response = await _handle_select_hotel(
                    state, effective_message, router_result, image_features,
                )
            else:
                response = {
                    "response_type": "chat",
                    "message": router_result.response,
                    "itinerary": None,
                    "image_features": image_features,
                }
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
        include_itinerary = state.phase == ConversationPhase.ITINERARY_REVIEW
        response = {
            "response_type": "chat",
            "message": message,
            "itinerary": state.itinerary if include_itinerary else None,
            "image_features": image_features,
        }
        # When the LLM misroutes a modification (e.g. "remove outdoors") as
        # answer_question, the itinerary data is still present but the card
        # would be suppressed because response_type is "chat" not "itinerary".
        # Adding the replace_itinerary_card action ensures the card renders.
        if include_itinerary and state.itinerary:
            response["ui"] = {"actions": ["replace_itinerary_card"]}

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

    # Enrich itinerary responses with preference data for the pre-itinerary message
    if response and response.get("itinerary") and isinstance(response.get("itinerary"), dict):
        _prefs = _build_preference_summary(state.slots)
        if _prefs:
            response["preference_summary"] = _prefs

    if response and response.get("message"):
        state.add_assistant_message(response["message"])

    return response

def _prepare_message(user_message: Optional[str], image_features: Optional[VisionFeatures] = None) -> str:
    effective_message = (user_message or "").strip()
    if effective_message:
        return effective_message
    # Build a descriptive fallback when the user only uploaded an image
    # so the message interpreter can route the intent correctly.
    if image_features and image_features.confidence != "low":
        hints = []
        if image_features.interests:
            hints.append(f"interests={image_features.interests}")
        if image_features.travel_style:
            hints.append(f"style={image_features.travel_style}")
        if image_features.pace:
            hints.append(f"pace={image_features.pace}")
        if image_features.budget_level:
            hints.append(f"budget={image_features.budget_level}")
        signal = ", ".join(hints) if hints else "low-signal"
        return (
            f"[Image uploaded — analysis: {signal}] "
            "Plan a trip based on this image."
        )
    return "I uploaded an image for my trip."

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
    recovery_state: Optional[dict] = None,
) -> dict:
    lock = _get_user_lock(user_id)
    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id, recovery_state=recovery_state)
        image_features = await _parse_image(image_bytes)
        effective_message = _prepare_message(user_message, image_features)
        response = await _process_message(user_id, state, effective_message, image_features, token)
        await manager.save(state)
        await manager.extend_ttl(state.session_id)

        if response:
            response["session_id"] = state.session_id
            response["phase"] = state.phase.value

        _log_itinerary_presence(
            response,
            phase=state.phase.value if state else "?",
            source="handle_chat",
            user_id=user_id,
        )

        return response

async def handle_chat_stream(user_id, user_message, image_bytes=None, token=None, session_id=None, initial_pool_state=None, recovery_state=None):
    lock = _get_user_lock(user_id)

    async with lock:
        manager = await get_session_manager()
        state = await manager.resume_or_create(user_id, session_id, recovery_state=recovery_state)

        logger.info(
            "[DIAG][handle_chat_stream] ENTRY user=%s provided_session=%s recovery=%s -> "
            "restored_phase=%s dest=%s turn=%d hist_len=%d",
            user_id, session_id, (recovery_state is not None),
            state.phase.value, state.slots.destination_city,
            state.turn_count, len(state.history),
        )

        if initial_pool_state and not state.candidate_places:
            state.hydrate_pool(initial_pool_state)
            await manager.save(state)

        yield {"type": "session", "data": {"session_id": state.session_id, "phase": state.phase.value}}

        image_features = await _parse_image(image_bytes)
        effective_message = _prepare_message(user_message, image_features)

        from ai_engine.graph.progress import get_progress_queue, remove_progress_queue

        progress_queue = get_progress_queue(state.session_id)
        pipeline_task = asyncio.create_task(
            _process_message(user_id, state, effective_message, image_features, token)
        )

        # Always consume the progress queue while the pipeline is running,
        # regardless of the initial phase.  The phase may transition to
        # PLAN_GENERATION *inside* _process_message (e.g. after slot-filling
        # is complete), and graph nodes push progress events at that point.
        # Without this loop, progress events sit in the queue and are never
        # forwarded to the Flutter client.
        try:
            while not pipeline_task.done():
                try:
                    progress = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                    yield {"type": "progress", "data": progress}
                except asyncio.TimeoutError:
                    continue

            # Drain any remaining events after the task finishes.
            while True:
                try:
                    progress = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                    yield {"type": "progress", "data": progress}
                except asyncio.TimeoutError:
                    break
        finally:
            remove_progress_queue(state.session_id)

        response = await pipeline_task

        # Persist state to Redis with explicit failure checking.
        # If save fails silently, the next message will NOT find this
        # session and will create a fresh one — losing all collected
        # slots (destination, duration, interests, etc.).
        save_ok = await manager.save(state)
        if not save_ok:
            logger.error(
                "[ConversationAgent] FAILED to save session %s for user %s — "
                "state will be lost on next message! "
                "Phase=%s, destination=%s, duration=%s, history_len=%d",
                state.session_id, user_id,
                state.phase.value,
                state.slots.destination_city,
                state.slots.duration_days,
                len(state.history),
            )
        elif state.slots.destination_city:
            logger.info(
                "[ConversationAgent] Saved session %s for user %s — "
                "destination=%s, duration=%s, turn=%d",
                state.session_id, user_id,
                state.slots.destination_city,
                state.slots.duration_days,
                state.turn_count,
            )

        await manager.extend_ttl(state.session_id)
        phase_value = state.phase.value

    yield {"type": "phase", "data": {"phase": phase_value}}

    _log_itinerary_presence(
        response,
        phase=phase_value,
        source="handle_chat_stream",
        user_id=user_id,
    )

    message = _display_message_for_response(response, phase_value)
    async for chunk in _stream_text(message):
        yield chunk

    # Only yield a result event when there's meaningful structured data.
    # Skip it for simple clarification/chat responses that only stream text.
    if response and (
        response.get("response_type") == "itinerary"
        or response.get("response_type") == "booking"
        or response.get("response_type") == "booking_confirmed"
        or response.get("itinerary")
        or response.get("validation")
        or response.get("flight_search_results")
        or response.get("flight_booking")
        or response.get("image_features")
    ):
        result_data = {
            "message": message,
            "response_type": response.get("response_type"),
            "phase": phase_value,
            "session_id": state.session_id,
            "ui": response.get("ui"),
        }
        if response.get("action"):
            result_data["action"] = response["action"]

        # Itinerary data
        if response.get("itinerary"):
            result_data["itinerary"] = response["itinerary"]

        # Common optional fields
        for field in ("profile", "explanation", "agent_messages", "agent_metrics", "validation", "pool_state", "image_features", "accommodation_preferences"):
            if response.get(field):
                result_data[field] = response[field].model_dump() if hasattr(response[field], "model_dump") else response[field]

        # Booking data (flight + hotel selection for Flutter)
        if response.get("booking_data"):
            result_data["booking_data"] = response["booking_data"]

        # Flight booking data (for Flutter to process payment)
        has_fb = response.get("flight_booking")
        logger.info(
            "[StreamResult] flight_booking present=%s, keys=%s",
            bool(has_fb),
            list(has_fb.keys()) if isinstance(has_fb, dict) else "N/A",
        )
        if has_fb:
            # DEBUG: Check raw_offer inside flight_booking
            fb_raw = has_fb.get("raw_offer")
            logger.info(
                "[StreamResult] flight_booking.raw_offer present=%s, type=%s, is None=%s",
                "raw_offer" in has_fb if isinstance(has_fb, dict) else "N/A",
                type(fb_raw).__name__ if fb_raw is not None else "None",
                fb_raw is None,
            )
            if fb_raw is not None and isinstance(fb_raw, dict):
                logger.info(
                    "[StreamResult] flight_booking.raw_offer has %d keys: %s",
                    len(fb_raw),
                    list(fb_raw.keys())[:10],
                )
            result_data["flight_booking"] = response["flight_booking"]

        # Flight search results (for Flutter to display)
        if response.get("flight_search_results"):
            result_data["flight_search_results"] = response["flight_search_results"]

        # Flight metadata (trip type, dates)
        if response.get("trip_type"):
            result_data["trip_type"] = response["trip_type"]
        if response.get("departure_date"):
            result_data["departure_date"] = response["departure_date"]
        if response.get("return_date"):
            result_data["return_date"] = response["return_date"]
        if response.get("cabin_class"):
            result_data["cabin_class"] = response["cabin_class"]
        if response.get("duration_days"):
            result_data["duration_days"] = response["duration_days"]

        yield {"type": "result", "data": result_data}

    yield {"type": "done", "data": None}

# ── Helpers ────────────────────────────────────────────────────────────────────

# ── Flight Selection Helpers ───────────────────────────────────────────────

def _parse_date_to_iso(date_str: str | None) -> str | None:
    """Parse a user-provided date string to ISO format (YYYY-MM-DD).

    Tries common formats and falls back to None if parsing fails.
    """
    if not date_str:
        return None
    date_str = date_str.strip()

    # Already ISO format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        pass

    # Try common natural-language formats
    for fmt in (
        "%B %d, %Y", "%b %d, %Y",           # July 28, 2026 / Jul 28, 2026
        "%B %d %Y", "%b %d %Y",              # July 28 2026 / Jul 28 2026
        "%d %B %Y", "%d %b %Y",              # 28 July 2026 / 28 Jul 2026
        "%d/%m/%Y", "%m/%d/%Y",              # 28/07/2026 / 07/28/2026
        "%d-%m-%Y", "%m-%d-%Y",              # 28-07-2026 / 07-28-2026
        "%Y/%m/%d",                           # 2026/07/28
        "%d.%m.%Y",                            # 28.07.2026
    ):
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try ordinal formats (e.g. "second of july", "1st of July", "3rd of July")
    # Remove ordinals and "of" to normalize
    import re
    normalized = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str, flags=re.IGNORECASE)
    normalized = re.sub(r'\bof\b', '', normalized, flags=re.IGNORECASE)
    normalized = normalized.strip()

    for fmt in (
        "%B %d %Y", "%b %d %Y",              # July 28 2026 / Jul 28 2026
        "%d %B %Y", "%d %b %Y",              # 28 July 2026 / 28 Jul 2026
    ):
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try month-day without year (e.g. "July 28") — use current year
    try:
        parsed = datetime.strptime(f"{date_str} {datetime.now().year}", "%B %d %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        parsed = datetime.strptime(f"{date_str} {datetime.now().year}", "%b %d %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try ordinal without year (e.g. "second of july") — use current year
    try:
        parsed = datetime.strptime(f"{normalized} {datetime.now().year}", "%B %d %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        parsed = datetime.strptime(f"{normalized} {datetime.now().year}", "%b %d %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    logger.info("[DateParser] Could not parse date: %r — falling back to 30-days-from-now default", date_str)
    return None


def _extract_departure_from_range(date_str: str | None) -> str | None:
    """Strip a date-range suffix so the result can be parsed as a single departure date.

    The LLM sometimes emits ``travel_dates`` as a range like
    ``"2026-07-28 to 2026-07-31"`` or ``"July 28 - August 1"``.
    This helper extracts the start date so ``_parse_date_to_iso`` can handle it.

    Returns the cleaned string (unchanged if no range pattern is found).
    """
    if not date_str:
        return None
    # Match: first-date SPACE (to|-|\u2013|through) SPACE rest
    m = re.match(
        r"^(.+?)\s+(?:to|\u2013|\u2014|-|through)\s+.+$",
        date_str.strip(),
        re.IGNORECASE,
    )
    if m:
        logger.info(
            '[DateRange] Stripped range suffix from %r -- using "%s" as departure',
            date_str, m.group(1),
        )
        return m.group(1).strip()
    return date_str


async def _handle_search_flights(
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[VisionFeatures],
) -> dict:
    """Handle the search_flights action — search and present flight options."""
    extracted = router_result.extracted
    origin = extracted.get("origin_city") or state.slots.origin_city

    if not origin:
        # Ask the user for origin city
        message = "Where will you be flying from? Please tell me your departure city."
        return {
            "response_type": "chat",
            "message": message,
            "itinerary": state.itinerary,
            "image_features": image_features,
        }

    # Store origin
    state.slots.origin_city = origin
    dest = state.slots.destination_city or ""
    group_size = state.slots.group_size or 1

    # ── Check for cabin class preference ────────────────────────────────
    cabin_class = extracted.get("cabin_class") or state.slots.preferred_cabin_class
    if cabin_class:
        cabin_class = cabin_class.upper().strip()
        valid_classes = {"ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"}
        if cabin_class not in valid_classes:
            mapping = {
                "FIRST CLASS": "FIRST", "FIRST-CLASS": "FIRST", "1ST CLASS": "FIRST",
                "BUSINESS CLASS": "BUSINESS", "BUSINESS-CLASS": "BUSINESS",
                "PREMIUM ECONOMY": "PREMIUM_ECONOMY", "PREMIUM": "PREMIUM_ECONOMY",
                "ECONOMY CLASS": "ECONOMY", "ECONOMY-CLASS": "ECONOMY", "COACH": "ECONOMY",
            }
            cabin_class = mapping.get(cabin_class, None)
        if cabin_class:
            state.slots.preferred_cabin_class = cabin_class

    # ── Auto-set round-trip from trip duration (Option A) ──────────────
    # If the user has a multi-day trip planned, auto-infer round-trip and
    # compute the return date from departure_date + duration_days.
    # No need to ask "one-way or round-trip?" or "what date returning?".
    if state.slots.is_round_trip is None and state.slots.duration_days and state.slots.duration_days >= 1:
        state.slots.is_round_trip = True
        logger.info(
            "[FlightSelection] Auto-set round-trip from duration=%d days",
            state.slots.duration_days,
        )

    # Allow explicit override if the user said "one-way"
    is_round_trip = extracted.get("is_round_trip")
    if is_round_trip is not None:
        state.slots.is_round_trip = is_round_trip
        if is_round_trip is False:
            if state.slots.return_date:
                logger.info(
                    "[FlightSelection] Clearing return date for one-way flight: %s",
                    state.slots.return_date,
                )
            state.slots.return_date = None

    # ── Check for departure date ────────────────────────────────────────
    travel_dates = extracted.get("travel_dates") or state.slots.travel_dates or None
    if not travel_dates:
        trip_hint = " round-trip" if state.slots.is_round_trip else ""
        message = (
            f"Great, flying from {origin} to {dest}! "
            f"What date will you be departing? "
            f"(e.g. July 28, 2026). "
            f"If you'd like round-trip flights, please also mention your return date "
            f"(e.g. 'July 28, returning August 3')."
        )
        return {
            "response_type": "chat",
            "message": message,
            "itinerary": state.itinerary,
            "image_features": image_features,
        }

    # Strip any range prefix before parsing (e.g. "2026-07-28 to 2026-07-31" → "2026-07-28")
    travel_dates = _extract_departure_from_range(travel_dates) or travel_dates

    # Parse date to ISO format
    departure_date = _parse_date_to_iso(travel_dates)

    # ── Auto-compute return date from departure + duration ────────────
    return_date = None
    explicit_return_date = extracted.get("return_date")
    if not explicit_return_date and extracted.get("is_round_trip") is None:
        explicit_return_date = state.slots.return_date
    if not state.slots.is_round_trip:
        state.slots.return_date = None
    elif explicit_return_date:
        parsed_return_date = _parse_date_to_iso(explicit_return_date)
        return_date = parsed_return_date or explicit_return_date
        state.slots.return_date = return_date
        logger.info(
            "[FlightSelection] Using explicit return date: %s",
            return_date,
        )
    elif departure_date and state.slots.duration_days:
        try:
            dep = datetime.strptime(departure_date, "%Y-%m-%d")
            ret = dep + timedelta(days=state.slots.duration_days)
            return_date = ret.strftime("%Y-%m-%d")
            state.slots.return_date = return_date
            logger.info(
                "[FlightSelection] Auto-computed return date: %s (depart=%s + %d days)",
                return_date, departure_date, state.slots.duration_days,
            )
        except (ValueError, TypeError):
            logger.warning("[FlightSelection] Could not compute return date from %r", departure_date)

    trip_type = "round-trip" if state.slots.is_round_trip else "one-way"
    cabin_label = f" ({cabin_class})" if cabin_class else ""
    return_label = f" → return {return_date}" if return_date else ""
    logger.info(
        "[FlightSelection] Searching %s flights: %s → %s (depart=%s%s, adults=%s, cabin=%s)",
        trip_type, origin, dest, departure_date or "(30-day default)", return_label,
        group_size, cabin_class or "any",
    )

    offers = await search_flights_for_trip(
        origin_city=origin,
        destination_city=dest,
        departure_date=departure_date,
        adults=group_size,
        cabin_class=cabin_class,
        return_date=return_date,
    )
    state.slots.flight_search_results = offers

    if not offers:
        filter_note = f" {cabin_class}" if cabin_class else ""
        message = (
            f"I couldn't find{filter_note} {trip_type} flights from {origin} to {dest} "
            f"on {departure_date or 'that date'}"
            f"{f' returning {return_date}' if return_date else ''}. "
            f"Would you like to try a different origin city, date, "
            f"cabin class, or proceed to hotels?"
        )
    else:
        flight_text = format_flight_options(offers, cabin_class_filter=cabin_class)
        header_note = f" {cabin_class}" if cabin_class else ""
        return_note = f", returning {return_date}" if return_date else ""
        message = (
            f"Here are the available{header_note} {trip_type} flights "
            f"from {origin} to {dest} on {departure_date}{return_note}:\n\n"
            f"{flight_text}\n"
            f"Which one catches your eye? (Just say the number or airline name.)"
        )

    return {
        "response_type": "chat",
        "message": message,
        "itinerary": state.itinerary,
        "image_features": image_features,
        "flight_search_results": offers[:3] if offers else [],
        "trip_type": trip_type,
        "departure_date": departure_date,
        "return_date": return_date,
        "cabin_class": cabin_class,
        "duration_days": state.slots.duration_days,
    }

async def _handle_select_flight(
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[VisionFeatures],
) -> dict:
    """Handle the select_flight action — store selection and proceed to hotels.

    If the user instead requests a different cabin class (e.g. "provide first class
    flights"), we intercept it here and re-route to _handle_search_flights with
    the updated cabin class preference — just like _handle_select_hotel intercepts
    accommodation type changes.
    """
    # ── Check for cabin class request first ─────────────────────────
    cabin_class = _is_cabin_class_request(effective_message)
    if cabin_class:
        logger.info(
            "[SelectFlight] Cabin class request '%s' detected — re-routing to search",
            cabin_class,
        )
        # Store the cabin class preference on slots so _handle_search_flights picks it up
        state.slots.preferred_cabin_class = cabin_class
        return await _handle_search_flights(
            state, effective_message, router_result, image_features,
        )

    offers = state.slots.flight_search_results or []
    extracted = router_result.extracted
    selected_number = extracted.get("selected_flight_number")

    selected = extract_flight_selection(effective_message, offers, selected_number)

    if not selected:
        # Could not determine which flight
        message = (
            "I didn't catch which flight you want. Please try again with "
            "the number (e.g. 'flight 2') or airline name."
        )
        return {
            "response_type": "chat",
            "message": message,
            "itinerary": state.itinerary,
            "image_features": image_features,
        }

    # Store the selected flight offer in slots
    state.slots.selected_flight_offer = selected

    logger.info(
        "[FlightSelection] User selected flight: %s %s (%s %s)",
        selected.get("airline_name", ""),
        selected.get("flight_number", ""),
        selected.get("total_price", "?"),
        selected.get("currency", ""),
    )

    # DEBUG: Deep inspection of selected offer's raw_offer
    raw_val = selected.get("raw_offer")
    logger.info(
        "[_handle_select_flight] SELECTED offer keys=%s, raw_offer key present=%s, raw_offer value type=%s, raw_offer is None=%s",
        list(selected.keys()),
        "raw_offer" in selected,
        type(raw_val).__name__,
        raw_val is None,
    )
    if raw_val is not None and isinstance(raw_val, dict):
        logger.info(
            "[_handle_select_flight] raw_offer has %d keys: %s",
            len(raw_val),
            list(raw_val.keys())[:20],
        )
        for key in ["id", "type", "source", "instantTicketingRequired"]:
            if key in raw_val:
                logger.info("[_handle_select_flight] raw_offer.%s=%s", key, raw_val[key])

    # Build flight booking info for the Flutter client
    has_raw = selected.get("raw_offer") is not None
    logger.info(
        "[SelectFlight] Building flight_booking - selected=%s %s, "
        "raw_offer present=%s, raw_offer type=%s",
        selected.get("airline_name", ""),
        selected.get("flight_number", ""),
        has_raw,
        type(selected.get("raw_offer")).__name__ if selected.get("raw_offer") else "None",
    )
    flight_booking = {
        "selected_offer": selected,
        "origin_city": state.slots.origin_city,
        "destination_city": state.slots.destination_city,
        "airline": selected.get("airline_name", selected.get("airline_code", "")),
        "flight_number": selected.get("flight_number", ""),
        "total_price": selected.get("total_price", 0),
        "currency": selected.get("currency", ""),
        "raw_offer": selected.get("raw_offer"),
        "trip_id": state.trip_id,
        "is_round_trip": bool(state.slots.is_round_trip),
    }
    if state.slots.return_date:
        flight_booking["return_date"] = state.slots.return_date

    # Present a summary to the user, then proceed to hotel selection
    airline = selected.get("airline_name", selected.get("airline_code", "?"))
    flight_num = selected.get("flight_number", "")
    price = selected.get("total_price", 0)
    currency = selected.get("currency", "")
    origin_iata = selected.get("origin_iata", "")
    dest_iata = selected.get("destination_iata", "")
    depart = selected.get("departure_at_formatted", "")
    arrival = selected.get("arrival_at_formatted", "")

    selection_msg = (
        f"✈️ Great choice! You selected:\n"
        f"**{airline} {flight_num}**: {origin_iata} → {dest_iata}\n"
        f"{depart} → {arrival}\n"
        f"**{price} {currency}**\n\n"
        f"Your flight details are saved. You can book through our payment system.\n"
        f"Now, let's find you a place to stay!"
    )

    # Proceed to hotel selection
    hotel_response = await _run_hotel_selection_and_present(
        state, effective_message, image_features,
    )

    # Combine the flight selection message with hotel options
    hotel_message = hotel_response.get("message", "")
    combined_message = f"{selection_msg}\n\n{hotel_message}"

    return {
        "response_type": "chat",
        "message": combined_message,
        "itinerary": state.itinerary,
        "image_features": image_features,
        "flight_booking": flight_booking,
        "agent_messages": hotel_response.get("agent_messages", []),
        "accommodation_preferences": hotel_response.get("accommodation_preferences")
            or state.slots.accommodation_preferences or [],
    }

async def _run_hotel_selection_and_present(
    state: ConversationState,
    effective_message: str,
    image_features: Optional[VisionFeatures],
    acc_type_change: str | None = None,
    star_class_change: int | None = None,
) -> dict:
    """Run the hotel selection agent and present hotel options to the user.

    This is called when transitioning from FLIGHT_SELECTION to HOTEL_SELECTION,
    or when the user approves from ITINERARY_REVIEW with no flights needed.

    If ``acc_type_change`` and ``star_class_change`` are provided, they are
    used directly (no re-detection needed).  This avoids duplicate calls to
    ``_is_accommodation_type_change`` when the caller has already detected
    the change.
    """
    # Check if the user's message implies an accommodation type change
    # (only re-detect if the caller hasn't already done so)
    if acc_type_change is None and star_class_change is None:
        acc_type_change, star_class_change = _is_accommodation_type_change(
            effective_message,
            current_preferences=state.slots.accommodation_preferences,
        ) or (None, None)
    if acc_type_change or star_class_change is not None:
        logger.info(
            "[ConversationAgent] Accommodation type change '%s' intercepted during approval",
            acc_type_change,
        )
        _apply_accommodation_change(state.slots, acc_type_change, star_class=star_class_change)

    # ── Search hotels directly from the DB (like flights) ─────────
    hotel_agent_msgs: list[str] = []
    if state.itinerary:
        city = state.slots.destination_city or state.itinerary.get("destination", "")
        if city:
            acc_prefs = state.slots.accommodation_preferences or []
            accommodation_type = None
            if acc_prefs:
                from ai_engine.tools.slot_normalizer import map_accommodation_to_type
                accommodation_type = map_accommodation_to_type(acc_prefs)

            hotels = await hs_search_hotels(
                city=city,
                accommodation_type=accommodation_type,
                preferred_star_class=state.slots.preferred_hotel_star_class,
                budget_level=state.slots.budget_level,
                max_results=10,
            )

            state.slots.hotel_search_results = hotels
            # Populate itinerary.accommodation_suggestions for Flutter compat
            state.itinerary["accommodation_suggestions"] = [
                {
                    "id": h.get("id", ""),
                    "name": h.get("name", ""),
                    "sub_category": h.get("sub_category", ""),
                    "accommodation_type": h.get("accommodation_type", "hotel"),
                    "lat": h.get("lat", 0),
                    "lon": h.get("lon", 0),
                    "rating": h.get("rating", 0),
                    "why_recommended": (
                        f"{h.get('accommodation_type', 'Hotel').capitalize()} "
                        f"near your route."
                    ),
                    "nightly_rate": h.get("nightly_rate", 0),
                    "address": h.get("address", ""),
                    "photos": (h.get("photos") or [])[:1],
                }
                for h in hotels
            ]
            hotel_agent_msgs.append(
                f"[HotelAgent] Found {len(hotels)} hotels in {city}"
            )
            logger.info(
                "[HotelAgent] Found %d hotels in '%s'", len(hotels), city,
            )

    # ── Accommodation type change during approval ────────────
    if acc_type_change or star_class_change is not None:
        if state.itinerary and state.itinerary.get("accommodation_suggestions"):
            return {
                "response_type": "itinerary",
                "message": _format_itinerary(state.itinerary, approved=False),
                "itinerary": state.itinerary,
                "image_features": image_features,
                "agent_messages": hotel_agent_msgs,
                "ui": {"actions": ["replace_itinerary_card"]},
            }
        else:
            return {
                "response_type": "chat",
                "message": f"Updated your accommodation to {acc_type_change}. "
                          "You can approve or modify further.",
                "itinerary": None,
                "image_features": image_features,
            }

    # Transition to hotel selection phase — user picks their preferred hotel
    state.transition_to(ConversationPhase.HOTEL_SELECTION)
    hotel_prompt = _format_hotel_options(state.itinerary)

    # If the user has a selected flight, mention it
    flight_note = ""
    if state.slots.selected_flight_offer:
        flight = state.slots.selected_flight_offer
        airline = flight.get("airline_name", flight.get("airline_code", ""))
        flight_num = flight.get("flight_number", "")
        flight_note = (
            f"✈️ Your flight ({airline} {flight_num}) is noted. "
            f"You can book it through the payment section.\n\n"
        )

    message = (
        f"{flight_note}Here are the hotel options:\n\n"
        f"{hotel_prompt}\n"
        f"Which hotel would you like to stay at? You can pick by number, "
        f"name, or just say 'looks good' to go with the first option."
    )
    return {
        "response_type": "chat",
        "message": message,
        "itinerary": state.itinerary,
        "image_features": image_features,
        "agent_messages": hotel_agent_msgs,
        "accommodation_preferences": state.slots.accommodation_preferences or [],
    }


def _card_backed_itinerary_response(response: dict) -> bool:
    """Return True when the itinerary should be rendered as a UI card."""
    if not response.get("itinerary"):
        return False
    ui = response.get("ui") or {}
    actions = ui.get("actions", []) if isinstance(ui, dict) else []
    return (
        response.get("response_type") == "itinerary"
        or "replace_itinerary_card" in actions
    )


def _image_features_have_signal(features) -> bool:
    if not features:
        return False
    if hasattr(features, "model_dump"):
        features = features.model_dump()
    if not isinstance(features, dict):
        return False
    return (
        features.get("confidence") in ("high", "medium")
        and bool(features.get("interests"))
    )


def _build_preference_summary(slots) -> dict:
    """Build a compact summary of user preferences for display in the pre-itinerary message."""
    summary: Dict[str, Any] = {}
    if slots.interests:
        summary["interests"] = slots.interests[:5]
    if slots.travel_style:
        summary["travel_style"] = slots.travel_style
    if slots.pace:
        summary["pace"] = slots.pace
    if slots.budget_level:
        summary["budget_level"] = slots.budget_level
    if slots.food_preferences:
        summary["food_preferences"] = slots.food_preferences[:3]
    return summary


def _itinerary_summary(itinerary: dict, *, updated: bool = False, preference_summary: dict | None = None) -> str:
    destination = itinerary.get("destination") or "your destination"
    days = itinerary.get("days", [])
    day_count = len(days) or itinerary.get("duration_days")
    stop_count = sum(len(day.get("stops", [])) for day in days)

    day_label = f"{day_count}-day " if day_count else ""
    prefix = "Your updated" if updated else "Here is your"
    message = f"{prefix} {day_label}{destination} itinerary."

    # Add a preference summary that explains what the itinerary was based on
    if preference_summary and not updated:
        pref_parts = []
        interests = preference_summary.get("interests", [])
        style = preference_summary.get("travel_style", "")
        pace = preference_summary.get("pace", "")
        budget = preference_summary.get("budget_level", "")

        if interests:
            pref_parts.append(f"based on your interest in {', '.join(interests)}")
        if style:
            pref_parts.append(f"{style} style")
        if pace:
            pref_parts.append(f"at a {pace} pace")
        if budget:
            pref_parts.append(f"with a {budget} budget")

        food_prefs = preference_summary.get("food_preferences", [])
        if food_prefs:
            pref_parts.append(f"with a taste for {', '.join(food_prefs)}")

        if pref_parts:
            message += f" I designed this {', '.join(pref_parts)}."

    if stop_count:
        message += f" Review the {stop_count} planned stops in the card below."
    else:
        message += " Review the card below."
    return message


def _extract_warning_note(message: str) -> str:
    """Keep important failure notes while stripping detailed card-like text."""
    lower = message.lower()
    for marker in (
        "i couldn't apply that change",
        "i could not apply that change",
        "note:",
        "warning:",
    ):
        idx = lower.find(marker)
        if idx >= 0:
            return message[idx:].strip()
    return ""


def _looks_like_detailed_itinerary_text(message: str) -> bool:
    lower = message.lower()
    markers = ("day ", "where to stay", "chosen hotel", "personalized")
    return len(message) > 300 or ("\n" in message and any(marker in lower for marker in markers))


def _display_message_for_response(response: Optional[dict], phase_value: str) -> str:
    """Return the text that should be streamed beside structured UI cards."""
    if not response:
        return "I'm here to help!"

    message = response.get("message") or "I'm here to help!"
    itinerary = response.get("itinerary") if isinstance(response.get("itinerary"), dict) else None
    response_type = response.get("response_type")

    if response.get("booking_data"):
        if response_type == "booking_confirmed":
            return "Your trip is confirmed. You can proceed to payment through the app."
        return "Your trip is all set. Choose whether to pay now or book later."

    flight_results = response.get("flight_search_results") or []
    if flight_results:
        count = len(flight_results)
        option_label = "option" if count == 1 else "options"
        trip_type = response.get("trip_type")
        depart = response.get("departure_date")
        ret = response.get("return_date")
        if trip_type or depart:
            parts = [f"I found {count} {trip_type or 'flight'} {option_label}"]
            if depart:
                parts.append(f"departing {depart}")
                if ret:
                    parts.append(f"returning {ret}")
                elif trip_type == "one-way":
                    parts.append("(one-way)")
            parts.append("Choose one from the card below.")
            return " · ".join(parts)
        return f"I found {count} flight {option_label}. Choose one from the card below."

    if itinerary and phase_value == ConversationPhase.HOTEL_SELECTION.value:
        hotels = itinerary.get("accommodation_suggestions", [])
        if hotels:
            count = len(hotels)
            option_label = "option" if count == 1 else "options"
            return f"I found {count} hotel {option_label}. Choose one from the card below."

    if itinerary and _card_backed_itinerary_response(response):
        warning = _extract_warning_note(message)
        if warning:
            return f"I kept the itinerary card below unchanged. {warning}"
        if not _looks_like_detailed_itinerary_text(message):
            return message
        updated = "updated" in message.lower()
        return _itinerary_summary(itinerary, updated=updated, preference_summary=response.get("preference_summary"))

    if _image_features_have_signal(response.get("image_features")):
        return "I analyzed your photo and found travel preferences you can review below."

    return message


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


# ── Image Review Helpers ─────────────────────────────────────────────────────


def _build_image_review_message(features) -> str:
    """Build a detailed image review message showing what was extracted.

    Shows interests, food_preferences, environment_type, and vibe.
    Does NOT show pace, budget_level, or travel_style per user request.
    """
    bits = []
    if features.interests:
        bits.append(f"• You seem interested in: **{', '.join(features.interests[:5])}**")
    if features.food_preferences:
        bits.append(f"• You might enjoy: **{', '.join(features.food_preferences[:3])}** cuisine")
    if features.environment_type:
        bits.append(f"• The setting looks like: **{features.environment_type}**")
    if features.vibe:
        bits.append(f"• Overall vibe: *\"{features.vibe}\"*")

    if not bits:
        return (
            "I've analyzed your photo, but I couldn't identify specific travel preferences "
            "from it. Would you like to tell me what kind of trip you're looking for, "
            "or would you like to try uploading a different photo?"
        )

    message = "I've analyzed your photo! Here's what stands out:\n\n"
    message += "\n".join(bits)
    message += (
        "\n\nWould you like me to plan a trip based on these preferences? "
        "Just say **'yes'** to go ahead, **'no thanks'** to start fresh, "
        "or tell me what you'd like to change."
    )
    return message


def _build_image_review_retry_message(pending: dict) -> str:
    """Build a retry message when the user's response is unclear."""
    bits = []
    interests = pending.get("interests", [])
    food_prefs = pending.get("food_preferences", [])
    env = pending.get("environment_type")
    vibe = pending.get("vibe")

    if interests:
        bits.append(f"interested in {', '.join(interests[:5])}")
    if food_prefs:
        bits.append(f"enjoying {', '.join(food_prefs[:3])} cuisine")
    if env:
        bits.append(f"a {env} setting")
    if vibe:
        bits.append(f'a "{vibe}" vibe')

    hint = ", ".join(bits) if bits else "some preferences from your photo"

    return (
        f"I'm not sure if that's a yes or no. Based on your photo, I noticed you seem "
        f"{hint}. "
        f"Would you like me to plan a trip based on these preferences? "
        f"Just say **'yes'** to go ahead, **'no thanks'** to start fresh, "
        f"or tell me what you'd like to change."
    )


def _fuse_pending_image_features(state, pending: dict) -> None:
    """Merge stored VisionFeatures dict into the conversation state slots.

    This is called when the user confirms the image review, fusing the
    extracted preferences (interests, food, travel_style, pace, budget)
    into the trip slots so downstream planning uses them.
    """
    # ── Merge interests (union, no duplicates) ─────────────────────────────
    img_interests = pending.get("interests", [])
    if img_interests:
        existing = state.slots.interests or []
        existing_lower = {i.lower() for i in existing}
        for interest in img_interests:
            if interest.lower() not in existing_lower:
                existing.append(interest)
                existing_lower.add(interest.lower())
        state.slots.interests = existing

    # ── Merge food preferences (union, no duplicates) ──────────────────────
    img_food = pending.get("food_preferences", [])
    if img_food:
        existing = state.slots.food_preferences or []
        existing_lower = {f.lower() for f in existing}
        for pref in img_food:
            if pref.lower() not in existing_lower:
                existing.append(pref)
                existing_lower.add(pref.lower())
        state.slots.food_preferences = existing

    # ── Merge scalar fields (only if image provides a non-None value) ─────────
    scalar_map = {
        "travel_style": "travel_style",
        "pace": "pace",
        "budget_level": "budget_level",
    }
    for img_key, slot_attr in scalar_map.items():
        val = pending.get(img_key)
        if val is not None and not getattr(state.slots, slot_attr, None):
            setattr(state.slots, slot_attr, val)

    logger.info(
        "[ImageReview] Fused pending image features: %d interests, %d food_prefs, "
        "style=%s, pace=%s, budget=%s",
        len(img_interests),
        len(img_food),
        pending.get("travel_style"),
        pending.get("pace"),
        pending.get("budget_level"),
    )


def _build_booking_data(state: ConversationState) -> dict:
    itinerary = state.itinerary or {}
    selected_hotel = itinerary.get("selected_hotel", {})
    flight = state.slots.selected_flight_offer

    flight_cost = 0.0
    flight_currency = "USD"
    if flight:
        try:
            flight_cost = float(flight.get("total_price", 0))
        except (ValueError, TypeError):
            flight_cost = 0.0
        flight_currency = flight.get("currency", "USD") or "USD"

    hotel_cost = 0.0
    if selected_hotel:
        try:
            hotel_cost = float(selected_hotel.get("nightly_rate", 0))
        except (ValueError, TypeError):
            hotel_cost = 0.0
        if state.slots.duration_days and hotel_cost > 0:
            hotel_cost = hotel_cost * state.slots.duration_days

    currency = flight_currency if flight else "USD"

    return {
        "flight": {
            "selected": flight is not None,
            "airline": flight.get("airline_name", flight.get("airline_code", "")) if flight else None,
            "flight_number": flight.get("flight_number", "") if flight else None,
            "origin_iata": flight.get("origin_iata", "") if flight else None,
            "destination_iata": flight.get("destination_iata", "") if flight else None,
            "departure_at": flight.get("departure_at_formatted", "") if flight else None,
            "arrival_at": flight.get("arrival_at_formatted", "") if flight else None,
            "price": flight_cost,
            "currency": flight_currency,
        } if flight else None,
        "hotel": {
            "selected": bool(selected_hotel),
            "name": selected_hotel.get("name", ""),
            "rating": selected_hotel.get("rating", 0),
            "nightly_rate": selected_hotel.get("nightly_rate", 0),
            "total_cost": hotel_cost,
            "currency": currency,
            "place_id": selected_hotel.get("id", ""),
        } if selected_hotel else None,
        "trip_summary": {
            "destination": state.slots.destination_city or "",
            "duration_days": state.slots.duration_days or 0,
            "travelers": state.slots.group_size or 1,
            "origin_city": state.slots.origin_city or "",
        },
        "pricing": {
            "flight_cost": flight_cost,
            "hotel_cost": hotel_cost,
            "total_estimated": round(flight_cost + hotel_cost, 2),
            "currency": currency,
        },
        "trip_id": state.trip_id,
        "has_flight": flight is not None,
        "has_hotel": bool(selected_hotel),
    }

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
        preferred_hotel_star_class=slots.preferred_hotel_star_class,
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
) -> tuple[dict, str | None]:
    """Post-edit optimization: rebalance clustered slots, then run OSRM routing.

    Returns:
        A tuple of (modified_itinerary, route_optimization_message_or_None).
        The message is suitable for appending to ``agent_messages``.
    """
    edit_type = (classification or {}).get("edit_type", "").upper()
    if edit_type in ("RE_THEME", "CHANGE_HOTEL"):
        return modified, None

    # Step 1: Rebalance slot clustering before route optimization
    from ai_engine.services.operations import _rebalance_clustered_slots
    try:
        rebalanced = _rebalance_clustered_slots(modified)
        if rebalanced is not modified:
            logger.info("[ConversationAgent] Rebalanced clustered slots after edit")
            modified = rebalanced
    except Exception as exc:
        logger.warning("[ConversationAgent] Slot rebalancing failed: %s", exc)

    # Step 2: Detect affected days for route optimization
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
        return modified, None

    try:
        result = await optimize_itinerary_days(modified, day_numbers=affected)
        # Compute route stats for logging
        n_days = len(result.get("days", []))
        total_stops = sum(len(d.get("stops", [])) for d in result.get("days", []))
        total_travel = sum(
            d.get("total_travel_time_minutes", 0) for d in result.get("days", [])
        )
        route_msg = (
            f"[RouteOptimizer] Post-edit: {n_days} days, "
            f"{total_stops} stops, {total_travel:.0f} min total travel "
            f"(re-optimized {len(affected)} affected day(s))"
        )
        logger.info("[ConversationAgent] %s", route_msg)
        return result, route_msg
    except Exception as exc:
        logger.warning("[ConversationAgent] Post-edit route optimization failed: %s", exc)
        return modified, None

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
    destination = modified.get("destination", "your trip")
    days_list = modified.get("days", [])
    total_stops = sum(len(d.get("stops", [])) for d in days_list)
    num_days = len(days_list)
    # Concise message for modifications — the itinerary card will show the full
    # plan with all stops and details.  If the card doesn't render, this brief
    # summary still gives the user useful context.
    short_msg = f"Your {num_days}-day {destination} itinerary has been updated!"
    if total_stops:
        short_msg += f" ({total_stops} stop{'s' if total_stops > 1 else ''})"
    response = {
        "response_type": "itinerary",
        "message": short_msg,
        "itinerary": modified,
        "image_features": image_features,
        "pool_state": state.get_pool_state(),
        "ui": {"actions": ["replace_itinerary_card"]},
    }
    if agent_messages:
        response["agent_messages"] = agent_messages
    if state.slots.accommodation_preferences:
        response["accommodation_preferences"] = state.slots.accommodation_preferences
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
        "ui": {"actions": ["replace_itinerary_card"]},
        "accommodation_preferences": state.slots.accommodation_preferences or [],
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
        destination_city=state.slots.destination_city,
        destination_country=state.slots.destination_country,
    )
    modifier_note = modified.pop("_modifier_note", "")
    modifier_applied = _has_real_modifications(modified, original_itinerary)

    if modifier_applied:
        modified, route_msg = await _post_edit_optimize(modified, original_itinerary, classification)
        trailing_note = modified.pop("_modifier_note", "")
        if trailing_note:
            modifier_note = f"{modifier_note}\n{trailing_note}".strip()
        if modifier_note:
            agent_messages.append(f"[ModifierAgent] {modifier_note}")
        if route_msg:
            agent_messages.append(route_msg)
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

    hints = _detect_category_hints(modification_request, pool=existing_pool)
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
    """Build a compact conversation history for the LLM.

    Limited to the last 10 messages to cap token consumption.
    Each message is truncated to 150 characters.
    """
    lines = []
    for msg in (state.history or [])[-10:]:
        role = msg.role.capitalize()
        content = (msg.content or "")[:150]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def _apply_accommodation_change(slots, new_type: str, star_class: int | None = None) -> None:
    """Apply accommodation type change with add/remove semantics.

    Adds the new type to existing preferences without removing old ones,
    so preferences accumulate over time rather than being overwritten.
    Also sets preferred_hotel_star_class if provided.
    """
    current = list(slots.accommodation_preferences or [])
    if new_type and new_type not in current:
        current.append(new_type)
    slots.accommodation_preferences = current
    if star_class is not None:
        slots.preferred_hotel_star_class = star_class

def _is_flight_change_request(message: str, extracted: dict) -> dict | None:
    """Detect trip-type/date edits for the existing flight-selection workflow.

    Returns a dict of slot updates to apply, or None if the message does not
    look like a flight edit. Dates are never parsed here; the interpreter owns
    date extraction and passes them through ``extracted``.
    """
    msg_lower = message.lower()
    if not msg_lower:
        return None

    extracted = extracted or {}
    updates: dict = {}

    one_way_patterns = [
        r"\bone[-\s]?way\b",
        r"\bsingle flight\b",
        r"\bsingle ticket\b",
        r"\bno return(?: flight| ticket)?\b",
        r"\bwithout (?:a )?return(?: flight| ticket)?\b",
        r"\bskip (?:the )?return(?: flight)?\b",
        r"\bdo(?:n't| not) need (?:a )?return(?: flight| ticket)?\b",
        r"\bnot (?:a )?round[-\s]?trip\b",
        r"\bjust (?:the )?(?:outbound|departure)(?: flight)?\b",
        r"\bonly (?:the )?(?:outbound|departure)(?: flight)?\b",
    ]
    round_trip_patterns = [
        r"\bround[-\s]?trip\b",
        r"\breturn flight\b",
        r"\breturn ticket\b",
        r"\bboth ways\b",
        r"\bthere and back\b",
        r"\bwith (?:a )?return(?: flight| ticket)?\b",
        r"\badd (?:a )?return(?: flight| ticket)?\b",
        r"\binclude (?:a )?return(?: flight| ticket)?\b",
        r"\bneed (?:a )?return(?: flight| ticket)?\b",
    ]

    one_way_change = any(re.search(pattern, msg_lower) for pattern in one_way_patterns)
    round_trip_change = any(re.search(pattern, msg_lower) for pattern in round_trip_patterns)

    return_date_context = any(kw in msg_lower for kw in (
        "return date",
        "different return",
        "new return",
        "change my return",
        "change the return",
        "push back my return",
        "move my return",
        "returning",
        "come back",
        "coming back",
        "fly back",
        "flight back",
        "back home",
    ))
    departure_date_context = any(kw in msg_lower for kw in (
        "departure date",
        "departing",
        "depart on",
        "leave on",
        "leaving on",
        "fly out",
        "outbound date",
        "travel date",
        "flight date",
    ))
    date_change_context = departure_date_context and any(kw in msg_lower for kw in (
        "actually",
        "change",
        "different",
        "instead",
        "move",
        "new",
        "push",
        "switch",
        "update",
    ))

    if one_way_change:
        updates["is_round_trip"] = False
    elif round_trip_change:
        updates["is_round_trip"] = True

    if not one_way_change:
        extracted_round_trip = extracted.get("is_round_trip")
        if extracted_round_trip is not None and (round_trip_change or return_date_context):
            updates["is_round_trip"] = extracted_round_trip

        return_date = extracted.get("return_date")
        if return_date and (return_date_context or round_trip_change):
            updates["is_round_trip"] = True
            updates["return_date"] = return_date

    travel_dates = extracted.get("travel_dates")
    if travel_dates and date_change_context:
        updates["travel_dates"] = travel_dates

    if not updates:
        return None

    logger.info(
        "[FlightChangeRequest] Detected flight change updates=%s in '%s'",
        updates, message[:60],
    )
    return updates

def _apply_flight_change_updates(state: ConversationState, updates: dict) -> None:
    """Apply flight edit slot updates and clear stale round-trip state."""
    travel_dates = updates.get("travel_dates")
    if travel_dates:
        state.slots.travel_dates = travel_dates

    if updates.get("is_round_trip") is False:
        state.slots.is_round_trip = False
        if state.slots.return_date:
            logger.info(
                "[FlightChangeRequest] Clearing return date for one-way flight: %s",
                state.slots.return_date,
            )
        state.slots.return_date = None
        return

    if "is_round_trip" in updates:
        state.slots.is_round_trip = updates["is_round_trip"]

    return_date = updates.get("return_date")
    if return_date:
        state.slots.return_date = return_date
        state.slots.is_round_trip = True

def _flight_change_acknowledgment(updates: dict) -> str:
    """Build a short acknowledgement to prefix the refreshed flight search."""
    if updates.get("is_round_trip") is False:
        return "Got it - switching to one-way."
    if updates.get("return_date"):
        return f"Got it - updating the return date to {updates['return_date']}."
    if updates.get("is_round_trip") is True:
        return "Got it - switching to round-trip."
    if updates.get("travel_dates"):
        return "Got it - updating the flight date."
    return "Got it - updating the flight search."

def _is_cabin_class_request(modification_request: str) -> str | None:
    """Detect if the user is asking for a specific cabin class during flight selection.

    Returns the normalized cabin class (e.g. 'FIRST', 'BUSINESS', 'PREMIUM_ECONOMY',
    'ECONOMY') if a cabin class request is detected, or None otherwise.

    This intercepts phrases like "first class flights", "business class",
    "premium economy", etc. during FLIGHT_SELECTION, so they aren't misrouted
    as selecting the first flight option (number 1).
    """
    msg_lower = modification_request.lower()

    # Check for explicit cabin class keywords with context words.
    # These patterns indicate the user wants a *type* of flight, not a flight number.
    # The presence of "class", "flights", "tickets", "seats", or "cabin" alongside
    # a class keyword strongly suggests a cabin class request.
    has_travel_context = any(kw in msg_lower for kw in (
        "class", "flights", "flight", "tickets", "seats", "cabin",
        "premium", "business", "economy", "coach", "first",
        "provide", "show", "give me", "i want", "change to",
        "let it be", "make it", "switch to",
        "upgrade", "downgrade",
    ))

    if not has_travel_context:
        return None

    # Detect specific cabin class phrases (longest-first to avoid short-circuit).
    # Only explicit compound phrases are matched — bare keywords like "first"
    # are NOT included to avoid false positives on selection phrases like
    # "I want the first one" (which means flight #1, not FIRST class).
    cabin_patterns = [
        # Longest compound phrases first (checked before shorter substrings)
        ("premium economy", "PREMIUM_ECONOMY"),
        ("premium-economy", "PREMIUM_ECONOMY"),
        ("first class", "FIRST"),
        ("first-class", "FIRST"),
        ("1st class", "FIRST"),
        ("business class", "BUSINESS"),
        ("business-class", "BUSINESS"),
        ("economy class", "ECONOMY"),
        ("economy-class", "ECONOMY"),
        # Common phrasings without the word "class" (e.g. "economy flights")
        ("economy flights", "ECONOMY"),
        ("economy tickets", "ECONOMY"),
        ("economy seats", "ECONOMY"),
        ("business flights", "BUSINESS"),
        ("business tickets", "BUSINESS"),
        ("coach flights", "ECONOMY"),
        ("coach tickets", "ECONOMY"),
        ("coach seats", "ECONOMY"),
    ]

    for keyword, cabin_type in cabin_patterns:
        if keyword in msg_lower:
            logger.info(
                "[CabinClassRequest] Detected cabin class: %s in '%s'",
                cabin_type, modification_request[:60],
            )
            return cabin_type

    return None

def _might_need_preference_update(classification: dict) -> bool:
    """Check if the edit classification could potentially need preference adjustment.

    REGENERATE edits go straight to the full pipeline, so preference
    adjustment is never needed.  All other edit types (preference_edit,
    surgical, unknown) may benefit from having adjustments pre-computed.
    """
    edit_type = (classification.get("edit_type") or "").upper()
    return edit_type != "REGENERATE"

def _is_star_class_request(modification_request: str) -> int | None:
    """Detect if the user is asking for a specific hotel star class.

    Returns the star class (1-5) if detected, or None otherwise.
    This intercepts phrases like "4-star hotels", "5 star", "four star", etc.
    during hotelling, without triggering a false accommodation type change.

    Modeled after _is_cabin_class_request for flight cabin class detection.
    """
    msg_lower = modification_request.lower()

    # Check for digit-star patterns: "4-star", "5 star", "3-star", etc.
    star_match = re.search(r'(\d+)\s*-?\s*star', msg_lower)
    if star_match:
        try:
            star_class = int(star_match.group(1))
            if 1 <= star_class <= 5:
                logger.info(
                    "[StarClassRequest] Detected star class: %d-star in '%s'",
                    star_class, modification_request[:60],
                )
                return star_class
        except (ValueError, TypeError):
            pass

    # Check for word patterns: "four star", "five star", "three star"
    word_patterns = {
        "four star": 4, "five star": 5, "three star": 3,
        "four-star": 4, "five-star": 5, "three-star": 3,
    }
    for phrase, star_class in word_patterns.items():
        if phrase in msg_lower:
            logger.info(
                "[StarClassRequest] Detected star class: %d-star (word) in '%s'",
                star_class, modification_request[:60],
            )
            return star_class

    return None


def _is_accommodation_type_change(modification_request: str, current_preferences: list[str] | None = None) -> tuple[str | None, int | None]:
    """Detect if the user is asking to change accommodation type (e.g. 'resorts instead of hotels').

    Returns a tuple of (accommodation_type, star_class).
    accommodation_type is a canonical type string (e.g. 'resort', 'hostel', 'luxury', 'hotel')
    or None if no type change is detected.
    star_class is an int (1-5) if a star class change is detected, or None otherwise.
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

    # Use the standalone _is_star_class_request for star class detection
    star_class = _is_star_class_request(modification_request)

    # Check for "instead of" / "instead" patterns
    has_instead = "instead" in msg_lower
    has_switch = any(kw in msg_lower for kw in ("switch to", "change to", "replace with", "use "))
    has_want = any(kw in msg_lower for kw in (
        "i want ", "give me ", "provide ", "show me ",
        "let it be ", "i'd like ", "i would like ",
        "prefer ", "make it ",
    ))

    # Also treat bare star class mentions as changes (e.g. "4-star hotels" with no switch keyword)
    if star_class is not None:
        has_want = True  # A star class mention implies intent

    if not (has_instead or has_switch or has_want):
        return None, None

    # Extract the accommodation type keyword mentioned
    # Use word-boundary matching and break on FIRST match since
    # _ACCOMMODATION_KEYWORDS lists specific phrases first.
    # This ensures "boutique hotel" -> luxury (not overwritten by "hotel").
    matched_type = None
    for keyword, acc_type in _ACCOMMODATION_KEYWORDS:
        if keyword in msg_lower:
            matched_type = acc_type
            break

    # Skip no-op type matches
    # If the matched accommodation type is already in the user's current
    # preferences, don't treat it as a change.  This prevents false positives
    # like "4-star hotels" triggering a "hotel" type change when the user
    # already prefers hotels.
    if matched_type and current_preferences:
        if matched_type in current_preferences:
            logger.info(
                "[AccommodationTypeChange] Skipping no-op type '%s' "
                "(already in current preferences: %s)",
                matched_type, current_preferences,
            )
            matched_type = None

    if matched_type:
        logger.info(
            "[AccommodationTypeChange] Detected accommodation type change: %s in '%s'",
            matched_type, modification_request[:60],
        )
    return matched_type, star_class

def _format_hotel_options(itinerary: dict) -> str:
    """Format hotel suggestions as numbered options for user selection."""
    hotels = itinerary.get("accommodation_suggestions", [])
    if not hotels:
        return "No hotel options available."

    lines = []
    for i, hotel in enumerate(hotels):
        num_emoji = _HOTEL_NUMBER_EMOJI[i] if i < len(_HOTEL_NUMBER_EMOJI) else f"{i + 1}."
        name = hotel.get("name", "Unknown")
        rating = hotel.get("rating", 0)
        acc_type = hotel.get("accommodation_type", "")
        sub_cat = hotel.get("sub_category", "")
        amenities = hotel.get("amenities", [])
        address = hotel.get("address", "")
        maps_link = hotel.get("maps_link", "")
        why = hotel.get("why_recommended", "")

        type_label = sub_cat.title() if sub_cat else (acc_type.capitalize() if acc_type else "Hotel")
        star_count = min(round(rating or 0), 5)
        stars_str = "⭐" * star_count

        lines.append(f"{num_emoji} **{name}** ({type_label})")
        if rating:
            lines.append(f"   {stars_str} {rating}/5")
        if amenities:
            am_str = ", ".join(a.capitalize() for a in amenities[:6])
            if len(amenities) > 6:
                am_str += f" +{len(amenities) - 6} more"
            lines.append(f"   🏷 {am_str}")
        if address:
            lines.append(f"   📍 {address[:70]}")
        if maps_link:
            lines.append(f"   🗺 {maps_link[:80]}")
        if why:
            lines.append(f"   💡 {why[:150]}")
        lines.append("")

    return "\n".join(lines)

def _format_itinerary(itinerary: dict, approved: bool = False) -> str:
    if not itinerary:
        return "I wasn't able to generate a complete itinerary. Please try again."

    lines = []
    destination = itinerary.get("destination", "your destination")
    days = itinerary.get("days", [])
    hotels = itinerary.get("accommodation_suggestions", [])
    selected_hotel = itinerary.get("selected_hotel")

    if approved:
        lines.append(f"✅ Your trip to {destination} has been approved!")
        lines.append("")
        if selected_hotel:
            lines.append(f"🏨 Chosen Hotel: {selected_hotel.get('name', 'Selected')}")
            lines.append("")
    else:
        lines.append(f"✨ Here's your personalized {len(days)}-day itinerary for {destination}!")
        lines.append("")

    # Always show the day-by-day stops
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
            sub_cat = stop.get("sub_category", "")
            
            cuisine = stop.get("cuisine_type", "")
            address = stop.get("address", "")
            maps_link = stop.get("maps_link", "")
            review_count = stop.get("review_count")
            price_level = stop.get("price_level")
            entry_fee = stop.get("entry_fee")
            hours = stop.get("hours") or stop.get("opening_hours", {})

            time_emoji = {"morning": "🌅", "afternoon": "☀️", "evening": "🌙"}.get(time_slot, "📍")
            time_label = time_slot.capitalize() if time_slot else ""

            parts = [f"  {time_emoji} {name}"]
            if time_label:
                parts.append(f"({time_label})")
            if duration:
                parts.append(f"{duration} min")
            lines.append(" • ".join(parts))

            detail_bits = []
            # Show sub_category first (more specific than category)
            label = sub_cat.title() if sub_cat else (cat.title() if cat else "")
            if label:
                detail_bits.append(label)
            if rating:
                rating_str = f"⭐ {rating}"
                if review_count:
                    rating_str += f" ({review_count:,} reviews)"
                detail_bits.append(rating_str)
            elif review_count:
                detail_bits.append(f"({review_count:,} reviews)")
            # Show cuisine type for restaurants
            if cuisine and cat == "restaurant":
                detail_bits.append(f"🍲 {cuisine}")

            if price_level:
                detail_bits.append(f"💰 {price_level}")
            if entry_fee:
                detail_bits.append(f"🎟 {entry_fee}")
            if detail_bits:
                sep = " · "
                lines.append(f"      {sep.join(detail_bits)}")

            # Extra details on their own lines
            if hours and isinstance(hours, dict):
                first_hour = next(iter(hours.values()), "")
                if first_hour:
                    lines.append(f"      🕐 {first_hour[:60]}")
            elif hours and isinstance(hours, str):
                lines.append(f"      🕐 {hours[:60]}")
            if address:
                lines.append(f"      📍 {address[:80]}")
            if maps_link:
                short_link = maps_link[:80] + "..." if len(maps_link) > 80 else maps_link
                lines.append(f"      🗺 {short_link}")
            if why:
                lines.append(f"      💡 {why}")

        lines.append("")        # Hotels section
    if hotels:
        lines.append("🏨 Where to Stay")
        for hotel in hotels:
            name = hotel.get("name", "Unknown")
            acc_type = hotel.get("accommodation_type", "")
            sub_cat = hotel.get("sub_category", "")
            rating = hotel.get("rating", 0)
            amenities = hotel.get("amenities", [])
            address = hotel.get("address", "")
            maps_link = hotel.get("maps_link", "")
            why = hotel.get("why_recommended", "")
            review_count = hotel.get("review_count")
            is_selected = selected_hotel and hotel.get("id") == selected_hotel.get("id")

            type_label = sub_cat.title() if sub_cat else (acc_type.capitalize() if acc_type else "")
            star_count = min(round(rating or 0), 5)
            stars_str = "⭐" * star_count if star_count > 0 else ""

            # Mark selected hotel with a checkmark
            prefix = "  ✅ " if is_selected else "  • "
            line = f"{prefix}{name}"
            if type_label:
                line += f" ({type_label})"
            if rating:
                line += f" {stars_str} {rating}"
            if review_count:
                line += f" ({review_count:,} reviews)"
            lines.append(line)

            if amenities:
                am_str = ", ".join(a.capitalize() for a in amenities[:6])
                if len(amenities) > 6:
                    am_str += f" +{len(amenities) - 6} more"
                lines.append(f"      🏷 {am_str}")
            if address:
                lines.append(f"      📍 {address[:60]}")
            if maps_link:
                short_link = maps_link[:70] + "..." if len(maps_link) > 70 else maps_link
                lines.append(f"      🗺 {short_link}")
            if why:
                lines.append(f"      💡 {why}")

    lines.append("")
    if not approved:
        lines.append("💡 You can ask me to modify any part of this itinerary, or say 'approve' to save it!")
    return "\n".join(lines)

@traced(name="modify_itinerary", tags=["conversation", "modify"], metadata={"component": "orchestrator"})

def _extract_adjustments_from_classification(classification: dict) -> dict:
    """Extract preference adjustment fields from the edit classification.

    When the classifier detected a preference edit (CHANGE_INTERESTS,
    CHANGE_BUDGET, CHANGE_PACE, CHANGE_PREFERENCES), it may have already
    populated the adjustment fields. Returns a dict in the same format as
    `interpret_preference_adjustment`, or an empty dict if no adjustments
    were found.
    """
    edit_type = (classification.get("edit_type") or "").upper()
    if edit_type not in ("CHANGE_INTERESTS", "CHANGE_BUDGET", "CHANGE_PACE", "CHANGE_PREFERENCES"):
        return {}

    adjustments: dict[str, Any] = {}

    interests_add = classification.get("interests_add")
    interests_remove = classification.get("interests_remove")
    if interests_add:
        adjustments["interests_add"] = interests_add
    if interests_remove:
        adjustments["interests_remove"] = interests_remove

    budget = classification.get("budget_level")
    if budget:
        adjustments["budget_level"] = budget

    style = classification.get("travel_style")
    if style:
        adjustments["travel_style"] = style

    pace = classification.get("pace")
    if pace:
        adjustments["pace"] = pace

    food_add = classification.get("food_preferences_add")
    food_remove = classification.get("food_preferences_remove")
    if food_add:
        adjustments["food_preferences_add"] = food_add
    if food_remove:
        adjustments["food_preferences_remove"] = food_remove

    rerank_reason = classification.get("rerank_reason")
    if rerank_reason:
        adjustments["rerank_reason"] = rerank_reason

    if adjustments:
        logger.info(
            "[EditClassifier] Using built-in adjustments: %s",
            adjustments,
        )

    return adjustments


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
    acc_type_change, star_class_change = _is_accommodation_type_change(effective_message) or (None, None)
    if acc_type_change and state.itinerary and state.slots.destination_city:
        logger.info(
            "[ConversationAgent] Intercepted accommodation type change: %s → '%s'",
            effective_message[:60], acc_type_change,
        )
        # Update slots with new accommodation preference
        _apply_accommodation_change(state.slots, acc_type_change, star_class=star_class_change)
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

    # ── Shared preference adjustment ─────────────────────────────────
    # The edit classifier already includes adjustment fields for preference
    # edits (interests_add/remove, budget_level, pace, etc.). Use those
    # directly to save one LLM call. Only call interpret_preference_adjustment
    # as a fallback when the classifier didn't supply them.
    if _might_need_preference_update(classification):
        adjustments = _extract_adjustments_from_classification(classification)
        if not adjustments:
            adjustments = await interpret_preference_adjustment(
                effective_message, current_preferences=preferences
            )
    else:
        adjustments = {}

    if need_db and db_reason == "preference_shift":
        if adjustments:
            try:
                reranked = await asyncio.wait_for(
                    _rerank_and_replan(
                        user_id=user_id,
                        state=state,
                        adjustments=adjustments,
                        effective_message=effective_message,
                        image_features=image_features,
                    ), timeout=35.0
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[RerankReplan] Timeout (35s) for rerank — falling back to modifier agent"
                )
                reranked = None
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
                try:
                    reranked = await asyncio.wait_for(
                        _rerank_and_replan(
                            user_id=user_id,
                            state=state,
                            adjustments=adjustments,
                            effective_message=effective_message,
                            image_features=image_features,
                        ), timeout=35.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "[RerankReplan] Timeout (35s) for rerank — falling back to modifier agent"
                    )
                    reranked = None
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

    # Modifier was unchanged — log transition
    logger.info(
        "[ConversationAgent] Modifier unchanged — trying preference re-ranking"
    )

    # Branch 3: fallback preference adjustment (only when adjustments exist)
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
            try:
                reranked = await asyncio.wait_for(
                    _rerank_and_replan(
                        user_id=user_id,
                        state=state,
                        adjustments=adjustments,
                        effective_message=effective_message,
                        image_features=image_features,
                    ), timeout=35.0
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "[RerankReplan] Timeout (35s) for rerank — falling back to modifier agent"
                )
                reranked = None
            if reranked:
                return _itinerary_response(
                    state,
                    reranked["itinerary"],
                    image_features,
                    agent_messages + reranked.get("agent_messages", []),
                    reranked.get("validation"),
                )

    logger.info(
        "[ConversationAgent] Preference re-ranking failed or no adjustments"
    )

    logger.info("[ConversationAgent] Falling back to full pipeline regeneration")
    return await _fallback_full_regeneration(
        user_id, state, effective_message, router_result, image_features, token,
        modifier_applied=False,
        accommodations_updated=False,
        agent_messages=agent_messages,
    )

async def _handle_select_hotel(
    state: ConversationState,
    effective_message: str,
    router_result,
    image_features: Optional[VisionFeatures],
) -> dict:
    """Handle user's hotel selection during HOTEL_SELECTION phase.

    The message interpreter extracts ``selected_hotel_name`` and/or
    ``selected_hotel_number`` from the user's message.  We match these
    against ``accommodation_suggestions`` to pick the chosen hotel,
    then finalize the itinerary and transition to COMPLETED.

    If the user instead requests a change of accommodation type
    (e.g. "provide resorts"), we intercept it here and re-run
    hotel selection with the updated preference.

    Pure star-class requests (e.g. "provide 4-star hotels" when hotels
    are already preferred) are also intercepted and re-run hotel selection
    with the updated star class without triggering a false type change.
    """
    # Check for star class change first
    # The message interpreter already extracts preferred_hotel_star_class
    # and merges it into state.slots.  Compare against the extracted value
    # from this turn to detect star class changes.
    extracted_star = router_result.extracted.get("preferred_hotel_star_class")
    current_star = state.slots.preferred_hotel_star_class
    star_class_changed = (
        extracted_star is not None
        and extracted_star != current_star
    )
    if star_class_changed:
        logger.info(
            "[SelectHotel] Star class change: %d -> %d re-running hotel selection",
            current_star, extracted_star,
        )
        state.slots.preferred_hotel_star_class = extracted_star
        return await _run_hotel_selection_and_present(
            state, effective_message, image_features,
            star_class_change=extracted_star,
        )

    # Check for accommodation type change
    acc_type_change, star_class_change = _is_accommodation_type_change(
        effective_message,
        current_preferences=state.slots.accommodation_preferences,
    ) or (None, None)
    if acc_type_change or star_class_change is not None:
        logger.info(
            "[SelectHotel] Accommodation type change '%s' intercepted re-running hotel selection",
            acc_type_change,
        )
        return await _run_hotel_selection_and_present(
            state, effective_message, image_features,
            acc_type_change=acc_type_change,
            star_class_change=star_class_change,
        )

    extracted = router_result.extracted
    extracted = router_result.extracted
    selected_name = extracted.get("selected_hotel_name", "")
    selected_number = extracted.get("selected_hotel_number")

    hotels = (state.itinerary or {}).get("accommodation_suggestions", [])
    chosen = None

    if selected_number is not None and 1 <= selected_number <= len(hotels):
        # User picked by number (e.g. "hotel 2")
        chosen = hotels[selected_number - 1]
        logger.info("[SelectHotel] User picked by number %d → %s", selected_number, chosen.get("name", "?"))
    elif selected_name:
        # User picked by name — try fuzzy match
        name_lower = selected_name.lower()
        for hotel in hotels:
            h_name = (hotel.get("name") or "").lower()
            if name_lower in h_name or h_name in name_lower:
                chosen = hotel
                logger.info("[SelectHotel] User picked by name '%s' → %s", selected_name, hotel.get("name", "?"))
                break

    if not chosen:
        # Fallback: try matching keywords from user's message in hotel names
        msg_lower = effective_message.lower()
        for hotel in hotels:
            h_name = (hotel.get("name") or "").lower()
            # Check if any word from the hotel name appears in the message
            name_words = set(h_name.split())
            msg_words = set(msg_lower.split())
            overlap = name_words & msg_words
            if len(overlap) >= 2:
                chosen = hotel
                logger.info("[SelectHotel] Fallback keyword match → %s", hotel.get("name", "?"))
                break

    if not chosen:
        # Last resort: pick the first hotel
        chosen = hotels[0] if hotels else None
        if chosen:
            logger.info("[SelectHotel] No match found — defaulting to first hotel: %s", chosen.get("name", "?"))

    if chosen:
        state.itinerary["selected_hotel"] = chosen

    # ── Transition to BOOKING phase — present booking choices ──────────
    state.transition_to(ConversationPhase.BOOKING)

    # Build a summary of everything that was selected
    hotel_name = chosen["name"] if chosen else "Selected hotel"
    flight_info = state.slots.selected_flight_offer
    flight_line = ""
    if flight_info:
        airline = flight_info.get("airline_name", flight_info.get("airline_code", "?"))
        fnum = flight_info.get("flight_number", "?")
        price = flight_info.get("total_price", 0)
        currency = flight_info.get("currency", "")
        flight_line = f"✈️ **Flight:** {airline} {fnum} — {price} {currency}\n"

    message = (
        f"✅ **Your trip is all set!**\n\n"
        f"🏨 **Hotel:** {hotel_name}\n"
        f"{flight_line}\n"
        f"📅 **Duration:** {state.slots.duration_days or '?'} days in {state.slots.destination_city or 'your destination'}\n\n"
        f"Would you like to proceed to payment now?\n\n"
        f"**1️⃣** 💳 Pay Now — Book everything and pay\n"
        f"**2️⃣** ⏸ Do it later — I'll book through the app"
    )

    # Build structured booking data for Flutter
    booking_data = _build_booking_data(state)

    return {
        "response_type": "booking",
        "message": message,
        "itinerary": state.itinerary,
        "image_features": image_features,
        "booking_data": booking_data,
        "agent_messages": [f"[HotelSelector] User chose: {hotel_name}"],
    }

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

    if state.slots.accommodation_preferences:
        result["accommodation_preferences"] = state.slots.accommodation_preferences

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

            # ── Fuse image features into the profile if available ─────────────
            vision_agent_msgs: list[str] = []
            if image_features and image_features.confidence != "low":
                from ai_engine.graph.state import TripProfile
                profile_obj = TripProfile(**profile)
                fused = fuse_image_with_profile(profile_obj, image_features)
                profile = dict(fused)
                logger.info(
                    "[RerankReplan] Fused image features into profile: "
                    "interests=%s, style=%s, pace=%s, budget=%s",
                    image_features.interests,
                    image_features.travel_style,
                    image_features.pace,
                    image_features.budget_level,
                )
                vision_agent_msgs.append(
                    f"[VisionFusion] Merged image signals: "
                    f"interests={image_features.interests}, "
                    f"style={image_features.travel_style}, "
                    f"pace={image_features.pace}"
                )

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
                "agent_messages": vision_agent_msgs,
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
            # Hotels are NOT selected during re-ranking — they are selected
            # after the user approves the itinerary to avoid wasting hotel
            # selections when the user makes multiple modifications.
            # Try validation with a short timeout so a slow validator
            # doesn't block the user, but a fast one still catches issues.
            try:
                rerank_state = await asyncio.wait_for(
                    validate_itinerary(rerank_state), timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("[RerankReplan] Validation timed out (10s) — proceeding without it")
            except Exception as exc:
                logger.warning("[RerankReplan] Validation error: %s — proceeding without it", exc)

            optimized = rerank_state.get("optimized_itinerary")
            if not optimized:
                logger.warning("[RerankReplan] No optimized itinerary after planning")
                return None

            logger.info("[RerankReplan] Success: %d days, %d total stops, valid=%s",
                        len(optimized.get("days", [])),
                        sum(len(d.get("stops", [])) for d in optimized.get("days", [])),
                        rerank_state.get("is_valid"))
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

        # ── Checkpoint: persist PLAN_GENERATION phase before pipeline starts ──
        #    Save the state to Redis so that if the server crashes during the
        #    long-running trip_graph.ainvoke() call, the plan_started_at and
        #    PLAN_GENERATION phase are not lost.  On reconnect, the timeout
        #    detection in _process_message_inner can reset SLOT_FILLING and
        #    inform the user, instead of rolling back to an older state.
        try:
            _checkpoint_mgr = await get_session_manager()
            if _checkpoint_mgr.is_connected:
                await _checkpoint_mgr.save(state)
        except Exception as _checkpoint_err:
            logger.warning(
                "[ConversationAgent] Failed to save pipeline checkpoint (non-fatal): %s",
                _checkpoint_err,
            )

        # Trip context is NOT appended to the user_message here because the
        # graph pipeline already receives `profile` (all preference data) and
        # `conversation_context` (conversation history).  Duplicating it in
        # user_message would send the same data 3×, wasting ~300 tokens.
        initial_state = {
            "user_id": user_id,
            "user_message": user_message,
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

        if state and optimized:
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
    
        "ui": {"actions": ["replace_itinerary_card"]},    }
