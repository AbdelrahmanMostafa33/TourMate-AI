# backend/ai_engine/vision/multimodal_fusion.py
"""Merges image-extracted travel preferences into the trip profile.

Called when the user uploads an image alongside (or instead of) a text message.
The enriched profile is stored in ``TripState`` so downstream agents see a
fuller picture of user intent.
"""

from __future__ import annotations

import logging

from ai_engine.graph.state import TripProfile
from ai_engine.schemas.vision_schema import VisionFeatures

logger = logging.getLogger(__name__)


def fuse_image_with_profile(
    profile: TripProfile,
    image_features: VisionFeatures,
) -> TripProfile:
    """Merge image-extracted travel features into the trip profile.

    Behaviour:
    - ``inferred_interests`` are appended to ``profile["interests"]``
      (union, no duplicates).
    - ``environment_type`` and ``activity_style`` are currently logged
      for future use (dimension-score enrichment).

    Args:
        profile:        The ``TripProfile`` loaded from ``TripState``.
        image_features: The validated ``VisionFeatures`` from
                        ``analyze_travel_image()``.

    Returns:
        An updated copy of the ``TripProfile`` with image signals merged in.
    """
    updated = dict(profile)

    new_interests = image_features.inferred_interests

    # --- Merge interests (union, no duplicates) ---
    existing_interests: list = list(updated.get("interests") or [])
    existing_lower = {i.lower() for i in existing_interests}
    for interest in new_interests:
        if interest.lower() not in existing_lower:
            existing_interests.append(interest)
            existing_lower.add(interest.lower())
    updated["interests"] = existing_interests

    if image_features.confidence in ("high", "medium"):
        logger.info(
            "[VisionFusion] Merged %d interests (confidence=%s, env=%s, style=%s)",
            len(new_interests),
            image_features.confidence,
            image_features.environment_type,
            image_features.activity_style,
        )

    return TripProfile(**updated)