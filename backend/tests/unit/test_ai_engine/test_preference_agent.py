# tests/unit/test_ai_engine/test_preference_agent.py

"""
Unit tests for the Preference Agent.

Tests cover:
    - _derive_scores(): calculates dimension scores from profile fields
    - _calculate_confidence(): calculates confidence from fill rate
    - map_accommodation_to_enum(): maps natural language to enum
"""

import pytest

from ai_engine.agents.preference_agent import (
    _derive_scores,
    _calculate_confidence,
    map_accommodation_to_enum,
)
from tests.unit.test_ai_engine.conftest import _make_profile


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
        for key in ("luxury_score", "culture_score", "adventure_score"):
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



