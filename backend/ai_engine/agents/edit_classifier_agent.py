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
    "REPLACE_PLACE",
    "CHANGE_HOTEL",
    "CHANGE_PREFERENCES",
    "CHANGE_BUDGET",
    "CHANGE_PACE",
    "CHANGE_INTERESTS",
    "RE_THEME",
    "REGENERATE",
    "UNKNOWN",
]


class EditClassification(BaseModel):
    """Structured classification of an itinerary edit request."""

    edit_type: EditType = Field(
        description=(
            "Primary edit type. Use REMOVE, REORDER, MOVE_DAY, ADD_PLACE, "
            "REPLACE_PLACE, CHANGE_HOTEL, RE_THEME for surgical edits; "
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


EDIT_CLASSIFIER_PROMPT = """\
You are the Edit Classifier for TourMate AI. Classify the user's itinerary
modification request into exactly one edit type.

Edit types:
- REMOVE — delete a stop or place
- REORDER — change stop order within a day
- MOVE_DAY — move a stop to another day
- ADD_PLACE — insert a new stop from available options
- REPLACE_PLACE — swap one stop for another (use EXCHANGE when both are already in the itinerary)
- CHANGE_HOTEL — change accommodation suggestions
- RE_THEME — update a day's theme only
- CHANGE_BUDGET — make trip cheaper or more luxury
- CHANGE_PACE — faster/slower pace
- CHANGE_INTERESTS — shift focus (more cultural, adventure, food, etc.)
- CHANGE_PREFERENCES — general vibe change not covered above
- REGENERATE — major overhaul (new destination, dates, remove all X and rebuild)
- UNKNOWN — unclear request

Rules:
- Prefer surgical types (REMOVE, ADD_PLACE, REPLACE_PLACE) when the user names a place or day
- Use REGENERATE only when the trip intent fundamentally changes
- Extract target_day when a day number is mentioned
- Extract target_category when a place type is mentioned (museum, restaurant, hotel, etc.)
- Set requested_count when the user asks for multiple additions
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
        "REPLACE_PLACE",
        "CHANGE_HOTEL",
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
