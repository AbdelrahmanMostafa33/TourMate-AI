# tests/unit/test_ai_engine/test_preference_agent.py

"""
Unit tests for the Preference Agent.

Tests cover:
    - _build_profile_context(): converts TripProfile to LLM context text
    - _derive_scores(): calculates dimension scores from profile fields
    - _calculate_confidence(): calculates confidence from fill rate
    - run_preference_agent(): full agent run with mocked LLM refinement
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from ai_engine.agents.preference_agent import (
    _build_profile_context,
    _derive_scores,
    _calculate_confidence,
    run_preference_agent,
    map_accommodation_to_enum,
)
from ai_engine.graph.state import TripProfile
from tests.unit.test_ai_engine.conftest import _make_state, _make_profile


# ── map_accommodation_to_enum Tests ──────────────────────────────────────

class TestMapAccommodationToEnum:

    def test_hostel_keyword(self):
        assert map_accommodation_to_enum(["cheap hostel"]) == "hostel"

    def test_resort_keyword(self):
        assert map_accommodation_to_enum(["beach resort"]) == "resort"

    def test_luxury_keyword(self):
        assert map_accommodation_to_enum(["luxury hotel"]) == "luxury"

    def test_boutique_keyword(self):
        assert map_accommodation_to_enum(["boutique hotel"]) == "luxury"

    def test_hotel_keyword(self):
        assert map_accommodation_to_enum(["standard hotel"]) == "hotel"

    def test_airbnb_keyword(self):
        assert map_accommodation_to_enum(["airbnb apartment"]) == "hotel"

    def test_unrecognized_returns_none(self):
        assert map_accommodation_to_enum(["some random place"]) is None

    def test_empty_list_returns_none(self):
        assert map_accommodation_to_enum([]) is None

    def test_first_match_wins(self):
        assert map_accommodation_to_enum(["luxury resort"]) == "resort"

    def test_case_insensitive(self):
        assert map_accommodation_to_enum(["HOSTEL"]) == "hostel"

    def test_five_star_maps_to_luxury(self):
        assert map_accommodation_to_enum(["five star hotel"]) == "luxury"

    def test_backpacker_maps_to_hostel(self):
        assert map_accommodation_to_enum(["backpacker dorm"]) == "hostel"


# ── _build_profile_context Tests ──────────────────────────────────────────────

class TestBuildProfileContext:

    def test_full_profile_generates_all_fields(self):
        profile = _make_profile()
        ctx = _build_profile_context(profile)

        assert "Budget: moderate" in ctx
        assert "Travel style: cultural" in ctx
        assert "Pace: moderate" in ctx
        assert "Interests: history, art, food" in ctx
        assert "Food preferences: local cuisine, street food" in ctx
        assert "Accommodation: boutique hotel, airbnb" in ctx

    def test_empty_profile_returns_fallback(self):
        profile = _make_profile(
            budget_level=None,
            travel_style=None,
            pace=None,
            interests=[],
            food_preferences=[],
            accommodation_preferences=[],
        )
        ctx = _build_profile_context(profile)
        assert ctx == "No profile data available."

    def test_budget_level_luxury(self):
        profile = _make_profile(budget_level="luxury")
        ctx = _build_profile_context(profile)
        assert "Budget: luxury" in ctx

    def test_budget_level_budget(self):
        profile = _make_profile(budget_level="budget")
        ctx = _build_profile_context(profile)
        assert "Budget: budget" in ctx

    def test_pace_relaxed(self):
        profile = _make_profile(pace="relaxed")
        ctx = _build_profile_context(profile)
        assert "Pace: relaxed" in ctx

    def test_pace_packed(self):
        profile = _make_profile(pace="packed")
        ctx = _build_profile_context(profile)
        assert "Pace: packed" in ctx

    def test_travel_style_romantic(self):
        profile = _make_profile(travel_style="romantic")
        ctx = _build_profile_context(profile)
        assert "Travel style: romantic" in ctx

    def test_only_interests_no_others(self):
        profile = _make_profile(
            budget_level=None,
            travel_style=None,
            pace=None,
            food_preferences=[],
            accommodation_preferences=[],
        )
        ctx = _build_profile_context(profile)
        assert "Interests:" in ctx
        assert "Budget:" not in ctx
        assert "Travel style:" not in ctx


# ── _derive_scores Tests ─────────────────────────────────────────────────────

class TestDeriveScores:

    def test_luxury_budget_gives_high_score(self):
        profile = _make_profile(budget_level="luxury")
        scores = _derive_scores(profile)
        assert scores["luxury_score"] >= 0.85

    def test_budget_budget_gives_low_score(self):
        profile = _make_profile(budget_level="budget", accommodation_preferences=[])  # no boost from accommodation
        scores = _derive_scores(profile)
        assert scores["luxury_score"] <= 0.2

    def test_moderate_budget_gives_mid_score(self):
        profile = _make_profile(budget_level="moderate", accommodation_preferences=[])  # no boost from accommodation
        scores = _derive_scores(profile)
        assert 0.4 <= scores["luxury_score"] <= 0.6

    def test_resort_boosts_luxury(self):
        profile = _make_profile(
            budget_level="moderate",
            accommodation_preferences=["resort"],
        )
        scores = _derive_scores(profile)
        # moderate=0.5 + resort boost 0.15 = 0.65
        assert scores["luxury_score"] >= 0.6

    def test_hostel_reduces_luxury(self):
        profile = _make_profile(
            budget_level="moderate",
            accommodation_preferences=["hostel"],
        )
        scores = _derive_scores(profile)
        # moderate=0.5 - hostel penalty 0.2 = 0.3
        assert scores["luxury_score"] <= 0.35

    def test_cultural_style_boosts_culture(self):
        profile = _make_profile(travel_style="cultural")
        scores = _derive_scores(profile)
        # base 0.3 + history(0.15) + art(0.15) + cultural style(0.25) = 0.85
        assert scores["culture_score"] >= 0.7

    def test_history_art_interests_boost_culture(self):
        profile = _make_profile(
            travel_style=None,
            interests=["history", "art", "museums"],
        )
        scores = _derive_scores(profile)
        # base 0.3 + 3 hits * 0.15 = 0.75
        assert scores["culture_score"] >= 0.7

    def test_adventure_style_boosts_adventure(self):
        profile = _make_profile(
            travel_style="adventure",
            interests=["hiking"],
        )
        scores = _derive_scores(profile)
        assert scores["adventure_score"] >= 0.5

    def test_packed_pace_boosts_adventure(self):
        profile = _make_profile(
            travel_style=None,
            pace="packed",
            interests=[],
        )
        scores = _derive_scores(profile)
        # base 0.2 + packed 0.1 = 0.3
        assert scores["adventure_score"] >= 0.25

    def test_relaxed_pace_reduces_adventure(self):
        profile = _make_profile(
            travel_style=None,
            pace="relaxed",
            interests=[],
        )
        scores = _derive_scores(profile)
        # base 0.2 - relaxed 0.15 = 0.05
        assert scores["adventure_score"] <= 0.1

    def test_shopping_interests_boost_shopping(self):
        profile = _make_profile(interests=["shopping", "markets"])
        scores = _derive_scores(profile)
        # base 0.15 + 2 hits * 0.2 = 0.55
        assert scores["shopping_score"] >= 0.5

    def test_family_style_boosts_family(self):
        profile = _make_profile(travel_style="family")
        scores = _derive_scores(profile)
        assert scores["family_score"] == 0.85

    def test_kids_interests_boost_family(self):
        profile = _make_profile(
            travel_style=None,
            interests=["kids", "family", "playground"],
        )
        scores = _derive_scores(profile)
        # base 0.2 + 3 hits * 0.25 = 0.95
        assert scores["family_score"] >= 0.8

    def test_empty_profile_gives_default_scores(self):
        profile = _make_profile(
            budget_level=None,
            travel_style=None,
            pace=None,
            interests=[],
            food_preferences=[],
            accommodation_preferences=[],
        )
        scores = _derive_scores(profile)
        # All scores should be non-negative and <= 1.0
        for key in ("luxury_score", "culture_score", "adventure_score", "shopping_score", "family_score"):
            assert 0.0 <= scores[key] <= 1.0


# ── _calculate_confidence Tests ──────────────────────────────────────────────

class TestCalculateConfidence:

    def test_all_fields_filled(self):
        profile = _make_profile()
        conf = _calculate_confidence(profile)
        # 6/6 fields filled = 1.0
        assert conf == 1.0

    def test_no_fields_filled(self):
        profile = _make_profile(
            budget_level=None,
            travel_style=None,
            pace=None,
            interests=[],
            food_preferences=[],
            accommodation_preferences=[],
        )
        conf = _calculate_confidence(profile)
        assert conf == 0.0

    def test_half_fields_filled(self):
        profile = _make_profile(
            budget_level="luxury",
            travel_style="romantic",
            pace=None,
            interests=[],
            food_preferences=[],
            accommodation_preferences=[],
        )
        conf = _calculate_confidence(profile)
        # 2/6 = 0.33
        assert 0.3 <= conf <= 0.4

    def test_one_field_filled(self):
        profile = _make_profile(
            budget_level="budget",
            travel_style=None,
            pace=None,
            interests=[],
            food_preferences=[],
            accommodation_preferences=[],
        )
        conf = _calculate_confidence(profile)
        # 1/6 = 0.17
        assert 0.1 <= conf <= 0.2


# ── run_preference_agent Tests (with mocked LLM) ─────────────────────────────

class TestRunPreferenceAgent:

    @pytest.mark.asyncio
    async def test_successful_refinement(self):
        """LLM returns valid refinements → profile enriched with scores."""
        refinement_response = {
            "budget_level": "luxury",
            "interests_add": ["museums"],
            "interests_remove": [],
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps(refinement_response)

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        profile = result["profile"]
        assert profile is not None
        # LLM override applied
        assert profile["budget_level"] == "luxury"
        # Interest added
        assert "museums" in profile["interests"]
        # Scores derived
        assert "luxury_score" in profile
        assert "culture_score" in profile
        assert "adventure_score" in profile
        assert "shopping_score" in profile
        assert "family_score" in profile
        # Confidence calculated
        assert "confidence" in profile
        assert 0.0 <= profile["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_empty_refinement_keeps_profile(self):
        """LLM returns empty object → profile unchanged except scores."""
        mock_response = MagicMock()
        mock_response.content = "{}"

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        profile = result["profile"]
        assert profile["budget_level"] == "moderate"  # unchanged
        assert profile["travel_style"] == "cultural"  # unchanged
        assert profile["pace"] == "moderate"  # unchanged
        # Scores still derived
        assert "luxury_score" in profile

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json_falls_back(self):
        """LLM returns garbage → graceful fallback, profile as-is."""
        mock_response = MagicMock()
        mock_response.content = "not json at all"

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        profile = result["profile"]
        # Profile fields unchanged
        assert profile["budget_level"] == "moderate"
        # Scores still derived
        assert "luxury_score" in profile
        assert "confidence" in profile

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back(self):
        """LLM raises exception → graceful fallback."""
        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", side_effect=Exception("API timeout")):
            state = _make_state()
            result = await run_preference_agent(state)

        profile = result["profile"]
        assert profile["budget_level"] == "moderate"
        assert "luxury_score" in profile

    @pytest.mark.asyncio
    async def test_extracted_preferences_populated(self):
        """After refinement, extracted_preferences is populated for downstream."""
        mock_response = MagicMock()
        mock_response.content = "{}"

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        prefs = result["extracted_preferences"]
        assert prefs is not None
        assert prefs["budget_level"] == "moderate"
        assert prefs["travel_style"] == "cultural"
        assert prefs["pace"] == "moderate"
        assert prefs["food_preferences"] == ["local cuisine", "street food"]
        assert prefs["interests_from_conversation"] == ["history", "art", "food"]
        # accommodation_style is first preference
        assert prefs["accommodation_style"] == "boutique hotel"

    @pytest.mark.asyncio
    async def test_destination_passed_in_prompt(self):
        """Destination from state should be included in the LLM prompt."""
        mock_response = MagicMock()
        mock_response.content = "{}"

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response) as mock_fn:
            state = _make_state(destination_city="Dubai")
            await run_preference_agent(state)

        # Verify the prompt sent to LLM contains the destination
        call_args = mock_fn.call_args
        messages = call_args[0][1]
        human_msg = messages[1].content
        assert "Dubai" in human_msg

    @pytest.mark.asyncio
    async def test_interests_add_and_remove(self):
        """LLM can add and remove interests from the profile."""
        refinement_response = {
            "interests_add": ["diving"],
            "interests_remove": ["art"],
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps(refinement_response)

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        interests = result["profile"]["interests"]
        assert "diving" in interests
        assert "art" not in interests
        # Original interests still there
        assert "history" in interests
        assert "food" in interests

    @pytest.mark.asyncio
    async def test_food_preferences_add_and_remove(self):
        """LLM can add and remove food preferences."""
        refinement_response = {
            "food_preferences_add": ["sushi"],
            "food_preferences_remove": ["street food"],
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps(refinement_response)

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        foods = result["profile"]["food_preferences"]
        assert "sushi" in foods
        assert "street food" not in foods
        assert "local cuisine" in foods

    @pytest.mark.asyncio
    async def test_accommodation_preferences_add_and_remove(self):
        """LLM can add and remove accommodation preferences."""
        refinement_response = {
            "accommodation_preferences_add": ["resort"],
            "accommodation_preferences_remove": ["airbnb"],
        }

        mock_response = MagicMock()
        mock_response.content = json.dumps(refinement_response)

        with patch("ai_engine.agents.preference_agent.invoke_with_fallback", return_value=mock_response):
            state = _make_state()
            result = await run_preference_agent(state)

        accs = result["profile"]["accommodation_preferences"]
        assert "resort" in accs
        assert "airbnb" not in accs
        assert "boutique hotel" in accs
