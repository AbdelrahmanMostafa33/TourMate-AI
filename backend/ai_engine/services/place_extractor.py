"""
Place Name Extractor — extracts place names from modification requests.

This service uses a lightweight LLM call to extract place names from user
modification requests like "Add the Grand Egyptian Museum" or "Remove
the Pyramids of Giza". The extracted name is then used for exact database
matching before falling back to vector search.

This is the first step in the hybrid search pipeline:
1. Extract place name (LLM)
2. Try exact match (PostgreSQL)
3. Fall back to vector search (embeddings)

IMPORTANT: The LLM may not recognize unusual or non-English place names
(e.g. "Wa7wa7"). If the LLM detects an action but no place name, a
heuristic fallback strips the action verb and uses the remaining text as
the candidate place name.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage, HumanMessage
from ai_engine.llm import invoke_with_fallback

logger = logging.getLogger(__name__)


# ── Structured Output Schema ──────────────────────────────────────────────

class PlaceNameExtraction(BaseModel):
    """Structured output from place name extraction LLM."""

    place_names: list[str] = Field(
        default_factory=list,
        description="List of place names mentioned in the request (can be multiple for 'add X and Y')"
    )
    confidence: float = Field(
        default=0.0,
        description="Confidence score (0-1) that place names were actually mentioned"
    )
    action: Optional[str] = Field(
        default=None,
        description="The action being performed (add, remove, swap, etc.)"
    )

    @property
    def place_name(self) -> Optional[str]:
        """Legacy property for backward compatibility - returns first place name."""
        return self.place_names[0] if self.place_names else None



# ── System Prompt ───────────────────────────────────────────────────────────


EXTRACTOR_SYSTEM_PROMPT = """You are a place name extractor for TourMate AI.

Your task is to extract place names from user modification requests about travel itineraries.

Rules:
1. Extract ALL specific place names mentioned (e.g., ["Grand Egyptian Museum", "Pyramids of Giza"])
2. Do NOT include generic terms like "the", "a", "an" in the extracted names
3. If no specific places are mentioned, return empty place_names list and confidence as 0.0
4. Set confidence to 1.0 only when clear, specific place names are mentioned
5. Set confidence to 0.5 for vague references (e.g., "that museum we discussed")
6. Set confidence to 0.0 when no places are mentioned
7. Extract the action: add, remove, swap, change, replace, etc.
8. For requests like "add X and Y", return both X and Y in the place_names list

