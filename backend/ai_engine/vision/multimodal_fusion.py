# backend/ai_engine/vision/multimodal_fusion.py

from typing import Optional
from ai_engine.graph.state import TripProfile


def fuse_image_with_profile(
    profile: TripProfile,
    image_features: dict,
) -> TripProfile:
    """
    Merges image-extracted travel features into the trip profile.

    Called when the user uploads an image alongside a text message.
    The enriched profile is stored in TripState so downstream agents
    see a fuller picture of user intent.

    Behavior:
    - Appends inferred_interests to profile["interests"] (no duplicates).
    - If image confidence is "high", enriches adventure_score with
      activity_style signal.
    - Bumps confidence to reflect additional signal.

    Args:
        profile:        The TripProfile loaded from TripState.
        image_features: The validated dict from image_analyzer.analyze_travel_image().

    Returns:
        An updated copy of the TripProfile with image signals merged in.
    """
    updated = dict(profile)

    img_confidence = image_features.get("confidence", "low")
    new_interests = image_features.get("inferred_interests", [])

    # --- Merge interests (union, no duplicates) ---
    existing_interests: list = list(updated.get("interests") or [])
    existing_lower = {i.lower() for i in existing_interests}
    for interest in new_interests:
        if interest.lower() not in existing_lower:
            existing_interests.append(interest)
            existing_lower.add(interest.lower())
    updated["interests"] = existing_interests

    # --- Enrich adventure_score from image activity_style ---
    if img_confidence == "high":
        activity_style = image_features.get("activity_style")
        if activity_style:
            style_to_score = {
                "adventurous": 0.85,
                "relaxing":    0.25,
                "cultural":    0.55,
                "culinary":    0.50,
                "mixed":       0.50,
            }
            new_score = style_to_score.get(activity_style, 0.50)
            current = updated.get("adventure_score") or 0.50
            updated["adventure_score"] = round((current + new_score) / 2, 2)

    # --- Bump confidence ---
    current_conf = updated.get("confidence", 0.0) or 0.0
    if img_confidence == "high":
        updated["confidence"] = min(1.0, round(current_conf + 0.15, 2))

    return TripProfile(**updated)