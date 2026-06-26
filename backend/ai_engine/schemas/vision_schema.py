"""Pydantic models for vision / image-analysis features.

Replaces the bare ``dict`` interface that the vision module previously used.
All image-analysis functions now return / accept ``VisionFeatures``, which
provides typed fields, validation, and a structured contract for downstream
consumers (orchestrator, profile fusion, etc.).
"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field


class VisionFeatures(BaseModel):
    """Structured travel preferences extracted from a user-uploaded image.

    Every field has a safe default so callers never need to handle ``None``
    or missing keys explicitly unless they choose to.
    """

    environment_type: Optional[str] = Field(
        default=None,
        description="Depicted environment: urban, nature, beach, desert, mountain, mixed",
    )
    activity_style: Optional[str] = Field(
        default=None,
        description="Inferred activity style: relaxing, adventurous, cultural, culinary, mixed",
    )
    vibe: Optional[str] = Field(
        default=None,
        description="Short phrase describing the image atmosphere (max ~8 words)",
    )
    inferred_interests: list[str] = Field(
        default_factory=list,
        description="1–5 travel-interest keywords inferred from the image",
    )
    confidence: Literal["high", "medium", "low"] = Field(
        default="low",
        description="How clearly the image signals travel preferences",
    )

    @property
    def has_signal(self) -> bool:
        """``True`` when confidence is at least ``medium`` and interests exist."""
        return self.confidence in ("high", "medium") and len(self.inferred_interests) > 0

    @classmethod
    def fallback(cls) -> "VisionFeatures":
        """Return a zero-signal instance (all defaults, confidence ``low``)."""
        return cls()
