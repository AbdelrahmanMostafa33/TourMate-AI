# ai/vision/feature_extractor.py

# ── Feature Extractor — Types & Validates VLM Output ────────────────────────
#
# Takes the raw dict from image_analyzer.py and produces a clean,
# validated VisualFeatures TypedDict ready for downstream use.
#
# Responsibilities:
#   - Define the VisualFeatures type (mirrors BehavioralProfile pattern)
#   - Sanitize values against allowed enum sets
#   - Fill in safe defaults for missing or invalid fields
#   - Provide a helper to convert VisualFeatures → plain text (for LLM prompts)
#
# Call order:
#   image_analyzer.py  → raw dict from Groq
#   feature_extractor.py ← YOU ARE HERE
#   multimodal_fusion.py → merges into TripState
# ─────────────────────────────────────────────────────────────────────────────

from typing import TypedDict, List, Optional


# ── Allowed values for each categorical field ─────────────────────────────────
# If the VLM returns a value outside these sets, it is replaced with the default.

VALID_ENVIRONMENT_TYPES = {
    "beach", "mountains", "desert", "city",
    "forest", "countryside", "historical", "unknown",
}

VALID_TRAVEL_STYLES = {
    "adventure", "relaxing", "cultural", "luxury",
    "budget", "nature", "urban", "unknown",
}

VALID_ATMOSPHERES = {
    "vibrant", "calm", "romantic", "family-friendly", "spiritual", "unknown",
}

VALID_PACES = {"slow", "moderate", "fast"}

VALID_BUDGET_HINTS = {"budget", "moderate", "luxury"}

# Minimum confidence threshold below which features are considered unreliable.
# Used by multimodal_fusion.py to decide whether to apply visual enrichment.
CONFIDENCE_THRESHOLD = 0.4


class VisualFeatures(TypedDict):
    """
    Typed, validated representation of features extracted from a travel image.

    Produced by extract_features() from the raw dict returned by analyze_travel_image().
    Injected into TripState by multimodal_fusion.fuse_vision_into_state().
    """

    # ── Primary Scene Classification ─────────────────────────────────────────
    environment_type: str
    # Physical setting of the image (e.g., "beach", "city", "historical")

    travel_style: str
    # Implied travel preference (e.g., "adventure", "cultural", "relaxing")

    atmosphere: str
    # Mood/social vibe of the image (e.g., "romantic", "vibrant", "calm")

    # ── Planning Signals ─────────────────────────────────────────────────────
    pace: str
    # Implied trip pace: "slow" | "moderate" | "fast"

    budget_hint: str
    # Implied budget level: "budget" | "moderate" | "luxury"

    # ── Interest & Activity Suggestions ──────────────────────────────────────
    suggested_interests: List[str]
    # Keywords the planner agent can merge with profile interests
    # Example: ["history", "architecture", "photography"]

    suggested_activities: List[str]
    # Concrete activity ideas for the itinerary
    # Example: ["visit local museums", "take a walking tour of the old city"]

    # ── Quality Signal ────────────────────────────────────────────────────────
    confidence: float
    # 0.0–1.0. Below CONFIDENCE_THRESHOLD the features are treated as hints only.

    # ── Source Flag ───────────────────────────────────────────────────────────
    is_reliable: bool
    # True when confidence >= CONFIDENCE_THRESHOLD.
    # Downstream code uses this to decide how strongly to weight image features.


def extract_features(raw: dict) -> VisualFeatures:
    """
    Validate and normalize the raw dict from analyze_travel_image().

    Any value not in the allowed enum set is replaced with a safe default.
    Lists are deduplicated and clamped to a maximum of 6 items.

    Args:
        raw: The dict returned directly by analyze_travel_image().

    Returns:
        A fully populated VisualFeatures TypedDict.
    """

    # ── Validate categorical fields ───────────────────────────────────────────
    environment_type = raw.get("environment_type", "unknown")
    if environment_type not in VALID_ENVIRONMENT_TYPES:
        print(f"[FeatureExtractor] Unknown environment_type '{environment_type}' → 'unknown'")
        environment_type = "unknown"

    travel_style = raw.get("travel_style", "unknown")
    if travel_style not in VALID_TRAVEL_STYLES:
        print(f"[FeatureExtractor] Unknown travel_style '{travel_style}' → 'unknown'")
        travel_style = "unknown"

    atmosphere = raw.get("atmosphere", "unknown")
    if atmosphere not in VALID_ATMOSPHERES:
        print(f"[FeatureExtractor] Unknown atmosphere '{atmosphere}' → 'unknown'")
        atmosphere = "unknown"

    pace = raw.get("pace", "moderate")
    if pace not in VALID_PACES:
        print(f"[FeatureExtractor] Unknown pace '{pace}' → 'moderate'")
        pace = "moderate"

    budget_hint = raw.get("budget_hint", "moderate")
    if budget_hint not in VALID_BUDGET_HINTS:
        print(f"[FeatureExtractor] Unknown budget_hint '{budget_hint}' → 'moderate'")
        budget_hint = "moderate"

    # ── Validate list fields ──────────────────────────────────────────────────
    # Filter out non-strings, deduplicate, and cap at 6 items each.

    raw_interests = raw.get("suggested_interests", [])
    suggested_interests = list(dict.fromkeys(
        item.lower().strip()
        for item in raw_interests
        if isinstance(item, str) and item.strip()
    ))[:6]

    raw_activities = raw.get("suggested_activities", [])
    suggested_activities = list(dict.fromkeys(
        item.strip()
        for item in raw_activities
        if isinstance(item, str) and item.strip()
    ))[:4]

    # ── Validate confidence ───────────────────────────────────────────────────
    try:
        confidence = float(raw.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    is_reliable = confidence >= CONFIDENCE_THRESHOLD

    print(
        f"[FeatureExtractor] Extracted — "
        f"env={environment_type}, style={travel_style}, "
        f"atmosphere={atmosphere}, reliable={is_reliable}"
    )

    return VisualFeatures(
        environment_type=environment_type,
        travel_style=travel_style,
        atmosphere=atmosphere,
        pace=pace,
        budget_hint=budget_hint,
        suggested_interests=suggested_interests,
        suggested_activities=suggested_activities,
        confidence=confidence,
        is_reliable=is_reliable,
    )


def features_to_text(features: VisualFeatures) -> str:
    """
    Convert a VisualFeatures dict into a plain-text summary.

    Used to inject image context into LLM planner prompts,
    the same way profile_to_text() injects the behavioral profile.

    Args:
        features: The validated VisualFeatures from extract_features().

    Returns:
        A short human-readable string describing what the image suggests.
        Returns an empty string if features are unreliable.

    Example output:
        "Image suggests: historical environment, cultural travel style,
         calm atmosphere, slow pace, moderate budget.
         Interests hinted: history, architecture, photography.
         Activity ideas: visit local museums, explore the old city."
    """
    if not features.get("is_reliable"):
        return ""   # Don't pollute the prompt with low-confidence guesses

    lines = []

    lines.append(
        f"Image suggests: {features['environment_type']} environment, "
        f"{features['travel_style']} travel style, "
        f"{features['atmosphere']} atmosphere, "
        f"{features['pace']} pace, "
        f"{features['budget_hint']} budget."
    )

    if features.get("suggested_interests"):
        lines.append(
            f"Interests hinted: {', '.join(features['suggested_interests'])}."
        )

    if features.get("suggested_activities"):
        lines.append(
            f"Activity ideas: {', '.join(features['suggested_activities'])}."
        )

    return "\n".join(lines)