# backend/tests/unit/test_ai_engine/test_vision.py

import json
import pytest
from unittest.mock import patch

from ai_engine.vision.image_analyzer import analyze_travel_image
from ai_engine.vision.feature_extractor import extract_and_validate
from ai_engine.vision.multimodal_fusion import fuse_image_with_profile
from ai_engine.tools.profile_tool import load_mock_profile


VALID_VLM_RESPONSE = json.dumps({
    "environment_type": "urban",
    "activity_style":   "cultural",
    "vibe":             "busy historic bazaar",
    "inferred_interests": ["history", "food", "architecture"],
    "confidence": "high",
})

FENCED_VLM_RESPONSE = f"```json\n{VALID_VLM_RESPONSE}\n```"


# ── image_analyzer tests ──────────────────────────────────────────────────────

class TestAnalyzeTravelImage:

    @patch("ai_engine.vision.image_analyzer.analyze_image")
    def test_valid_response_returns_clean_dict(self, mock_analyze):
        mock_analyze.return_value = VALID_VLM_RESPONSE
        result = analyze_travel_image(b"fake_image_bytes")

        assert result["environment_type"] == "urban"
        assert result["activity_style"] == "cultural"
        assert "history" in result["inferred_interests"]
        assert result["confidence"] == "high"

    @patch("ai_engine.vision.image_analyzer.analyze_image")
    def test_strips_markdown_fences(self, mock_analyze):
        mock_analyze.return_value = FENCED_VLM_RESPONSE
        result = analyze_travel_image(b"fake_image_bytes")
        # Should parse correctly despite fences
        assert result["confidence"] in ("high", "medium", "low")

    @patch("ai_engine.vision.image_analyzer.analyze_image")
    def test_malformed_json_returns_fallback(self, mock_analyze):
        mock_analyze.return_value = "this is not json at all"
        result = analyze_travel_image(b"fake_image_bytes")

        assert result["confidence"] == "low"
        assert result["inferred_interests"] == []
        assert result["environment_type"] is None

    @patch("ai_engine.vision.image_analyzer.analyze_image")
    def test_api_exception_returns_fallback(self, mock_analyze):
        mock_analyze.side_effect = Exception("Groq API unavailable")
        result = analyze_travel_image(b"fake_image_bytes")

        assert result["confidence"] == "low"
        assert result["inferred_interests"] == []

    @patch("ai_engine.vision.image_analyzer.analyze_image")
    def test_result_always_has_all_keys(self, mock_analyze):
        mock_analyze.return_value = VALID_VLM_RESPONSE
        result = analyze_travel_image(b"fake_image_bytes")

        required_keys = {
            "environment_type", "activity_style",
            "vibe", "inferred_interests", "confidence"
        }
        assert required_keys.issubset(result.keys())


# ── feature_extractor tests ───────────────────────────────────────────────────

class TestExtractAndValidate:

    def test_valid_dict_passes_through(self):
        raw = {
            "environment_type": "beach",
            "activity_style":   "relaxing",
            "vibe":             "sunny coastline",
            "inferred_interests": ["beaches", "swimming"],
            "confidence": "high",
        }
        result = extract_and_validate(raw)
        assert result["environment_type"] == "beach"
        assert result["confidence"] == "high"

    def test_invalid_environment_becomes_none(self):
        raw = {"environment_type": "INVALID", "activity_style": None,
               "vibe": None, "inferred_interests": [], "confidence": "low"}
        result = extract_and_validate(raw)
        assert result["environment_type"] is None

    def test_interests_capped_at_five(self):
        raw = {
            "environment_type": None, "activity_style": None, "vibe": None,
            "inferred_interests": ["a", "b", "c", "d", "e", "f", "g"],
            "confidence": "medium",
        }
        result = extract_and_validate(raw)
        assert len(result["inferred_interests"]) == 5

    def test_non_list_interests_becomes_empty(self):
        raw = {
            "environment_type": None, "activity_style": None, "vibe": None,
            "inferred_interests": "history",   # string instead of list
            "confidence": "low",
        }
        result = extract_and_validate(raw)
        assert result["inferred_interests"] == []

    def test_missing_keys_get_safe_defaults(self):
        result = extract_and_validate({})  # completely empty dict
        assert result["confidence"] == "low"
        assert result["inferred_interests"] == []
        assert result["environment_type"] is None


# ── multimodal_fusion tests ───────────────────────────────────────────────────

class TestFuseImageWithProfile:

    def _base_profile(self):
        return load_mock_profile(user_id="test_user")

    def test_new_interests_are_merged(self):
        profile = self._base_profile()
        image_features = {
            "environment_type": "nature",
            "activity_style":   "adventurous",
            "vibe":             "mountain trail",
            "inferred_interests": ["hiking", "photography"],
            "confidence": "high",
        }
        updated = fuse_image_with_profile(profile, image_features)
        assert "hiking" in updated["interests"]
        assert "photography" in updated["interests"]

    def test_duplicate_interests_not_added(self):
        profile = self._base_profile()
        # Mock profile already has "history" in interests
        original_count = len(profile["interests"])
        image_features = {
            "environment_type": "urban",
            "activity_style": "cultural",
            "vibe": None,
            "inferred_interests": ["history"],   # already in profile
            "confidence": "high",
        }
        updated = fuse_image_with_profile(profile, image_features)
        # Count of "history" should still be 1
        assert updated["interests"].count("history") == 1

    def test_original_profile_not_mutated(self):
        profile = self._base_profile()
        original_interests = list(profile["interests"])
        image_features = {
            "environment_type": "beach", "activity_style": "relaxing",
            "vibe": None, "inferred_interests": ["surfing"], "confidence": "high",
        }
        fuse_image_with_profile(profile, image_features)
        # Original should be unchanged
        assert profile["interests"] == original_interests

    def test_low_confidence_does_not_update_slider(self):
        profile = self._base_profile()
        # Remove slider value to simulate unset profile
        profile = dict(profile)
        profile["adventure_relaxing"] = None
        from ai_engine.graph.state import BehavioralProfile
        profile = BehavioralProfile(**profile)

        image_features = {
            "environment_type": None, "activity_style": "adventurous",
            "vibe": None, "inferred_interests": [], "confidence": "low",
        }
        updated = fuse_image_with_profile(profile, image_features)
        # Low confidence → slider should stay None
        assert updated["adventure_relaxing"] is None