# tests/unit/test_ai_engine/test_preference_reranker_agent.py

"""
Unit tests for the Preference Reranker Agent (Mode 1).

Tests cover:
    - apply_preference_adjustments(): applies adjustment dicts to TripSlots
    - interpret_preference_adjustment(): interprets vibe changes via mocked LLM
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from ai_engine.agents.preference_reranker_agent import (
    interpret_preference_adjustment,
    apply_preference_adjustments,
)
from ai_engine.memory.conversation_state import TripSlots


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def filled_slots() -> TripSlots:
    """TripSlots with default smart defaults filled in."""
    slots = TripSlots()
    slots.fill_defaults()  # sets budget=moderate, style=cultural, pace=moderate, etc.
    return slots


@pytest.fixture
def empty_slots() -> TripSlots:
    """TripSlots with nothing set."""
    return TripSlots()


# ── apply_preference_adjustments Tests ─────────────────────────────────────────


class TestApplyPreferenceAdjustments:

    def test_add_interests(self, filled_slots):
        """'interests_add' appends new interests without removing existing ones."""
        adjustments = {
            "interests_add": ["entertainment", "nightlife"],
            "rerank_reason": "Adding entertainment for more fun",
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "entertainment" in result["interests_from_conversation"]
        assert "nightlife" in result["interests_from_conversation"]
        # Original defaults still present
        assert "local cuisine" in result.get("food_preferences", [])

    def test_remove_interests(self, filled_slots):
        """'interests_remove' removes specified interests."""
        # First add some interests so we have something to remove
        filled_slots.interests = ["history", "art", "food", "shopping"]

        adjustments = {
            "interests_remove": ["art", "food"],
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "art" not in result["interests_from_conversation"]
        assert "food" not in result["interests_from_conversation"]
        assert "history" in result["interests_from_conversation"]
        assert "shopping" in result["interests_from_conversation"]

    def test_change_budget_to_budget(self, filled_slots):
        """Budget level can be changed to 'budget'."""
        adjustments = {"budget_level": "budget"}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["budget_level"] == "budget"

    def test_change_budget_to_luxury(self, filled_slots):
        """Budget level can be changed to 'luxury'."""
        adjustments = {"budget_level": "luxury"}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["budget_level"] == "luxury"

    def test_more_entertaining_scenario(self, filled_slots):
        """Full adjustment for 'more entertaining'."""
        adjustments = {
            "interests_add": ["entertainment", "nightlife"],
            "special_focus": "evening entertainment and shows",
            "rerank_reason": "Adding entertainment and nightlife interests boosts venues",
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "entertainment" in result["interests_from_conversation"]
        assert "nightlife" in result["interests_from_conversation"]
        assert result["special_focus"] == "evening entertainment and shows"
        # Original fields preserved
        assert result["budget_level"] == "moderate"
        assert result["travel_style"] == "cultural"

    def test_cheaper_scenario(self, filled_slots):
        """Full adjustment for 'cheaper'."""
        adjustments = {
            "budget_level": "budget",
            "food_preferences_remove": ["expensive dining"],
            "rerank_reason": "Budget level filters expensive restaurants and hotels",
        }
        # Add something that will be removed
        filled_slots.food_preferences = ["local cuisine", "expensive dining"]

        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["budget_level"] == "budget"
        assert "expensive dining" not in result.get("food_preferences", [])
        assert "local cuisine" in result.get("food_preferences", [])

    def test_more_cultural_scenario(self, filled_slots):
        """Full adjustment for 'more cultural'."""
        adjustments = {
            "interests_add": ["history", "museums", "art"],
            "travel_style": "cultural",
            "rerank_reason": "Cultural interests boost museums and historic sites",
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "history" in result["interests_from_conversation"]
        assert "museums" in result["interests_from_conversation"]
        assert "art" in result["interests_from_conversation"]
        assert result["travel_style"] == "cultural"

    def test_empty_adjustments_returns_current(self, filled_slots):
        """Empty adjustments dict returns current preferences unchanged."""
        result = apply_preference_adjustments(filled_slots, {})

        assert result["budget_level"] == "moderate"
        assert result["travel_style"] == "cultural"
        assert result["pace"] == "moderate"
        assert result["special_focus"] is None

    def test_change_style_to_adventure(self, filled_slots):
        """Travel style can be changed to 'adventure'."""
        adjustments = {"travel_style": "adventure"}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["travel_style"] == "adventure"

    def test_change_pace_to_packed(self, filled_slots):
        """Pace can be changed to 'packed'."""
        adjustments = {"pace": "packed"}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["pace"] == "packed"

    def test_change_pace_to_relaxed(self, filled_slots):
        """Pace can be changed to 'relaxed'."""
        adjustments = {"pace": "relaxed"}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["pace"] == "relaxed"

    def test_food_preferences_add_and_remove(self, filled_slots):
        """Food preferences can be added and removed simultaneously."""
        filled_slots.food_preferences = ["local cuisine", "street food"]

        adjustments = {
            "food_preferences_add": ["sushi", "seafood"],
            "food_preferences_remove": ["street food"],
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "sushi" in result["food_preferences"]
        assert "seafood" in result["food_preferences"]
        assert "local cuisine" in result["food_preferences"]
        assert "street food" not in result["food_preferences"]

    def test_accommodation_preferences_add_and_remove(self, filled_slots):
        """Accommodation preferences can be added and removed."""
        filled_slots.accommodation_preferences = ["hotel"]

        adjustments = {
            "accommodation_preferences_add": ["resort"],
            "accommodation_preferences_remove": ["hotel"],
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert "resort" in result.get("accommodation_preferences", [])
        assert "hotel" not in result.get("accommodation_preferences", [])
        assert result["accommodation_style"] == "resort"

    def test_accommodation_style_first_preference(self, filled_slots):
        """accommodation_style is the first item in accommodation_preferences."""
        filled_slots.accommodation_preferences = ["hostel", "hotel"]

        adjustments = {
            "accommodation_preferences_add": ["resort"],
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["accommodation_style"] == "hostel"  # still first

    def test_accommodation_style_empty_falls_back(self, empty_slots):
        """When accommodation list is empty, style falls back to 'hotel'."""
        adjustments = {}
        result = apply_preference_adjustments(empty_slots, adjustments)

        assert result["accommodation_style"] == "hotel"

    def test_faster_pace_scenario(self, filled_slots):
        """Adjustment for 'faster pace' or 'packed schedule'."""
        adjustments = {
            "pace": "packed",
            "rerank_reason": "Packed pace encourages more stops per day",
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["pace"] == "packed"

    def test_multiple_adjustments_together(self, filled_slots):
        """Multiple adjustments applied at once combine correctly."""
        adjustments = {
            "budget_level": "luxury",
            "travel_style": "romantic",
            "pace": "relaxed",
            "interests_add": ["shopping", "spa"],
            "interests_remove": [],
            "special_focus": "luxury romantic getaway",
        }
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["budget_level"] == "luxury"
        assert result["travel_style"] == "romantic"
        assert result["pace"] == "relaxed"
        assert "shopping" in result["interests_from_conversation"]
        assert "spa" in result["interests_from_conversation"]
        assert result["special_focus"] == "luxury romantic getaway"

    def test_none_slots(self):
        """Empty TripSlots (None list fields) handled gracefully."""
        slots = TripSlots()  # all None

        adjustments = {
            "interests_add": ["history", "museums"],
            "budget_level": "budget",
        }
        result = apply_preference_adjustments(slots, adjustments)

        assert result["interests_from_conversation"] == ["history", "museums"]
        assert result["budget_level"] == "budget"

    def test_remove_nonexistent_interest_does_nothing(self, filled_slots):
        """Removing an interest that doesn't exist is a no-op."""
        filled_slots.interests = ["history"]

        adjustments = {"interests_remove": ["skydiving"]}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["interests_from_conversation"] == ["history"]

    def test_add_duplicate_interest_does_not_duplicate(self, filled_slots):
        """Adding an interest that already exists doesn't create duplicates."""
        filled_slots.interests = ["history"]

        adjustments = {"interests_add": ["history"]}
        result = apply_preference_adjustments(filled_slots, adjustments)

        assert result["interests_from_conversation"] == ["history"]


