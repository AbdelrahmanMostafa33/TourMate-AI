# backend/ai_engine/vision/feature_extractor.py

from typing import Optional

VALID_ENVIRONMENTS = {"urban", "nature", "beach", "desert", "mountain", "mixed"}
VALID_ACTIVITY_STYLES = {"relaxing", "adventurous", "cultural", "culinary", "mixed"}
VALID_CONFIDENCE = {"high", "medium", "low"}


def extract_and_validate(raw: dict) -> dict:
    """
    Cleans and validates the raw dict returned by the VLM.

    Ensures all keys exist, types are correct, and enum values are valid.
    Any invalid or unexpected value is replaced with a safe default
    so downstream code never has to do defensive checks.

    Args:
        raw: The dict parsed from the VLM JSON response.

    Returns:
        A clean, validated feature dict with guaranteed structure:
            - environment_type: str | None
            - activity_style:   str | None
            - vibe:             str | None
            - inferred_interests: list[str]  (max 5 items, strings only)
            - confidence:       "high" | "medium" | "low"
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

    return {
        "environment_type": environment_type,
        "activity_style":   activity_style,
        "vibe":             vibe,
        "inferred_interests": inferred_interests,
        "confidence":       confidence,
    }