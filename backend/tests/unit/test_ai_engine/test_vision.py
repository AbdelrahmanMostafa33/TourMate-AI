# backend/tests/unit/test_ai_engine/test_vision.py
"""Unit tests for the restructured vision module.

All tests use the new async ``analyze_travel_image`` API, the
``VisionFeatures`` Pydantic model, and mock ``invoke_with_fallback``
instead of the old ``analyze_image`` from ``app.external.llm_client``.
"""

from __future__ import annotations

import json

import pytest
from unittest.mock import AsyncMock, patch

from ai_engine.vision.image_analyzer import analyze_travel_image
from ai_engine.vision.feature_extractor import extract_and_validate
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile
from ai_engine.schemas.vision_schema import VisionFeatures
from ai_engine.tools.profile_tool import load_mock_profile


VALID_VLM_RESPONSE = json.dumps({
    "environment_type": "urban",
    "travel_style":     "cultural",
    "pace":             "moderate",
    "vibe":             "busy historic bazaar",
    "interests": ["history", "food", "architecture"],
    "food_preferences": ["street food"],
    "budget_level":     "moderate",
    "confidence": "high",
})

FENCED_VLM_RESPONSE = f"```json\n{VALID_VLM_RESPONSE}\n```"


# ── image_analyzer tests ──────────────────────────────────────────────────────

class TestAnalyzeTravelImage:
    """``analyze_travel_image`` is now async and returns ``VisionFeatures``."""

    @pytest.mark.asyncio
    @patch("ai_engine.vision.image_analyzer.invoke_with_fallback")
    async def test_valid_response_returns_vision_features(self, mock_invoke):
        mock_invoke.return_value = AsyncMock(content=VALID_VLM_RESPONSE)
        result: VisionFeatures = await analyze_travel_image(b"fake_image_bytes")

        assert result.environment_type == "urban"
        assert result.travel_style == "cultural"
        assert "history" in result.interests
        assert result.confidence == "high"

    @pytest.mark.asyncio
    @patch("ai_engine.vision.image_analyzer.invoke_with_fallback")
    async def test_strips_markdown_fences(self, mock_invoke):
        mock_invoke.return_value = AsyncMock(content=FENCED_VLM_RESPONSE)
        result = await analyze_travel_image(b"fake_image_bytes")
        assert result.confidence in ("high", "medium", "low")

    @pytest.mark.asyncio
    @patch("ai_engine.vision.image_analyzer.invoke_with_fallback")
    async def test_malformed_json_returns_fallback(self, mock_invoke):
        mock_invoke.return_value = AsyncMock(content="this is not json at all")
        result = await analyze_travel_image(b"fake_image_bytes")

        assert result.confidence == "low"
        assert result.interests == []
        assert result.environment_type is None

    @pytest.mark.asyncio
    @patch("ai_engine.vision.image_analyzer.invoke_with_fallback")
    async def test_api_exception_returns_fallback(self, mock_invoke):
        mock_invoke.side_effect = Exception("Gemini API unavailable")
        result = await analyze_travel_image(b"fake_image_bytes")

        assert result.confidence == "low"
        assert result.interests == []

    @pytest.mark.asyncio
    @patch("ai_engine.vision.image_analyzer.invoke_with_fallback")
    async def test_result_is_vision_features_instance(self, mock_invoke):
        mock_invoke.return_value = AsyncMock(content=VALID_VLM_RESPONSE)
        result = await analyze_travel_image(b"fake_image_bytes")

        assert isinstance(result, VisionFeatures)
        assert result.environment_type is not None
        assert len(result.interests) == 3
        assert result.confidence == "high"


# ── feature_extractor tests ───────────────────────────────────────────────────

