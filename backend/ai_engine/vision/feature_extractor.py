# backend/ai_engine/vision/feature_extractor.py
"""Validation layer for raw VLM (vision-language model) JSON output.

Takes the unvalidated dict from the LLM response and produces a clean
``VisionFeatures`` instance with guaranteed field types and safe defaults.
"""

from __future__ import annotations

from typing import Optional

from ai_engine.schemas.vision_schema import VisionFeatures

VALID_ENVIRONMENTS = {"urban", "nature", "beach", "desert", "mountain", "mixed"}
VALID_ACTIVITY_STYLES = {"relaxing", "adventurous", "cultural", "culinary", "mixed"}
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
    # --- environment_type ---
    env = raw.get("environment_type")
    environment_type: Optional[str] = env if env in VALID_ENVIRONMENTS else None

    # --- activity_style ---
    style = raw.get("activity_style")
    activity_style: Optional[str] = style if style in VALID_ACTIVITY_STYLES else None

    # --- vibe ---
    vibe_raw = raw.get("vibe")
    vibe: Optional[str] = str(vibe_raw).strip() if isinstance(vibe_raw, str) else None

    # --- inferred_interests ---
    raw_interests = raw.get("inferred_interests", [])
    if not isinstance(raw_interests, list):
        raw_interests = []
    # Keep only string items, strip whitespace, cap at 5
    inferred_interests = [
        str(i).strip().lower()
        for i in raw_interests
        if isinstance(i, str) and str(i).strip()
    ][:5]

    # --- confidence ---
    conf = raw.get("confidence", "low")
    confidence: str = conf if conf in VALID_CONFIDENCE else "low"

    return VisionFeatures(
        environment_type=environment_type,
        activity_style=activity_style,
        vibe=vibe,
        inferred_interests=inferred_interests,
        confidence=confidence,  # type: ignore[arg-type]
    )