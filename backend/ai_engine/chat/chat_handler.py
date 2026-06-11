# backend/ai_engine/chat/chat_handler.py

from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from app.external.groq_client import get_fast_llm
from ai_engine.chat.intent_parser import parse_intent
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
) -> dict:
    """
    Main entry point for the TourMate AI chat system.

    Orchestrates the full Sprint 3 chat flow:
      1. Parse intent from user_message using Llama 3.1 8B.
      2. If an image was uploaded, extract travel features from it using
         Llama 4 Scout and merge them into the user profile.
      3. Route based on intent_type:
           - "plan_trip"          → invoke the full LangGraph pipeline
           - "needs_clarification"→ generate a clarifying question via Groq
           - "general_chat"       → answer conversationally via Groq

    Args:
        user_id:     Firebase UID identifying the user.
        user_message: Raw text input from the user (may be empty if image-only).
        image_bytes: Optional raw image bytes from Firebase Storage download
                     or direct multipart upload.
        token:       Optional Firebase auth token for authenticated API calls
                     (e.g. loading the real user profile from the backend).

    Returns:
        A dict with:
            - response_type: "itinerary" | "clarification" | "chat"
            - message:       str  (clarification question or general answer)
            - itinerary:     dict | None  (only set for plan_trip)
            - image_features: dict | None (only set when an image was uploaded)
    """

    # ── Step 1: Parse intent ─────────────────────────────────────────────────
    # Uses Llama 3.1 8B (get_fast_llm). Returns a structured dict.
    # If user_message is empty (image-only input), treat as general_chat
    # so the image features drive the response.
    effective_message = user_message.strip() if user_message else ""
    if not effective_message:
        effective_message = "I uploaded an image for my trip."

    intent = parse_intent(effective_message)
    intent_type = intent.get("intent_type", "general_chat")

    # ── Step 2: Process image if provided ───────────────────────────────────
    image_features = None
    if image_bytes:
        image_features = analyze_travel_image(image_bytes)

    # ── Step 3: Route based on intent ────────────────────────────────────────
    if intent_type == "plan_trip":
        return await _handle_plan_trip(user_id, effective_message, intent, image_features, token)

    elif intent_type == "needs_clarification":
        return await _handle_clarification(intent, image_features)

    else:  # general_chat
        return await _handle_general_chat(effective_message, image_features)


# ── Streaming entry point ────────────────────────────────────────────────────

async def handle_chat_stream(
    user_id: str,
    user_message: str,
    image_bytes: Optional[bytes] = None,
    token: Optional[str] = None,
):
    """
    Streaming variant of handle_chat — yields chunks for WebSocket delivery.

    Each yielded dict has one of these shapes:
        {"type": "text",   "content": str}   — a word/token to display
        {"type": "actions", "data": list}     — structured actions (e.g. CREATE_TRIP)
        {"type": "done",   "data": None}      — signals end of stream

    Args:
        user_id:      Firebase UID identifying the user.
        user_message: Raw text input from the user.
        image_bytes:  Optional raw image bytes.
        token:        Optional Firebase auth token.
    """
    # ── Step 1: Parse intent ─────────────────────────────────────────────────
    effective_message = user_message.strip() if user_message else ""
    if not effective_message:
        effective_message = "I uploaded an image for my trip."

    intent = parse_intent(effective_message)
    intent_type = intent.get("intent_type", "general_chat")

    # ── Step 2: Process image if provided ───────────────────────────────────
    image_features = None
    if image_bytes:
        image_features = analyze_travel_image(image_bytes)

    # ── Step 3: Route and stream ─────────────────────────────────────────────
    if intent_type == "plan_trip":
        async for chunk in _stream_plan_trip(
            user_id, effective_message, intent, image_features, token
        ):
            yield chunk

    elif intent_type == "needs_clarification":
        result = await _handle_clarification(intent, image_features)
        async for chunk in _stream_text(result["message"]):
            yield chunk

    else:  # general_chat
        result = await _handle_general_chat(effective_message, image_features)
        async for chunk in _stream_text(result["message"]):
            yield chunk

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


async def _stream_plan_trip(
    user_id: str,
    user_message: str,
    intent: dict,
    image_features: Optional[dict],
    token: Optional[str] = None,
):
    """
    Streaming variant for plan_trip intent.

    Currently yields the full itinerary response as a single text chunk
    because the LangGraph pipeline (Sprint 4 placeholder) returns a
    complete result. When real agent streaming is implemented in Sprint 4,
    this will yield token-by-token from the LLM.
    """
    result = await _handle_plan_trip(user_id, user_message, intent, image_features, token)

    # Stream the confirmation message word-by-word
    async for chunk in _stream_text(result["message"]):
        yield chunk

    # Yield the itinerary as structured actions
    if result.get("itinerary"):
        yield {"type": "actions", "data": [{"type": "CREATE_TRIP", "data": result["itinerary"]}]}


# ── Route handlers ────────────────────────────────────────────────────────────

async def _handle_plan_trip(
    user_id: str,
    user_message: str,
    intent: dict,
    image_features: Optional[dict],
    token: Optional[str] = None,
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


async def _handle_clarification(intent: dict, image_features: Optional[dict]) -> dict:
    """
    Generates a natural clarifying question using Llama 3.1 8B.

    Called when the user clearly wants a trip but hasn't given
    destination or duration. Task 3.7.
    """
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