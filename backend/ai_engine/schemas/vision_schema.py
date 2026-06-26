"""Pydantic models for vision / image-analysis features.

Fields are aligned with ``TripProfile`` (from ``ai_engine.graph.state``) so that
image-extracted preferences can be merged directly into the trip profile without
a separate mapping layer.

The fields that overlap with ``TripProfile`` are:

+---------------------------+------------------------------+
| VisionFeatures field      | TripProfile field            |
+---------------------------+------------------------------+
| interests                 | interests                    |
| travel_style              | travel_style                 |
| pace                      | pace                         |
| food_preferences          | food_preferences             |
| budget_level              | budget_level                 |
+---------------------------+------------------------------+

Extra vision-specific fields (``environment_type``, ``vibe``, ``confidence``)
are kept for logging, explainability, and optional future enrichment.
"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field


class VisionFeatures(BaseModel):
    """Structured travel preferences extracted from a user-uploaded image.

    Every field has a safe default so callers never need to handle ``None``
    or missing keys explicitly unless they choose to.
    """

    # ── TripProfile-aligned fields (directly mergeable) ──────────────────

    interests: list[str] = Field(
        default_factory=list,
        description="1–5 travel-interest keywords (e.g. history, food, hiking)",
    )
    travel_style: Optional[str] = Field(
        default=None,
        description="One of: romantic, adventure, family, business, solo, cultural, relaxation | null",
    )
    pace: Optional[str] = Field(
        default=None,
        description="One of: relaxed, moderate, packed | null",
    )
    food_preferences: list[str] = Field(
        default_factory=list,
        description="Cuisine / food-style preferences inferred from image",
    )
    budget_level: Optional[str] = Field(
        default=None,
        description="One of: budget, moderate, luxury | null",
    )

    # ── Vision-specific extras (logging / explainability) ────────────────

    environment_type: Optional[str] = Field(
        default=None,
        description="Depicted environment: urban, nature, beach, desert, mountain, mixed | null",
    )
    vibe: Optional[str] = Field(
        default=None,
        description="Short phrase describing the image atmosphere (max ~8 words)",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="How clearly the image signals travel preferences",
    )

    @property
    def has_signal(self) -> bool:
        """``True`` when confidence is at least ``medium`` and interests exist."""
        return self.confidence in ("high", "medium") and len(self.interests) > 0

    @classmethod
    def fallback(cls) -> "VisionFeatures":
        """Return a zero-signal instance (all defaults, confidence ``low``)."""
        return cls()