class TestExtractAndValidate:
    """``extract_and_validate`` now returns ``VisionFeatures``."""

    def test_valid_dict_passes_through(self):
        raw = {
            "environment_type": "beach",
            "travel_style":     "relaxation",
            "pace":             "relaxed",
            "vibe":             "sunny coastline",
            "interests": ["beaches", "swimming"],
            "food_preferences": ["seafood"],
            "budget_level":     "moderate",
            "confidence": "high",
        }
        result = extract_and_validate(raw)
        assert isinstance(result, VisionFeatures)
        assert result.environment_type == "beach"
        assert result.travel_style == "relaxation"
        assert result.pace == "relaxed"
        assert "beaches" in result.interests
        assert "seafood" in result.food_preferences
        assert result.budget_level == "moderate"
        assert result.confidence == "high"

    def test_invalid_environment_becomes_none(self):
        raw = {"environment_type": "INVALID", "travel_style": "INVALID",
               "pace": "INVALID", "budget_level": "INVALID",
               "vibe": None, "interests": [], "food_preferences": [],
               "confidence": "low"}
        result = extract_and_validate(raw)
        assert result.environment_type is None
        assert result.travel_style is None
        assert result.pace is None
        assert result.budget_level is None

    def test_interests_capped_at_five(self):
        raw = {
            "environment_type": None, "travel_style": None,
            "pace": None, "budget_level": None,
            "vibe": None,
            "interests": ["a", "b", "c", "d", "e", "f", "g"],
            "food_preferences": [],
            "confidence": "medium",
        }
        result = extract_and_validate(raw)
        assert len(result.interests) == 5

    def test_non_list_interests_becomes_empty(self):
        raw = {
            "environment_type": None, "travel_style": None,
            "pace": None, "budget_level": None,
            "vibe": None,
            "interests": "history",   # string instead of list
            "food_preferences": [],
            "confidence": "low",
        }
        result = extract_and_validate(raw)
        assert result.interests == []

    def test_missing_keys_get_safe_defaults(self):
        result = extract_and_validate({})
        assert result.confidence == "low"
        assert result.interests == []
        assert result.environment_type is None

    def test_has_signal_property(self):
        """``has_signal`` returns True for high/medium with interests."""
        low = extract_and_validate({"confidence": "low", "interests": []})
        assert low.has_signal is False

        high = extract_and_validate({
            "confidence": "high",
            "interests": ["food"],
        })
        assert high.has_signal is True

    def test_fallback_classmethod(self):
        fallback = VisionFeatures.fallback()
        assert fallback.confidence == "low"
        assert fallback.interests == []
        assert fallback.food_preferences == []
        assert fallback.environment_type is None
        assert fallback.travel_style is None
        assert fallback.pace is None
        assert fallback.budget_level is None
        assert fallback.has_signal is False


# ── multimodal_fusion tests ───────────────────────────────────────────────────

class TestFuseImageWithProfile:
    """``fuse_image_with_profile`` now accepts ``VisionFeatures``."""

    def _base_profile(self):
        return load_mock_profile(trip_id="test_trip")

    def _features(self, **overrides) -> VisionFeatures:
        defaults = {
            "environment_type": "nature",
            "travel_style": "adventure",
            "pace": "moderate",
            "vibe": "mountain trail",
            "interests": ["hiking", "photography"],
            "food_preferences": [],
            "budget_level": None,
            "confidence": "high",
        }
        defaults.update(overrides)
        return VisionFeatures(**defaults)

    def test_new_interests_are_merged(self):
        profile = self._base_profile()
        image_features = self._features()
        updated = fuse_image_with_profile(profile, image_features)
        assert "hiking" in updated["interests"]
        assert "photography" in updated["interests"]

    def test_duplicate_interests_not_added(self):
        profile = self._base_profile()
        image_features = self._features(
            environment_type="urban",
            travel_style="cultural",
            vibe=None,
            interests=["history"],  # already in profile
        )
        updated = fuse_image_with_profile(profile, image_features)
        assert updated["interests"].count("history") == 1

    def test_original_profile_not_mutated(self):
        profile = self._base_profile()
        original_interests = list(profile["interests"])
        image_features = self._features(
            environment_type="beach",
            travel_style="relaxation",
            vibe=None,
            interests=["surfing"],
        )
        fuse_image_with_profile(profile, image_features)
        assert profile["interests"] == original_interests

    def test_low_confidence_still_merges(self):
        """Low confidence interests are still merged (no data loss)."""
        profile = self._base_profile()
        image_features = self._features(
            environment_type=None,
            travel_style=None,
            vibe=None,
            interests=["extra-interest"],
            confidence="low",
        )
        updated = fuse_image_with_profile(profile, image_features)
        assert "extra-interest" in updated["interests"]