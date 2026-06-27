# backend/ai_engine/vision/multimodal_fusion.py
"""Merges image-extracted travel preferences into the trip profile.

Called when the user uploads an image alongside (or instead of) a text message.
The enriched profile is stored in ``TripState`` so downstream agents see a
fuller picture of user intent.
"""

from __future__ import annotations

import logging

from ai_engine.graph.state import TripProfile
from ai_engine.observability import traced
from ai_engine.schemas.vision_schema import VisionFeatures

logger = logging.getLogger(__name__)


@traced(name="vision_fuse_image", tags=["vision", "fusion"], metadata={"component": "multimodal_fusion"})
def fuse_image_with_profile(
    profile: TripProfile,
    image_features: VisionFeatures,
) -> TripProfile:
    """Merge image-extracted travel features into the trip profile.

    Behaves as follows for each category of field:

    - **Scalar enums** (``travel_style``, ``pace``, ``budget_level``):
      overwrite the profile value *only* if the image provides a non-``None``
      value.  User-declared preferences take precedence over image signals.
    - **List fields** (``interests``, ``food_preferences``):
      union-merge into the existing list (no duplicates, case-insensitive).
    - **Extra fields** (``environment_type``, ``vibe``, ``confidence``):
      logged for observability; not stored in the profile.

    Args:
        profile:        The ``TripProfile`` loaded from ``TripState``.
        image_features: The validated ``VisionFeatures`` from
                        ``analyze_travel_image()``.

    Returns:
        An updated copy of the ``TripProfile`` with image signals merged in.
    """
    updated = dict(profile)

    # ── Scalar enums — only set if image provides a non-None value ──────
    _TRIP_PROFILE_FIELDS = {"travel_style", "pace", "budget_level"}
    for field in _TRIP_PROFILE_FIELDS:
        val = getattr(image_features, field, None)
        if val is not None:
            updated[field] = val

    # ── List fields — union merge (no duplicates) ────────────────────────
    _LIST_FIELDS = {"interests", "food_preferences"}
    for field in _LIST_FIELDS:
        new_items = getattr(image_features, field, [])
        if not new_items:
            continue
        existing: list = list(updated.get(field) or [])
        existing_lower = {i.lower() for i in existing}
        for item in new_items:
            if item.lower() not in existing_lower:
                existing.append(item)
                existing_lower.add(item.lower())
        updated[field] = existing

    if image_features.confidence in ("high", "medium"):
        logger.info(
            "[VisionFusion] Merged %d interests, %d food_prefs "
            "(confidence=%s, travel_style=%s, pace=%s, budget=%s, env=%s)",
            len(image_features.interests),
            len(image_features.food_preferences),
            image_features.confidence,
            image_features.travel_style,
            image_features.pace,
            image_features.budget_level,
            image_features.environment_type,
        )

    return TripProfile(**updated)