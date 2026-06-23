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

    return TripProfile(**updated)