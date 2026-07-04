"""
Preference Reranker Agent — interprets vibe changes and adjusts preferences.

When the user says things like "more entertaining", "cheaper", "more cultural",
this agent:
1. Interprets the natural language request as preference adjustments
2. Returns updated preference fields (interests, budget, pace, style, etc.)
3. The caller uses these to re-rank the existing candidate places pool

This is Mode 1 of the itinerary editing system — faster than a full pipeline
re-run because it skips retrieval and uses the existing places pool.

Uses structured output (``with_structured_output``) to guarantee valid JSON
from the LLM, eliminating manual JSON parsing and the fallback retry loop.
"""

import logging
from typing import List, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from ai_engine.llm import invoke_with_fallback
from ai_engine.observability import traced

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

**Required (always include)**:
- `rerank_reason`: One sentence explaining why these changes match the request

**Optional adjustments** (include only what needs to change):
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
- Always provide a rerank_reason explaining why the changes make sense
- If the request doesn't imply any change, return rerank_reason alone set to
  "No changes needed — current preferences already match the request."
- Return ONLY valid JSON — no preamble, no markdown fences
"""


# ── Structured Output Schema (Pydantic) ─────────────────────────────────────

class PreferenceAdjustment(BaseModel):
    """
    Structured preference adjustments interpreted from a user's modification request.

    All fields are optional — only fields that need to change are populated.
    If no changes are needed, all fields remain None.  Uses ``model_dump(exclude_none=True)``
    to produce a compact dict matching the current caller expectations.
    """

    interests_add: Optional[List[str]] = Field(
        default=None,
        description="New interests to add (e.g. ['entertainment', 'nightlife'])",
    )
    interests_remove: Optional[List[str]] = Field(
        default=None,
        description="Interests to remove",
    )
    budget_level: Optional[str] = Field(
        default=None,
        description="Budget level: 'budget', 'moderate', or 'luxury'",
    )
    travel_style: Optional[str] = Field(
        default=None,
        description="Travel style: 'cultural', 'adventure', 'relaxation', 'romantic', 'family', or 'solo'",
    )
    pace: Optional[str] = Field(
        default=None,
        description="Pace: 'relaxed', 'moderate', or 'packed'",
    )
    food_preferences_add: Optional[List[str]] = Field(
        default=None,
        description="New food interests to add",
    )
    food_preferences_remove: Optional[List[str]] = Field(
        default=None,
        description="Food interests to remove",
    )
    accommodation_preferences_add: Optional[List[str]] = Field(
        default=None,
        description="New accommodation types to add",
    )
    accommodation_preferences_remove: Optional[List[str]] = Field(
        default=None,
        description="Accommodation types to remove",
    )
    special_focus: Optional[str] = Field(
        default=None,
        description="A short phrase describing the new focus",
    )
    rerank_reason: str = Field(
        description="One sentence explaining why these changes match the request",
    )


@traced(name="preference_reranker", tags=["agent", "reranker"], metadata={"role": "preference_reranker"})
async def interpret_preference_adjustment(
    modification_request: str,
    current_preferences: dict | None = None,
) -> dict:
    """
    Interpret a vibe-change request and return preference adjustments.

    Uses ``structured_output=PreferenceAdjustment`` to guarantee valid output
    from the LLM, replacing the previous manual JSON extraction + retry loop.

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

Determine the preference adjustments needed."""

    # Build LangChain messages.
    # SystemMessage = instructions
    # HumanMessage = actual request/context
    messages = [
        SystemMessage(content=PREFERENCE_INTERPRETER_PROMPT),
        HumanMessage(content=prompt),
    ]

    # Single LLM call with structured output — invoke_with_fallback handles
    # key rotation and retry on rate-limit / transient errors internally.
    # The Pydantic model guarantees valid output, eliminating the old
    # manual JSON extraction + 2-attempt retry loop.
    try:
        response: PreferenceAdjustment = await invoke_with_fallback(
            "preference_reranker",
            messages,
            structured_output=PreferenceAdjustment,
        )

        if response is None:
            logger.warning(
                "[PreferenceReranker] LLM returned None for '%s' — returning empty",
                modification_request[:50],
            )
            return {}

        # Convert to dict, dropping None fields to match caller expectations.
        # rerank_reason is now required, so it will always be present.
        result = response.model_dump(exclude_none=True)

        # Defensive: if rerank_reason is somehow missing (e.g. model quirk),
        # inject a fallback so the caller never sees an empty dict.
        if "rerank_reason" not in result:
            result["rerank_reason"] = "Preferences adjusted based on user request."

        logger.info(
            "[PreferenceReranker] Interpreted '%s' → %s",
            modification_request[:50],
            result.get("rerank_reason", "no reason given"),
        )

        return result

    except Exception as e:
        logger.warning(
            "[PreferenceReranker] LLM call failed for '%s': %s — returning empty",
            modification_request[:50],
            e,
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
        or "balanced"
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