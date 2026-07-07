"""
Edit Classifier Agent — routes itinerary modification requests to the correct workflow.

Classifies user edits before executing modifier / rerank / full-regeneration paths.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ai_engine.llm import invoke_with_fallback
from ai_engine.observability import traced

logger = logging.getLogger(__name__)

EditType = Literal[
    "REMOVE",
    "REORDER",
    "MOVE_DAY",
    "ADD_PLACE",
    "ADD_CATEGORY",
    "REPLACE_PLACE",
    # CHANGE_HOTEL removed — hotels are handled in the post-approval
    # HOTEL_SELECTION phase (like flights), independent of the modifier.
    "CHANGE_PREFERENCES",
    "CHANGE_BUDGET",
    "CHANGE_PACE",
    "CHANGE_INTERESTS",
    "RE_THEME",
    "REGENERATE",
    "UNKNOWN",
]


class EditClassification(BaseModel):
    """Structured classification of an itinerary edit request.

    For preference-change edit types (CHANGE_INTERESTS, CHANGE_BUDGET,
    CHANGE_PACE, CHANGE_PREFERENCES), the model SHOULD also populate
    the optional adjustment fields so the orchestrator can skip the
    separate ``interpret_preference_adjustment`` LLM call.
    """

    edit_type: EditType = Field(
        description=(
            "Primary edit type. Use REMOVE, REORDER, MOVE_DAY, ADD_PLACE, "
            "ADD_CATEGORY, REPLACE_PLACE, RE_THEME for surgical edits; "
            "CHANGE_PREFERENCES / CHANGE_BUDGET / CHANGE_PACE / CHANGE_INTERESTS "
            "for vibe or preference shifts; REGENERATE for major overhauls."
        )
    )
    target_day: Optional[int] = Field(
        default=None,
        description="1-based day number if the edit targets a specific day",
    )
    target_category: Optional[str] = Field(
        default=None,
        description="Category hint such as museum, restaurant, hotel, nightlife",
    )
    requested_count: int = Field(
        default=1,
        description="How many places the user wants to add or replace",
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Classifier confidence in this routing decision",
    )
    reasoning: str = Field(
        default="",
        description="One sentence explaining the classification",
    )

    # ── Preference adjustment fields (optional — only for preference edits) ──
    # When edit_type is CHANGE_INTERESTS / CHANGE_PREFERENCES / CHANGE_BUDGET /
    # CHANGE_PACE, the classifier SHOULD populate these fields so the orchestrator
    # can apply adjustments directly without a second LLM call.

    interests_add: Optional[list[str]] = Field(
        default=None,
        description="New interests to add (e.g. ['entertainment', 'nightlife', 'nature']). Only for preference edits.",
    )
    interests_remove: Optional[list[str]] = Field(
        default=None,
        description="Interests to remove (e.g. ['history', 'shopping']). Only for preference edits.",
    )
    budget_level: Optional[str] = Field(
        default=None,
        description="New budget level: 'budget', 'moderate', or 'luxury'. Only for budget edits.",
    )
    travel_style: Optional[str] = Field(
        default=None,
        description="New travel style: 'cultural', 'adventure', 'relaxation', 'romantic', 'family', 'solo'. Only for preference edits.",
    )
    pace: Optional[str] = Field(
        default=None,
        description="New pace: 'relaxed', 'moderate', or 'packed'. Only for pace edits.",
    )
    food_preferences_add: Optional[list[str]] = Field(
        default=None,
        description="New food interests to add. Only for preference edits.",
    )
    food_preferences_remove: Optional[list[str]] = Field(
        default=None,
        description="Food interests to remove. Only for preference edits.",
    )
    rerank_reason: Optional[str] = Field(
        default=None,
        description="One sentence explaining why the adjustment matches the user request. Only for preference edits.",
    )


EDIT_CLASSIFIER_PROMPT = """\
You are the Edit Classifier for TourMate AI. Classify the user's itinerary
modification request into exactly one edit type.

