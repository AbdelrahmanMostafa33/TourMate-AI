# backend/ai_engine/vision/multimodal_fusion.py

from typing import Optional
from ai_engine.graph.state import BehavioralProfile


def fuse_image_with_profile(
    profile: BehavioralProfile,
    image_features: dict,
) -> BehavioralProfile:
    """
    Merges image-extracted travel features into the user's behavioral profile.

    Called in chat_handler.py when the user uploads an image alongside
    (or instead of) a text message. The enriched profile is then stored
    in TripState so the planning agent sees a fuller picture of user intent.

    Sprint 3 behaviour:
    - Appends inferred_interests to profile["interests"] (no duplicates).
    - Overwrites activity-style slider hint if image confidence is "high"
      and the profile slider is still at the default midpoint.
    - All other profile fields are left unchanged.

    Sprint 4+ can extend this to weight confidence scores, persist the
    enriched profile back to PostgreSQL, and handle multi-image sessions.

    Args:
        profile:        The BehavioralProfile loaded from TripState.
        image_features: The validated dict from image_analyzer.analyze_travel_image().

    Returns:
        An updated copy of the BehavioralProfile with image signals merged in.
    """
    # Work on a shallow copy so the original state is not mutated unexpectedly
    updated = dict(profile)

    confidence = image_features.get("confidence", "low")
    new_interests = image_features.get("inferred_interests", [])

    # --- Merge interests (union, no duplicates) ---
    existing_interests: list = list(updated.get("interests") or [])
    existing_lower = {i.lower() for i in existing_interests}
    for interest in new_interests:
        if interest.lower() not in existing_lower:
            existing_interests.append(interest)
            existing_lower.add(interest.lower())
    updated["interests"] = existing_interests

    # --- Optionally refine adventure_relaxing slider ---
    # Only overwrite if confidence is high and the current slider is unset
    # (None means quiz was skipped — image gives us a signal to start with)
    if confidence == "high":
        activity_style = image_features.get("activity_style")
        if activity_style and updated.get("adventure_relaxing") is None:
            # Map VLM activity style labels to approximate slider values
            style_to_slider = {
                "adventurous": 75,
                "relaxing":    25,
                "cultural":    55,
                "culinary":    50,
                "mixed":       50,
            }
            updated["adventure_relaxing"] = style_to_slider.get(activity_style)

    return BehavioralProfile(**updated)