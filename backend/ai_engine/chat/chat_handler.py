# backend/ai_engine/chat/chat_handler.py

"""Stateful chat handler with Redis-backed session management.

This module orchestrates the full conversational flow:
  1. Load or create a ConversationState from Redis
  2. Parse intent from the user message
  3. Update session state (phase transitions, slot filling)
  4. Route to the appropriate handler
  5. Save updated state back to Redis

The session manager ensures conversations survive WebSocket reconnections
and server restarts.
"""

from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from app.external.llm_client import get_fast_llm
from ai_engine.chat.intent_parser import parse_intent
from ai_engine.memory.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
)
from ai_engine.memory.redis_memory import get_session_manager
from ai_engine.graph.graph_builder import trip_graph
from ai_engine.vision.image_analyzer import analyze_travel_image
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile
from ai_engine.tools.profile_tool import load_behavioral_profile, load_mock_profile


# ── Prompts ───────────────────────────────────────────────────────────────────

_CLARIFICATION_SYSTEM_PROMPT = """
You are TourMate AI, a friendly and concise travel planning assistant.
The user wants to plan a trip but has not provided all the required information.
Missing fields: {missing_fields}

Generate exactly ONE friendly, natural-sounding question to ask the user for
the missing information. Do not list options. Do not use bullet points.
Keep it to one or two sentences maximum.
"""

_GENERAL_CHAT_SYSTEM_PROMPT = """
You are TourMate AI, a knowledgeable and friendly travel assistant.
Answer the user's travel-related question concisely and helpfully in 2-4 sentences.
If the question is completely unrelated to travel, gently redirect to travel topics.
Do not offer to generate an itinerary unless the user asks for one.
"""


# ── Main entry point ──────────────────────────────────────────────────────────