Examples:
- "Add the Grand Egyptian Museum" → place_names: ["Grand Egyptian Museum"], action: "add", confidence: 1.0
- "Add the Grand Egyptian Museum and Pyramids of Giza" → place_names: ["Grand Egyptian Museum", "Pyramids of Giza"], action: "add", confidence: 1.0
- "Remove the Pyramids" → place_names: ["Pyramids"], action: "remove", confidence: 0.8
- "Add a nice restaurant" → place_names: [], action: "add", confidence: 0.0
- "Swap the hotel" → place_names: [], action: "swap", confidence: 0.0
- "Change the Egyptian Museum to the Grand Egyptian Museum" → place_names: ["Grand Egyptian Museum"], action: "change", confidence: 1.0
"""


# ── Heuristic Fallback ─────────────────────────────────────────────────────


_ACTION_VERBS = (
    "add", "include", "insert",
    "remove", "delete", "exclude", "drop",
    "swap", "change", "replace", "exchange",
)
"""Action verbs that the heuristic looks for at the start of a request."""

_LEADING_ARTICLES = r'^(the|a|an|some)\s+'
"""Regex pattern to strip leading articles before extracting the place name."""

_GENERIC_WORDS = {
    "the", "a", "an", "some", "this", "that",
    "nice", "good", "great", "new", "old", "big", "small",
    "place", "spot", "area", "location",
    "restaurant", "hotel", "museum", "cafe", "shop", "store", "park", "bar", "club",
    "one", "two", "more", "another",
}
"""Words that are too generic to be a specific place name."""

_STOP_WORDS = {"to", "in", "at", "near", "for", "with", "from", "by", "on", "and", "or"}
"""Words that signal the end of a place name in a phrase (e.g. "add wa7wa7 to day 2")."""


def _heuristic_fallback(text: str, detected_action: str | None) -> tuple[list[str], float]:
    """
    Fallback extraction when the LLM couldn't identify place names.

    Strips the detected action verb from the message and returns the
    remaining text as candidate place names with moderate confidence.

    Handles trailing filler by trimming at stop words and splits on "and":
        "add wa7wa7 to the trip" → ["wa7wa7"]  (strips "to the trip")
        "add wa7wa7 and il nilo" → ["wa7wa7", "il nilo"]  (splits on "and")
        "add a nice restaurant" → []        (all words generic)

    Args:
        text: The raw modification request (e.g. "add wa7wa7").
        detected_action: The action the LLM identified (e.g. "add").

    Returns:
        ``(place_names, confidence)`` or ``([], 0.0)`` if the remainder
        looks like generic descriptions rather than specific places.
    """
    if not detected_action or not text:
        return [], 0.0

    text = text.strip()
    text_lower = text.lower()
    action_lower = detected_action.lower().strip()

    # The LLM already confirmed this is the action — it MUST start the text
    if not text_lower.startswith(action_lower):
        return [], 0.0

    remainder = text[len(action_lower):].strip()
    # Strip leading articles ("the", "a", "an", "some")
    remainder = re.sub(_LEADING_ARTICLES, '', remainder, flags=re.IGNORECASE).strip()

    if not remainder or len(remainder) < 2:
        return [], 0.0

    # Trim at first stop word to remove trailing filler (e.g. "to the trip")
    words = remainder.split()
    trimmed = []
    for w in words:
        if w.lower() in _STOP_WORDS:
            break
        trimmed.append(w)
    remainder = " ".join(trimmed)

    if not remainder or len(remainder) < 2:
        return [], 0.0

    # Split on "and" to handle multiple places
    # "wa7wa7 and il nilo" → ["wa7wa7", "il nilo"]
    # "wa7wa7 , il nilo" → ["wa7wa7", "il nilo"]
    parts = re.split(r'\s+and\s+|,\s*', remainder, flags=re.IGNORECASE)
    place_names = []
    for part in parts:
        part = part.strip()
        if len(part) < 2:
            continue

        # Check if ALL words are generic → likely a description, not a place name
        unique_words = set(part.lower().split())
        non_generic = unique_words - _GENERIC_WORDS
        if non_generic:
            place_names.append(part)

    if not place_names:
        return [], 0.0

    # Short phrases (≤3 words each) → likely specific place names
    # Longer phrases → could be descriptions, lower confidence
    max_words = max(len(p.split()) for p in place_names)
    confidence = 0.7 if max_words <= 3 else 0.5

    return place_names, confidence


# ── Main Extraction Function ────────────────────────────────────────────────


async def extract_place_name(modification_request: str) -> PlaceNameExtraction:
    """
    Extract place name from a modification request using LLM.

    Args:
        modification_request: User's modification request (e.g., "Add the Grand Egyptian Museum")

    Returns:
        PlaceNameExtraction with place_name, confidence, and action
    """
    if not modification_request:
        return PlaceNameExtraction(place_name=None, confidence=0.0, action=None)

    messages = [
        SystemMessage(content=EXTRACTOR_SYSTEM_PROMPT),
        HumanMessage(content=modification_request),
    ]

    try:
        result: Optional[PlaceNameExtraction] = await invoke_with_fallback(
            "extractor",
            messages,
            structured_output=PlaceNameExtraction,
        )

        if result is None:
            logger.warning("[PlaceExtractor] LLM returned None — using fallback")
            return PlaceNameExtraction(place_names=[], confidence=0.0, action=None)

        logger.info(
            "[PlaceExtractor] Extracted: place_names=%s, action='%s', confidence=%.2f",
            result.place_names,
            result.action,
            result.confidence,
        )

        # ── Heuristic fallback ───────────────────────────────────────────
        # If the LLM detected an action but couldn't identify place names
        # (e.g. unusual names like "Wa7wa7"), try stripping the action verb
        # and using the remainder as candidate place names.
        if not result.place_names and result.action is not None:
            heuristic_names, heuristic_confidence = _heuristic_fallback(
                modification_request, result.action
            )
            if heuristic_names:
                logger.info(
                    "[PlaceExtractor] Heuristic fallback: %s (confidence=%.2f)",
                    heuristic_names, heuristic_confidence,
                )
                return PlaceNameExtraction(
                    place_names=heuristic_names,
                    confidence=heuristic_confidence,
                    action=result.action,
                )

        return result

    except Exception as exc:
        logger.error("[PlaceExtractor] Extraction failed: %s", exc)
        return PlaceNameExtraction(place_names=[], confidence=0.0, action=None)


# ── Helper Functions ───────────────────────────────────────────────────────


def is_high_confidence_extraction(extraction: PlaceNameExtraction) -> bool:
    """Check if extraction has high confidence (>= 0.7) and at least one place name."""
    return extraction.confidence >= 0.7 and len(extraction.place_names) > 0


def is_add_action(extraction: PlaceNameExtraction) -> bool:
    """Check if the extracted action is an add operation."""
    if not extraction.action:
        return False
    return extraction.action.lower() in ("add", "include", "insert")


def is_remove_action(extraction: PlaceNameExtraction) -> bool:
    """Check if the extracted action is a remove operation."""
    if not extraction.action:
        return False
    return extraction.action.lower() in ("remove", "delete", "exclude")
