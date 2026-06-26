# backend/ai_engine/vision/feature_extractor.py
"""Validation layer for raw VLM (vision-language model) JSON output.

Takes the unvalidated dict from the LLM response and produces a clean
``VisionFeatures`` instance with guaranteed field types and safe defaults.
"""

from __future__ import annotations

from typing import Optional

from ai_engine.schemas.vision_schema import VisionFeatures

VALID_ENVIRONMENTS = {"urban", "nature", "beach", "desert", "mountain", "mixed"}
VALID_TRAVEL_STYLES = {"romantic", "adventure", "family", "business", "solo", "cultural", "relaxation"}
VALID_PACES = {"relaxed", "moderate", "packed"}
VALID_BUDGET = {"budget", "moderate", "luxury"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def extract_and_validate(raw: dict) -> VisionFeatures:
    """Validate and normalise the raw VLM response dict into a ``VisionFeatures``.

    Every key is type-checked and enum-constrained.  Invalid or missing values
    are replaced with safe defaults so downstream code never needs defensive
    null checks.

    Args:
        raw: The dict parsed from the VLM JSON response (may have missing/
             invalid keys).

    Returns:
        A validated ``VisionFeatures`` instance.
    """
    # --- interests (replaces old inferred_interests) ---
    raw_interests = raw.get("interests", [])
    if not isinstance(raw_interests, list):
        raw_interests = []
    interests = [
        str(i).strip().lower()
        for i in raw_interests
        if isinstance(i, str) and str(i).strip()
    ][:5]

    # --- travel_style ---
    ts = raw.get("travel_style")
    travel_style: Optional[str] = ts if ts in VALID_TRAVEL_STYLES else None

    # --- pace ---
    p = raw.get("pace")
    pace: Optional[str] = p if p in VALID_PACES else None

    # --- food_preferences ---
    raw_food = raw.get("food_preferences", [])
    if not isinstance(raw_food, list):
        raw_food = []
    food_preferences = [
        str(f).strip().lower()
        for f in raw_food
        if isinstance(f, str) and str(f).strip()
    ][:5]

    # --- budget_level ---
    bl = raw.get("budget_level")
    budget_level: Optional[str] = bl if bl in VALID_BUDGET else None

    # --- environment_type ---
    env = raw.get("environment_type")
    environment_type: Optional[str] = env if env in VALID_ENVIRONMENTS else None

    # --- vibe ---
    vibe_raw = raw.get("vibe")
    vibe: Optional[str] = str(vibe_raw).strip() if isinstance(vibe_raw, str) else None

    # --- confidence ---
    conf = raw.get("confidence", "low")
    confidence: str = conf if conf in VALID_CONFIDENCE else "low"

    return VisionFeatures(
        interests=interests,
        travel_style=travel_style,
        pace=pace,
        food_preferences=food_preferences,
        budget_level=budget_level,
        environment_type=environment_type,
        vibe=vibe,
        confidence=confidence,  # type: ignore[arg-type]
    )