async def handle_chat(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Stateful entry point for the TourMate AI chat system.

    Orchestrates the full conversational flow with Redis-backed session:
      1. Load or create ConversationState from Redis.
      2. Parse intent from user_message using Llama 3.1 8B.
      3. Update session state (merge slots, transition phases).
      4. If an image was uploaded, extract travel features.
      5. Route based on intent_type + current phase:
           - GREETING + general_chat → greeting response
           - SLOT_FILLING + needs_clarification → clarifying question
           - SLOT_FILLING + plan_trip → plan generation
           - ITINERARY_REVIEW → handle modifications
           - general_chat → conversational answer
      6. Save updated state back to Redis.

    Args:
        user_id:      Firebase UID identifying the user.
        user_message:  Raw text input from the user.
        image_bytes:  Optional raw image bytes.
        token:        Optional Firebase auth token.
        session_id:   Optional specific session to resume.

    Returns:
        A dict with:
            - response_type: "itinerary" | "clarification" | "chat" | "greeting"
            - message:       str
            - itinerary:     dict | None
            - image_features: dict | None
            - session_id:   str (for client to track)
    """
    # ── Step 0: Load or create session ───────────────────────────────────────
    manager = await get_session_manager()
    state = await manager.resume_or_create(user_id, session_id)

    # ── Step 1: Parse intent ─────────────────────────────────────────────────
    effective_message = user_message.strip() if user_message else ""
    if not effective_message:
        effective_message = "I uploaded an image for my trip."

    intent = parse_intent(effective_message)
    intent_type = intent.get("intent_type", "general_chat")

    # ── Step 2: Update session state with parsed intent ──────────────────────
    # Merge extracted slots into the session (only overwrites non-None fields)
    state.slots.merge(intent)
    state.add_user_message(effective_message, metadata={"intent_type": intent_type})

    # ── Step 3: Process image if provided ───────────────────────────────────
    image_features = None
    if image_bytes:
        image_features = analyze_travel_image(image_bytes)

    # ── Step 4: Phase-aware routing ──────────────────────────────────────────
    # The response depends on both the intent AND the current conversation phase.
    response = None

    if state.phase == ConversationPhase.GREETING:
        # First message — if user wants a trip, jump to slot filling
        if intent_type == "plan_trip" or intent_type == "needs_clarification":
            state.transition_to(ConversationPhase.SLOT_FILLING)
            if state.slots.is_complete():
                # User gave everything in the first message
                state.transition_to(ConversationPhase.PLAN_GENERATION)
                response = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
            else:
                response = await _handle_clarification(intent, image_features, state)
        else:
            response = await _handle_general_chat(effective_message, image_features)

    elif state.phase == ConversationPhase.SLOT_FILLING:
        if intent_type == "plan_trip" and state.slots.is_complete():
            # All slots filled — generate plan
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            response = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
        elif intent_type == "plan_trip" and not state.slots.is_complete():
            # Wants a plan but missing info
            response = await _handle_clarification(intent, image_features, state)
        elif intent_type == "needs_clarification":
            response = await _handle_clarification(intent, image_features, state)
        else:
            response = await _handle_general_chat(effective_message, image_features)

    elif state.phase == ConversationPhase.ITINERARY_REVIEW:
        # User is reviewing the itinerary — handle modifications
        response = await _handle_itinerary_review(user_id, effective_message, intent, image_features, token, state)

    elif state.phase == ConversationPhase.PLAN_GENERATION:
        # Plan is being generated — acknowledge and wait
        response = {
            "response_type": "chat",
            "message": "I'm working on your personalized itinerary! It'll be ready shortly.",
            "itinerary": None,
            "image_features": None,
        }

    elif state.phase == ConversationPhase.COMPLETED:
        # Session completed — handle follow-up or new trip
        if intent_type == "plan_trip":
            state.reset_for_new_trip()
            state.slots.merge(intent)
            if state.slots.is_complete():
                state.transition_to(ConversationPhase.PLAN_GENERATION)
                response = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
            else:
                response = await _handle_clarification(intent, image_features, state)
        else:
            response = await _handle_general_chat(effective_message, image_features)

    else:
        # Fallback
        response = await _handle_general_chat(effective_message, image_features)

    # ── Step 5: Save session and return ──────────────────────────────────────
    # Store itinerary in session state if plan was generated
    if response and response.get("itinerary") and state:
        state.set_itinerary(response["itinerary"])

    # Add assistant response to history
    if response and response.get("message"):
        state.add_assistant_message(response["message"])

    await manager.save(state)

    # Include session_id in response for client tracking
    if response:
        response["session_id"] = state.session_id
        response["phase"] = state.phase.value

    return response


# ── Streaming entry point ────────────────────────────────────────────────────

async def handle_chat_stream(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """
    Streaming variant of handle_chat — yields chunks for WebSocket delivery.

    Uses the same stateful session management as handle_chat.
    Each yielded dict has one of these shapes:
        {"type": "text",   "content": str}   — a word/token to display
        {"type": "actions", "data": list}     — structured actions (e.g. CREATE_TRIP)
        {"type": "done",   "data": None}      — signals end of stream
        {"type": "session", "data": dict}     — session metadata (id, phase)

    Args:
        user_id:      Firebase UID identifying the user.
        user_message:  Raw text input from the user.
        image_bytes:  Optional raw image bytes.
        token:        Optional Firebase auth token.
        session_id:   Optional specific session to resume.
    """
    # ── Step 0: Load session ─────────────────────────────────────────────────
    manager = await get_session_manager()
    state = await manager.resume_or_create(user_id, session_id)

    # Emit session metadata so client can track it
    yield {"type": "session", "data": {"session_id": state.session_id, "phase": state.phase.value}}

    # ── Step 1: Parse intent ─────────────────────────────────────────────────
    effective_message = user_message.strip() if user_message else ""
    if not effective_message:
        effective_message = "I uploaded an image for my trip."

    intent = parse_intent(effective_message)
    intent_type = intent.get("intent_type", "general_chat")

    # ── Step 2: Update session state ─────────────────────────────────────────
    state.slots.merge(intent)
    state.add_user_message(effective_message, metadata={"intent_type": intent_type})

    # ── Step 3: Process image ────────────────────────────────────────────────
    image_features = None
    if image_bytes:
        image_features = analyze_travel_image(image_bytes)

    # ── Step 4: Phase-aware routing ──────────────────────────────────────────
    result = None

    if state.phase == ConversationPhase.GREETING:
        if intent_type in ("plan_trip", "needs_clarification"):
            state.transition_to(ConversationPhase.SLOT_FILLING)
            if state.slots.is_complete():
                state.transition_to(ConversationPhase.PLAN_GENERATION)
                result = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
            else:
                result = await _handle_clarification(intent, image_features, state)
        else:
            result = await _handle_general_chat(effective_message, image_features)

    elif state.phase == ConversationPhase.SLOT_FILLING:
        if intent_type == "plan_trip" and state.slots.is_complete():
            state.transition_to(ConversationPhase.PLAN_GENERATION)
            result = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
        elif intent_type == "plan_trip":
            result = await _handle_clarification(intent, image_features, state)
        elif intent_type == "needs_clarification":
            result = await _handle_clarification(intent, image_features, state)
        else:
            result = await _handle_general_chat(effective_message, image_features)

    elif state.phase == ConversationPhase.ITINERARY_REVIEW:
        result = await _handle_itinerary_review(user_id, effective_message, intent, image_features, token, state)

    elif state.phase == ConversationPhase.COMPLETED:
        if intent_type == "plan_trip":
            state.reset_for_new_trip()
            state.slots.merge(intent)
            if state.slots.is_complete():
                state.transition_to(ConversationPhase.PLAN_GENERATION)
                result = await _handle_plan_trip(user_id, effective_message, intent, image_features, token, state)
            else:
                result = await _handle_clarification(intent, image_features, state)
        else:
            result = await _handle_general_chat(effective_message, image_features)

    else:
        result = await _handle_general_chat(effective_message, image_features)

    # ── Step 5: Stream the response ──────────────────────────────────────────
    if result and result.get("message"):
        async for chunk in _stream_text(result["message"]):
            yield chunk

    if result and result.get("itinerary"):
        yield {"type": "actions", "data": [{"type": "CREATE_TRIP", "data": result["itinerary"]}]}

    # ── Step 6: Save session ─────────────────────────────────────────────────
    # Store itinerary in session state if generated
    if result and result.get("itinerary") and state:
        state.set_itinerary(result["itinerary"])

    if result and result.get("message"):
        state.add_assistant_message(result["message"])
    await manager.save(state)

    yield {"type": "done", "data": None}


async def _stream_text(text: str):
    """
    Yields a response string word-by-word to simulate streaming.

    Each yield produces a dict with type "text" and a single word
    (plus trailing space) so the WebSocket client can render a
    typewriter effect.
    """
    for word in text.split():
        yield {"type": "text", "content": word + " "}


# ── Route handlers ────────────────────────────────────────────────────────────

async def _handle_plan_trip(
    user_id: str,
    user_message: str,
    intent: dict,
    image_features: Optional[dict],
    token: Optional[str] = None,
    state: Optional[ConversationState] = None,
) -> dict:
    """
    Invokes the full LangGraph pipeline for itinerary generation.

    Loads the user profile via real HTTP call when a token is provided,
    falling back to mock profile for development. Merges image features
    if available, then runs trip_graph.invoke().

    All TripState keys must be supplied — LangGraph raises KeyError for
    any missing key, even optional ones. Defaults are set explicitly here.
    """
    # Load profile — real if token available, mock otherwise
    if token:
        try:
            profile = await load_behavioral_profile(user_id=user_id, token=token)
        except Exception as e:
            print(f"[ChatHandler] Failed to load real profile ({e}), falling back to mock")
            profile = load_mock_profile(user_id=user_id)
    else:
        profile = load_mock_profile(user_id=user_id)

    # Merge image features into profile if an image was uploaded
    if image_features and image_features.get("confidence") != "low":
        profile = fuse_image_with_profile(profile, image_features)

    # Build the complete initial TripState.
    # Every key in TripState TypedDict must be present.
    initial_state = {
        # ── Core request ──────────────────────────────────────
        "user_id":           user_id,
        "user_message":      user_message,

        # ── Profile (enriched with image features if any) ─────
        "profile":           profile,
        "token":             token,

        # ── Pipeline outputs (None until agents run) ──────────
        "draft_itinerary":     None,
        "optimized_itinerary": None,
        "is_valid":            None,

        # ── Control flow ──────────────────────────────────────
        "next_agent": None,
        "error":      None,

        # ── Intent fields (pre-parsed — passed through to graph state
        #    so downstream agents have access without re-parsing) ─
        "intent_type":         intent.get("intent_type", "plan_trip"),
        "destination_city":    intent.get("destination_city"),
        "destination_country": intent.get("destination_country"),
        "duration_days":       intent.get("duration_days"),
        "travel_dates":        intent.get("travel_dates"),
        "special_requests":    intent.get("special_requests"),
        "group_size":          intent.get("group_size"),
        "missing_fields":      intent.get("missing_fields", []),

        # ── Trace ─────────────────────────────────────────────
        "agent_messages": [],
    }

    result_state = await trip_graph.ainvoke(initial_state)

    return {
        "response_type": "itinerary",
        "message":       "Here's your personalized itinerary!",
        "itinerary":     result_state.get("optimized_itinerary"),
        "image_features": image_features,
    }


async def _handle_clarification(
    intent: dict,
    image_features: Optional[dict],
    state: Optional[ConversationState] = None,
) -> dict:
    """
    Generates a natural clarifying question using Llama 3.1 8B.

    Called when the user clearly wants a trip but hasn't given
    destination or duration. Uses session context when available
    to avoid asking for information already provided.
    """
    # Use session state to determine what's actually missing
    # (avoids re-asking for information the user already provided)
    if state and state.slots.missing_required():
        missing = state.slots.missing_required()
    else:
        missing = intent.get("missing_fields", [])

    missing_str = " and ".join(missing) if missing else "destination and duration"

    llm = get_fast_llm()
    messages = [
        SystemMessage(
            content=_CLARIFICATION_SYSTEM_PROMPT.format(missing_fields=missing_str)
        ),
        HumanMessage(content="Generate the clarifying question now."),
    ]

    try:
        response = llm.invoke(messages)
        question = response.content.strip()
    except Exception:
        # Hardcoded fallback so the chat never goes silent
        question = (
            "I'd love to help plan your trip! "
            "Could you tell me where you'd like to go and for how many days?"
        )

    return {
        "response_type":  "clarification",
        "message":        question,
        "itinerary":      None,
        "image_features": image_features,
    }


# ── Itinerary Review Handler ──────────────────────────────────────────────────

async def _handle_itinerary_review(
    user_id: str,
    user_message: str,
    intent: dict,
    image_features: Optional[dict],
    token: Optional[str] = None,
    state: Optional[ConversationState] = None,
) -> dict:
    """
    Handle user interactions during the itinerary review phase.

    The user can:
      1. Approve the itinerary → move to COMPLETED phase
      2. Request modifications → re-run the pipeline with updated constraints
      3. Ask questions about the itinerary → answer conversationally

    This handler detects the intent and routes accordingly.
    """
    # ── Detect approval intent ──────────────────────────────────────────────
    approval_keywords = ["approve", "looks good", "perfect", "great", "yes", "confirm", "save"]
    is_approval = any(kw in user_message.lower() for kw in approval_keywords)

    # ── Detect modification request ─────────────────────────────────────────
    modification_keywords = ["change", "replace", "swap", "remove", "add", "modify", "update", "different"]
    is_modification = any(kw in user_message.lower() for kw in modification_keywords)

    if is_approval and not is_modification:
        # User approved the itinerary
        if state:
            state.approve_itinerary(itinerary_id=None)  # Will be set when saved to DB

        return {
            "response_type": "chat",
            "message": "Awesome! Your itinerary is confirmed. Have an amazing trip! 🎉",
            "itinerary": state.itinerary if state else None,
            "image_features": None,
        }

    elif is_modification:
        # User wants to modify the itinerary — re-run pipeline with new constraints
        if state:
            state.transition_to(ConversationPhase.PLAN_GENERATION)

        # Merge the modification request as a special_requests update
        modified_intent = dict(intent)
        modified_intent["special_requests"] = (
            f"{state.slots.special_requests or ''} | Modification: {user_message}"
        ).strip(" | ")

        # Re-run the pipeline
        result = await _handle_plan_trip(
            user_id, user_message, modified_intent, image_features, token, state
        )

        if state and result.get("itinerary"):
            state.set_itinerary(result["itinerary"])

        return result

    else:
        # General question about the itinerary — answer conversationally
        # Include itinerary context in the response
        itinerary_summary = ""
        if state and state.itinerary:
            days = state.itinerary.get("days", [])
            itinerary_summary = f"\n\nCurrent itinerary: {len(days)} days planned."

        llm = get_fast_llm()
        messages = [
            SystemMessage(content=
                f"You are TourMate AI. The user is reviewing their itinerary.{itinerary_summary}\n"
                f"Answer their question concisely and helpfully."
            ),
            HumanMessage(content=user_message),
        ]

        try:
            response = llm.invoke(messages)
            answer = response.content.strip()
        except Exception:
            answer = (
                "I'm here to help with your itinerary! "
                "Feel free to ask any questions or request changes."
            )

        return {
            "response_type": "chat",
            "message": answer,
            "itinerary": state.itinerary if state else None,
            "image_features": None,
        }


async def _handle_general_chat(user_message: str, image_features: Optional[dict]) -> dict:
    """
    Answers travel questions conversationally using Llama 3.1 8B.

    Also handles image-only input where the user didn't type a trip request —
    acknowledges the image features in the response when confidence is high.
    """
    # Build an enriched message if image features are useful
    enriched_message = user_message
    if image_features and image_features.get("confidence") in ("high", "medium"):
        vibe = image_features.get("vibe", "")
        interests = ", ".join(image_features.get("inferred_interests", []))
        if vibe or interests:
            enriched_message = (
                f"{user_message}\n\n"
                f"[Context from uploaded image: vibe='{vibe}', "
                f"interests detected={interests}]"
            )

    llm = get_fast_llm()
    messages = [
        SystemMessage(content=_GENERAL_CHAT_SYSTEM_PROMPT),
        HumanMessage(content=enriched_message),
    ]

    try:
        response = llm.invoke(messages)
        answer = response.content.strip()
    except Exception:
        answer = (
            "I'm here to help with your travel plans! "
            "Feel free to ask me anything about destinations, tips, or itineraries."
        )

    return {
        "response_type":  "chat",
        "message":        answer,
        "itinerary":      None,
        "image_features": image_features,
    }