"""
Preference Reranker Agent — interprets vibe changes and adjusts preferences.

When the user says things like "more entertaining", "cheaper", "more cultural",
this agent:
1. Interprets the natural language request as preference adjustments
2. Returns updated preference fields (interests, budget, pace, style, etc.)
3. The caller uses these to re-rank the existing candidate places pool

This is Mode 1 of the itinerary editing system — faster than a full pipeline
re-run because it skips retrieval and uses the existing places pool.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm_config import invoke_with_fallback
from ai_engine.observability import traced
from ai_engine.utils.json_utils import extract_json_from_llm_output

# Create a logger instance for tracking execution, warnings, and errors
logger = logging.getLogger(__name__)


# ── Preference Interpreter Prompt ───────────────────────────────────────────

# System prompt used by the LLM.
# It teaches the model how to convert a user's modification request
# into structured preference changes that can later be applied to
# itinerary ranking.
PREFERENCE_INTERPRETER_PROMPT = """\
You are the Preference Reranker Agent for TourMate AI. You interpret a user's
modification request and determine how to adjust their travel preferences.

You receive:
1. **Current Preferences**: The user's current travel profile values
2. **Modification Request**: What the user wants to change (e.g. "more
   entertaining", "cheaper", "more cultural", "faster pace")

**Your job**: Determine what preference adjustments would make the new
itinerary reflect the user's request. Return a JSON object with ONLY the
fields that need to change.

**Available adjustments**:
- `interests_add`: List of new interests to add (e.g. ["entertainment",
  "nightlife", "shopping", "history", "nature", "food", "museums"])
- `interests_remove`: List of interests to remove
- `budget_level`: Change to "budget", "moderate", or "luxury"
- `travel_style`: Change to "cultural", "adventure", "relaxation",
  "romantic", "family", or "solo"
- `pace`: Change to "relaxed", "moderate", or "packed"
- `food_preferences_add`: New food interests to add
- `food_preferences_remove`: Food interests to remove
- `accommodation_preferences_add`: New accommodation types to add
- `accommodation_preferences_remove`: Accommodation types to remove
- `special_focus`: A short phrase describing the new focus
- `rerank_reason`: One sentence explaining why these changes match the request

**Examples**:
- "more entertaining" → {"interests_add": ["entertainment", "nightlife"],
  "special_focus": "evening entertainment and shows",
  "rerank_reason": "Adding entertainment and nightlife interests boosts venues
   like cinemas, opera houses, and night spots in the ranking"}
- "cheaper" → {"budget_level": "budget",
  "rerank_reason": "Budget level filters expensive restaurants and hotels"}
- "more cultural" → {"interests_add": ["history", "museums", "art"],
  "travel_style": "cultural",
  "rerank_reason": "Cultural interests boost museums and historic sites"}
- "faster pace" → {"pace": "packed",
  "rerank_reason": "Packed pace encourages more stops per day"}
- "suggest resorts instead of hotels" → {
  "accommodation_preferences_add": ["resort"],
  "accommodation_preferences_remove": ["hotel"],
  "rerank_reason": "User wants resort-style accommodation instead of standard hotels"}
- "switch to hostels" → {
  "accommodation_preferences_add": ["hostel"],
  "accommodation_preferences_remove": ["hotel"],
  "rerank_reason": "User wants budget-friendly hostel accommodation"}

**Rules**:
- Only include fields that actually need to change
- If the request doesn't imply any change, return an empty object {}
- Return ONLY valid JSON — no preamble, no markdown fences
"""


@traced(name="preference_reranker", tags=["agent", "reranker"], metadata={"role": "preference_reranker"})
async def interpret_preference_adjustment(
    modification_request: str,
    current_preferences: dict | None = None,
) -> dict:
    """
    Interpret a vibe-change request and return preference adjustments.

    Args:
        modification_request: The user's request (e.g. "more entertaining")
        current_preferences: Optional dict with current preferences for context

    Returns:
        Dict with adjustment fields (interests_add, budget_level, pace, etc.)
        or empty dict if no changes needed.
    """

    # Human-readable summary of the user's current preferences.
    # This is included in the prompt to help the LLM understand
    # what should be changed relative to the current state.
    current_text = ""

    if current_preferences:
        parts = []

        # Collect important preference fields and format them
        # into text for the prompt.
        for key in (
            "budget_level",
            "travel_style",
            "pace",
            "interests",
            "food_preferences",
            "accommodation_preferences",
        ):
            val = current_preferences.get(key)

            if val:
                if isinstance(val, list):
                    parts.append(f"{key}: {', '.join(val)}")
                else:
                    parts.append(f"{key}: {val}")

        # Build final context block if any preferences exist
        if parts:
            current_text = "Current preferences:\n" + "\n".join(parts)

    # User-specific prompt sent to the LLM.
    # Combines the modification request with existing preferences.
    prompt = f"""\
Modification Request: {modification_request}

{current_text}

Determine the preference adjustments needed and return them as JSON."""

    # Build LangChain messages.
    # SystemMessage = instructions
    # HumanMessage = actual request/context
    messages = [
        SystemMessage(content=PREFERENCE_INTERPRETER_PROMPT),
        HumanMessage(content=prompt),
    ]

    # Retry configuration in case the model returns invalid JSON
    max_attempts = 2
    last_error = None

    # Retry loop
    for attempt in range(1, max_attempts + 1):
        try:
            # Copy original messages so retries don't mutate them
            attempt_messages = list(messages)

            # If previous attempt failed, tell the model why and
            # explicitly request valid JSON.
            if attempt > 1 and last_error:
                retry_note = (
                    f"\n\nYour previous output was invalid: {last_error}. "
                    f"Return ONLY a valid JSON object."
                )
                attempt_messages.append(HumanMessage(content=retry_note))

            # Call the LLM using the configured fallback mechanism
            response = await invoke_with_fallback(
                "preference_reranker",
                attempt_messages
            )

            # Extract JSON from the model response
            extracted = extract_json_from_llm_output(response.content)

            # Parse JSON into a Python dictionary
            result = json.loads(extracted)

            # Log successful interpretation
            logger.info(
                "[PreferenceReranker] Interpreted '%s' → %s",
                modification_request[:50],
                result.get("rerank_reason", "no reason given"),
            )

            return result

        except Exception as e:
            # Save error for retry attempt
            last_error = str(e)

            logger.warning(
                "[PreferenceReranker] Attempt %d/%d failed: %s",
                attempt,
                max_attempts,
                last_error,
            )

    # All retries failed
    logger.warning(
        "[PreferenceReranker] All attempts failed for '%s'",
        modification_request[:50],
    )

    # Return empty adjustments instead of crashing
    return {}


def apply_preference_adjustments(
    slots,
    adjustments: dict,
) -> dict:
    """
    Apply the preference adjustments to the current trip slots / preferences.

    Args:
        slots: The current TripSlots object (or any dict with interest/food lists)
        adjustments: Dict from interpret_preference_adjustment()

    Returns:
        Dict with updated preferences that can be passed to the ranking agent
        as ``extracted_preferences``.
    """

    # Copy current preference lists so we can modify them safely
    # without mutating the original TripSlots object.
    current_interests = list(getattr(slots, "interests", None) or [])
    current_food = list(getattr(slots, "food_preferences", None) or [])
    current_accommodation = list(
        getattr(slots, "accommodation_preferences", None) or []
    )

    # ── Apply Additions ─────────────────────────────────────────────

    # Add new interests if not already present
    for add in (adjustments.get("interests_add") or []):
        if add not in current_interests:
            current_interests.append(add)

    # Add new food preferences if not already present
    for add in (adjustments.get("food_preferences_add") or []):
        if add not in current_food:
            current_food.append(add)

    # Add new accommodation preferences if not already present
    for add in (adjustments.get("accommodation_preferences_add") or []):
        if add not in current_accommodation:
            current_accommodation.append(add)

    # ── Apply Removals ──────────────────────────────────────────────

    # Remove interests requested by the user
    for rem in (adjustments.get("interests_remove") or []):
        if rem in current_interests:
            current_interests.remove(rem)

    # Remove food preferences requested by the user
    for rem in (adjustments.get("food_preferences_remove") or []):
        if rem in current_food:
            current_food.remove(rem)

    # Remove accommodation preferences requested by the user
    for rem in (adjustments.get("accommodation_preferences_remove") or []):
        if rem in current_accommodation:
            current_accommodation.remove(rem)

    # ── Resolve Final Scalar Preferences ────────────────────────────

    # Use adjustment values if provided.
    # Otherwise fall back to existing slot values.
    # If neither exists, use sensible defaults.
    budget = (
        adjustments.get("budget_level")
        or getattr(slots, "budget_level", None)
        or "moderate"
    )

    style = (
        adjustments.get("travel_style")
        or getattr(slots, "travel_style", None)
        or "cultural"
    )

    pace = (
        adjustments.get("pace")
        or getattr(slots, "pace", None)
        or "moderate"
    )

    # Build the final preference profile expected by the ranking agent.
    # This output can be passed directly as extracted_preferences.
    return {
        "budget_level": budget,
        "travel_style": style,
        "pace": pace,
        "interests": current_interests,
        "food_preferences": current_food,
        "accommodation_preferences": current_accommodation,
        "special_focus": adjustments.get("special_focus"),
    }