# ── interpret_preference_adjustment Tests (with mocked LLM) ──────────────────


class TestInterpretPreferenceAdjustment:

    @pytest.mark.asyncio
    async def test_more_entertaining(self):
        """'more entertaining' → adds entertainment/nightlife interests."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "interests_add": ["entertainment", "nightlife"],
            "special_focus": "evening entertainment and shows",
            "rerank_reason": "Adding entertainment and nightlife interests boosts venues like cinemas, opera houses, and night spots in the ranking",
        })

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("more entertaining")

        assert "entertainment" in result.get("interests_add", [])
        assert "nightlife" in result.get("interests_add", [])
        assert "rerank_reason" in result

    @pytest.mark.asyncio
    async def test_cheaper(self):
        """'cheaper' → changes budget to budget level."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "budget_level": "budget",
            "rerank_reason": "Budget level filters expensive restaurants and hotels",
        })

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("cheaper")

        assert result.get("budget_level") == "budget"

    @pytest.mark.asyncio
    async def test_more_cultural(self):
        """'more cultural' → adds cultural interests and sets travel_style."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "interests_add": ["history", "museums", "art"],
            "travel_style": "cultural",
            "rerank_reason": "Cultural interests boost museums and historic sites",
        })

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("more cultural")

        assert "history" in result.get("interests_add", [])
        assert "museums" in result.get("interests_add", [])
        assert "art" in result.get("interests_add", [])
        assert result.get("travel_style") == "cultural"

    @pytest.mark.asyncio
    async def test_with_current_preferences(self):
        """Current preferences dict is included in the LLM prompt."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "interests_add": ["entertainment"],
            "rerank_reason": "Adding entertainment to existing cultural interests",
        })

        current_prefs = {
            "budget_level": "moderate",
            "travel_style": "cultural",
            "pace": "moderate",
            "interests": ["history", "art"],
            "food_preferences": ["local cuisine"],
            "accommodation_preferences": ["hotel"],
        }

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response) as mock_fn:
            result = await interpret_preference_adjustment(
                "more entertaining",
                current_preferences=current_prefs,
            )

        # Verify the prompt included current preferences
        call_args = mock_fn.call_args
        messages = call_args[0][1]
        human_msg = messages[1].content
        assert "more entertaining" in human_msg
        assert "budget_level: moderate" in human_msg
        assert "interests: history, art" in human_msg
        assert "food_preferences: local cuisine" in human_msg

        assert "entertainment" in result.get("interests_add", [])

    @pytest.mark.asyncio
    async def test_llm_invalid_json_falls_back(self):
        """LLM returns garbage → graceful fallback to empty dict."""
        mock_response = MagicMock()
        mock_response.content = "not valid json at all"

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("more entertaining")

        assert result == {}

    @pytest.mark.asyncio
    async def test_llm_empty_json(self):
        """LLM returns valid empty JSON object."""
        mock_response = MagicMock()
        mock_response.content = "{}"

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("no changes needed")

        assert result == {}

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back(self):
        """LLM raises exception → graceful fallback to empty dict."""
        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", side_effect=Exception("API timeout")):
            result = await interpret_preference_adjustment("more entertaining")

        assert result == {}

    @pytest.mark.asyncio
    async def test_faster_pace_request(self):
        """'faster pace' → returns pace=packed."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "pace": "packed",
            "rerank_reason": "Packed pace encourages more stops per day",
        })

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("faster pace")

        assert result.get("pace") == "packed"

    @pytest.mark.asyncio
    async def test_romantic_trip_request(self):
        """'more romantic' → changes style to romantic, adds appropriate interests."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "travel_style": "romantic",
            "interests_add": ["scenic views", "fine dining"],
            "special_focus": "romantic experiences",
            "rerank_reason": "Romantic style boosts scenic spots and fine dining venues",
        })

        with patch("ai_engine.agents.preference_reranker_agent.invoke_with_fallback", return_value=mock_response):
            result = await interpret_preference_adjustment("more romantic")

        assert result.get("travel_style") == "romantic"
        assert "scenic views" in result.get("interests_add", [])
        assert "fine dining" in result.get("interests_add", [])