Edit types:
- REMOVE — delete a stop or place
- REORDER — change stop order within a day
- MOVE_DAY — move a stop to another day
- ADD_PLACE — insert a new stop from available options (use when the user names a SPECIFIC place)
- ADD_CATEGORY — add places of a specific TYPE (e.g. \"add museums\", \"add more churches\", \"add restaurants\")
  Use ADD_CATEGORY when the user asks for a category/type of place rather than a specific named place.
- REPLACE_PLACE — swap one stop for another (use EXCHANGE when both are already in the itinerary)
# CHANGE_HOTEL removed — hotels are handled in the post-approval
# HOTEL_SELECTION phase (like flights), independent of the modifier.
- RE_THEME — update a day's theme only
- CHANGE_BUDGET — make trip cheaper or more luxury
- CHANGE_PACE — faster/slower pace
- CHANGE_INTERESTS — shift focus (more cultural, adventure, food, etc.)
- CHANGE_PREFERENCES — general vibe change not covered above
- REGENERATE — major overhaul (new destination, dates, remove all X and rebuild)
- UNKNOWN — unclear request

Rules:
- Use ADD_PLACE when the user names a SPECIFIC place (e.g. \"add the Grand Egyptian Museum\")
- Use ADD_CATEGORY when the user asks for a TYPE of place (e.g. \"add museums\", \"add more restaurants\")
  — even if they say \"add a museum\" (not naming a specific one), use ADD_CATEGORY
- Prefer surgical types (REMOVE, ADD_PLACE, ADD_CATEGORY, REPLACE_PLACE) when possible
- Use REGENERATE only when the trip intent fundamentally changes
- Extract target_day when a day number is mentioned
- Extract target_category when a place type is mentioned (museum, restaurant, hotel, etc.)
- Set requested_count when the user asks for multiple additions

**When the edit type is CHANGE_INTERESTS, CHANGE_PREFERENCES, CHANGE_BUDGET, or
CHANGE_PACE, you MUST also populate the corresponding adjustment fields** so
that a separate LLM call can be avoided.  Examples:
- \"make it more nature instead of history\" → {
    edit_type: CHANGE_INTERESTS,
    interests_add: [\"nature\"],
    interests_remove: [\"history\"],
    rerank_reason: \"Adding nature and removing history to refocus the itinerary\"
  }
- \"more entertaining\" → {
    edit_type: CHANGE_INTERESTS,
    interests_add: [\"entertainment\", \"nightlife\"],
    rerank_reason: \"Adding entertainment and nightlife interests\"
  }
- \"cheaper\" → {
    edit_type: CHANGE_BUDGET,
    budget_level: \"budget\",
    rerank_reason: \"Lowering budget to budget level\"
  }
- \"faster pace\" → {
    edit_type: CHANGE_PACE,
    pace: \"packed\",
    rerank_reason: \"Increasing pace to packed\"
  }
- \"more cultural\" → {
    edit_type: CHANGE_PREFERENCES,
    interests_add: [\"history\", \"museums\", \"art\"],
    travel_style: \"cultural\",
    rerank_reason: \"Adding cultural interests and setting travel style to cultural\"
  }

For non-preference edit types (surgical, regenerate, unknown), leave the
adjustment fields unset (null) — they will be ignored.
"""


def _build_itinerary_summary(itinerary: dict | None) -> str:
    if not itinerary:
        return "(no itinerary)"
    lines = [f"Destination: {itinerary.get('destination', '?')}"]
    for day in itinerary.get("days", [])[:5]:
        stops = ", ".join(s.get("name", "?") for s in day.get("stops", [])[:4])
        lines.append(f"Day {day.get('day_number')}: {stops}")
    return "\n".join(lines)


@traced(name="edit_classifier", tags=["agent", "classifier"], metadata={"role": "edit_classifier"})
async def classify_edit(
    modification_request: str,
    itinerary: dict | None = None,
) -> dict:
    """Classify a modification request and return a plain dict for routing."""
    messages = [
        SystemMessage(content=EDIT_CLASSIFIER_PROMPT),
        HumanMessage(content=(
            f"Current itinerary:\n{_build_itinerary_summary(itinerary)}\n\n"
            f"User request: {modification_request}\n\n"
            "Classify this edit."
        )),
    ]

    try:
        result: EditClassification | None = await invoke_with_fallback(
            "router",
            messages,
            structured_output=EditClassification,
        )
        if result is None:
            return {"edit_type": "UNKNOWN", "reasoning": "classifier returned None"}

        data = result.model_dump(exclude_none=True)
        logger.info(
            "[EditClassifier] '%s' → %s (%s)",
            modification_request[:60],
            data.get("edit_type"),
            data.get("reasoning", "")[:80],
        )
        return data

    except Exception as exc:
        logger.warning("[EditClassifier] Failed: %s — defaulting to UNKNOWN", exc)
        return {"edit_type": "UNKNOWN", "reasoning": str(exc)}


def is_surgical_edit(classification: dict) -> bool:
    """True when the edit should go through the delta modifier first."""
    edit_type = (classification.get("edit_type") or "").upper()
    return edit_type in {
        "REMOVE",
        "REORDER",
        "MOVE_DAY",
        "ADD_PLACE",
        "ADD_CATEGORY",
        "REPLACE_PLACE",
        # CHANGE_HOTEL removed — hotels are handled separately.
        "RE_THEME",
        "UNKNOWN",
    }


def is_preference_edit(classification: dict) -> bool:
    edit_type = (classification.get("edit_type") or "").upper()
    return edit_type in {
        "CHANGE_PREFERENCES",
        "CHANGE_BUDGET",
        "CHANGE_PACE",
        "CHANGE_INTERESTS",
    }


def is_regenerate_edit(classification: dict) -> bool:
    return (classification.get("edit_type") or "").upper() == "REGENERATE"
