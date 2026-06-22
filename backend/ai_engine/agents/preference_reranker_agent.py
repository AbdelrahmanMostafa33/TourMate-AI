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
from ai_engine.utils.json_utils import extract_json_from_llm_output

logger = logging.getLogger(__name__)


# ── Preference Interpreter Prompt ───────────────────────────────────────────

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

**Rules**:
- Only include fields that actually need to change
- If the request doesn't imply any change, return an empty object {}
- Return ONLY valid JSON — no preamble, no markdown fences
"""


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
    current_text = ""
    if current_preferences:
        parts = []
        for key in ("budget_level", "travel_style", "pace", "interests",
                     "food_preferences", "accommodation_preferences"):
            val = current_preferences.get(key)
            if val:
                if isinstance(val, list):
                    parts.append(f"{key}: {', '.join(val)}")
                else:
                    parts.append(f"{key}: {val}")
        if parts:
            current_text = "Current preferences:\n" + "\n".join(parts)

    prompt = f"""\
Modification Request: {modification_request}

{current_text}

Determine the preference adjustments needed and return them as JSON."""

    messages = [
        SystemMessage(content=PREFERENCE_INTERPRETER_PROMPT),
        HumanMessage(content=prompt),
    ]

    max_attempts = 2
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            attempt_messages = list(messages)
            if attempt > 1 and last_error:
                retry_note = (
                    f"\n\nYour previous output was invalid: {last_error}. "
                    f"Return ONLY a valid JSON object."
                )
                attempt_messages.append(HumanMessage(content=retry_note))

            response = await invoke_with_fallback("preference", attempt_messages)
            extracted = extract_json_from_llm_output(response.content)
            result = json.loads(extracted)
            logger.info(
                "[PreferenceReranker] Interpreted '%s' → %s",
                modification_request[:50],
                result.get("rerank_reason", "no reason given"),
            )
            return result

        except Exception as e:
            last_error = str(e)
            logger.warning(
                "[PreferenceReranker] Attempt %d/%d failed: %s",
                attempt, max_attempts, last_error,
            )

    logger.warning(
        "[PreferenceReranker] All attempts failed for '%s'",
        modification_request[:50],
    )
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
    # Build current list values
    current_interests = list(getattr(slots, "interests", None) or [])
    current_food = list(getattr(slots, "food_preferences", None) or [])
    current_accommodation = list(getattr(slots, "accommodation_preferences", None) or [])

    # Apply additions
    for add in (adjustments.get("interests_add") or []):
        if add not in current_interests:
            current_interests.append(add)
    for add in (adjustments.get("food_preferences_add") or []):
        if add not in current_food:
            current_food.append(add)
    for add in (adjustments.get("accommodation_preferences_add") or []):
        if add not in current_accommodation:
            current_accommodation.append(add)

    # Apply removals
    for rem in (adjustments.get("interests_remove") or []):
        if rem in current_interests:
            current_interests.remove(rem)
    for rem in (adjustments.get("food_preferences_remove") or []):
        if rem in current_food:
            current_food.remove(rem)
    for rem in (adjustments.get("accommodation_preferences_remove") or []):
        if rem in current_accommodation:
            current_accommodation.remove(rem)

    # Build the extracted_preferences dict expected by the ranking agent
    budget = adjustments.get("budget_level") or getattr(slots, "budget_level", None) or "moderate"
    style = adjustments.get("travel_style") or getattr(slots, "travel_style", None) or "cultural"
    pace = adjustments.get("pace") or getattr(slots, "pace", None) or "moderate"

    return {
        "budget_level": budget,
        "travel_style": style,
        "pace": pace,
        "interests_from_conversation": current_interests,
        "food_preferences": current_food,
        "accommodation_style": current_accommodation[0] if current_accommodation else "hotel",
        "accommodation_preferences": current_accommodation,
        "special_focus": adjustments.get("special_focus"),
    }
