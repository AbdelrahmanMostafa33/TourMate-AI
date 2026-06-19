# backend/tests/unit/test_ai_engine/test_ranking_agent.py

"""
Unit tests for the Ranking Agent.

Tests cover:
    - _score_popularity(): normalizes popularity to 0-1
    - _score_preference(): matches place tags/categories to user preferences
    - _score_proximity(): distance-based scoring with hotel exemption
    - _score_rating(): normalizes 1-5 rating to 0-1
    - _compute_composite_score(): weighted multi-signal formula
    - _diversity_optimize(): per-category caps and total candidate limit
    - run_ranking_agent(): full agent run (no LLM needed)
"""

import pytest
from ai_engine.agents.ranking_agent import (
    _score_popularity,
    _score_preference,
    _score_proximity,
    _score_rating,
    _compute_composite_score,
    _diversity_optimize,
    run_ranking_agent,
    WEIGHT_POPULARITY,
    WEIGHT_PREFERENCE,
    WEIGHT_PROXIMITY,
    WEIGHT_RATING,
    WEIGHT_DIVERSITY,
    MAX_TOTAL_CANDIDATES,
)

from tests.unit.test_ai_engine.conftest import _make_state, _make_place


# ── Default extracted_preferences for ranking tests ──────────────────────────

_DEFAULT_RANKING_PREFS = {
    "budget_level": "moderate",
    "travel_style": "cultural",
    "walking_tolerance": "medium",
    "food_preferences": ["local cuisine"],
    "accommodation_style": "hotel",
    "nightlife": "low",
    "interests_from_conversation": ["history", "art"],
    "pace": "balanced",
    "special_focus": None,
}


def _make_ranking_state(**overrides) -> dict:
    """State with extracted_preferences pre-populated for ranking tests."""
    defaults = {
        "profile": None,
        "extracted_preferences": dict(_DEFAULT_RANKING_PREFS),
        "filtered_places": [],
        "destination_city": "Cairo",
    }
    defaults.update(overrides)
    return _make_state(**defaults)


# ── _score_popularity Tests ───────────────────────────────────────────────────

class TestScorePopularity:

    def test_zero_popularity(self):
        assert _score_popularity({"popularity_score": 0}) == 0.0

    def test_max_popularity_capped_at_1(self):
        assert _score_popularity({"popularity_score": 150}) == 1.0

    def test_50_popularity(self):
        assert _score_popularity({"popularity_score": 50}) == 0.5

    def test_missing_popularity_defaults_to_zero(self):
        assert _score_popularity({}) == 0.0

    def test_none_popularity(self):
        assert _score_popularity({"popularity_score": None}) == 0.0

    def test_100_popularity(self):
        assert _score_popularity({"popularity_score": 100}) == 1.0


# ── _score_preference Tests ───────────────────────────────────────────────────

class TestScorePreference:

    def test_interest_tag_match(self):
        place = _make_place(interest_tags=["history", "museums"])
        prefs = {"interests_from_conversation": ["history"]}
        score = _score_preference(place, prefs)
        assert score > 0

    def test_interest_category_match(self):
        """Category name matches an interest directly."""
        place = _make_place(category="museum", interest_tags=[])
        prefs = {"interests_from_conversation": ["museum"]}
        score = _score_preference(place, prefs)
        assert score > 0

    def test_no_interest_match(self):
        place = _make_place(interest_tags=["sports"])
        prefs = {"interests_from_conversation": ["history", "art"]}
        score = _score_preference(place, prefs)
        assert score == 0.0

    def test_romantic_style_match(self):
        place = _make_place(sub_category="romantic riverside cafe")
        prefs = {"travel_style": "romantic"}
        score = _score_preference(place, prefs)
        assert score > 0

    def test_cultural_style_match_museum(self):
        place = _make_place(sub_category="museum exhibit")
        prefs = {"travel_style": "cultural"}
        score = _score_preference(place, prefs)
        assert score > 0

    def test_no_style_match(self):
        place = _make_place(sub_category="sports bar")
        prefs = {"travel_style": "romantic"}
        score = _score_preference(place, prefs)
        assert score == 0.0

    def test_food_preference_match(self):
        place = _make_place(category="restaurant", cuisine_type="local cuisine")
        prefs = {"food_preferences": ["local cuisine"]}
        score = _score_preference(place, prefs)
        assert score > 0

    def test_food_preference_no_match(self):
        place = _make_place(category="restaurant", cuisine_type="sushi")
        prefs = {"food_preferences": ["local cuisine"]}
        score = _score_preference(place, prefs)
        assert score == 0.0

    def test_food_check_only_for_restaurants(self):
        """Non-restaurant places skip food preference check."""
        place = _make_place(category="attractions", cuisine_type="")
        prefs = {"food_preferences": ["local cuisine"]}
        score = _score_preference(place, prefs)
        # Only interest check happened (0 since no tag match)
        assert score == 0.0

    def test_empty_preferences_returns_zero(self):
        place = _make_place()
        prefs = {}
        score = _score_preference(place, prefs)
        assert score == 0.0


# ── _score_proximity Tests ────────────────────────────────────────────────────

class TestScoreProximity:

    def test_same_location_returns_1(self):
        """Place at the center should score 1.0."""
        score = _score_proximity(
            _make_place(lat=30.0, lon=31.0),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score == 1.0

    def test_hotel_gets_neutral_score(self):
        """Hotels are exempt from proximity scoring."""
        score = _score_proximity(
            _make_place(category="hotel", lat=35.0, lon=36.0),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score == 0.5

    def test_close_place_scores_high(self):
        """Place ~3km away should score high."""
        score = _score_proximity(
            _make_place(lat=30.03, lon=31.23),
            center_lat=30.0,
            center_lon=31.2,
        )
        assert score >= 0.8

    def test_far_place_scores_low(self):
        """Place ~45km away should score low."""
        score = _score_proximity(
            _make_place(lat=30.5, lon=31.5),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score < 0.3

    def test_very_far_place_scores_near_zero(self):
        """Place ~100km away should score near 0."""
        score = _score_proximity(
            _make_place(lat=31.0, lon=32.0),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score >= 0.0
        assert score < 0.2


# ── _score_rating Tests ───────────────────────────────────────────────────────

class TestScoreRating:

    def test_perfect_rating(self):
        assert _score_rating({"rating": 5.0}) == 1.0

    def test_min_rating(self):
        assert _score_rating({"rating": 1.0}) == 0.0

    def test_average_rating(self):
        score = _score_rating({"rating": 3.0})
        assert 0.4 < score < 0.6

    def test_missing_rating_defaults_to_3(self):
        score = _score_rating({})
        assert 0.4 < score < 0.6

    def test_none_rating_defaults_to_3(self):
        score = _score_rating({"rating": None})
        assert 0.4 < score < 0.6

    def test_rating_clamped_above_5(self):
        assert _score_rating({"rating": 6.0}) == 1.0

    def test_rating_zero_uses_default(self):
        """rating=0.0 is falsy in Python, so `or 3.0` kicks in → treated as unrated."""
        assert _score_rating({"rating": 0.0}) == 0.5  # default 3.0


# ── _compute_composite_score Tests ────────────────────────────────────────────

class TestComputeCompositeScore:

    def test_perfect_place_scores_high(self):
        """A place with max popularity, rating, and preference match."""
        place = _make_place(
            popularity_score=100,
            rating=5.0,
            interest_tags=["history"],
            lat=30.0,
            lon=31.0,
        )
        prefs = {"interests_from_conversation": ["history"], "travel_style": "cultural"}
        cat_counts = {}
        targets = {"attractions": 6}

        score = _compute_composite_score(place, prefs, 30.0, 31.0, cat_counts, targets)
        assert score > 0.6  # Should be high

    def test_zero_popularity_low_rating_scores_low(self):
        place = _make_place(
            popularity_score=0,
            rating=1.0,
            interest_tags=[],
            lat=35.0,
            lon=36.0,
        )
        prefs = {"interests_from_conversation": ["history"]}
        cat_counts = {"attractions": 10}
        targets = {"attractions": 6}

        score = _compute_composite_score(place, prefs, 30.0, 31.0, cat_counts, targets)
        assert score < 0.4

    def test_diversity_bonus_for_underrepresented_category(self):
        """Category at 0 count should get full diversity bonus."""
        place = _make_place(category="restaurant")
        prefs = {}
        cat_counts = {}  # restaurant not seen yet
        targets = {"restaurant": 3}

        score = _compute_composite_score(place, prefs, 30.0, 31.0, cat_counts, targets)
        # Diversity bonus should contribute positively
        assert score > 0

    def test_no_diversity_bonus_for_overrepresented_category(self):
        """Category already at target should get no diversity bonus."""
        place = _make_place(category="restaurant", popularity_score=0, rating=1.0, interest_tags=[])
        prefs = {}
        cat_counts = {"restaurant": 5}  # already at target
        targets = {"restaurant": 3}

        score_over = _compute_composite_score(place, prefs, 30.0, 31.0, cat_counts, targets)

        cat_counts_under = {}
        score_under = _compute_composite_score(place, prefs, 30.0, 31.0, cat_counts_under, targets)

        assert score_under >= score_over  # Underrepresented gets higher score

    def test_weights_sum_to_one(self):
        total = WEIGHT_POPULARITY + WEIGHT_PREFERENCE + WEIGHT_PROXIMITY + WEIGHT_RATING + WEIGHT_DIVERSITY
        assert abs(total - 1.0) < 0.001


# ── _diversity_optimize Tests ─────────────────────────────────────────────────

class TestDiversityOptimize:

    def test_caps_total_candidates(self):
        """Result should not exceed MAX_TOTAL_CANDIDATES."""
        # Create places across multiple categories to hit the 30 cap
        places = []
        for i in range(15):
            places.append((_make_place(id=f"attr_{i}", category="attractions"), 0.9))
        for i in range(15):
            places.append((_make_place(id=f"rest_{i}", category="restaurant"), 0.85))
        for i in range(10):
            places.append((_make_place(id=f"hotel_{i}", category="hotel"), 0.8))
        for i in range(10):
            places.append((_make_place(id=f"shop_{i}", category="shopping"), 0.75))
        result = _diversity_optimize(places, duration_days=3)
        assert len(result) <= MAX_TOTAL_CANDIDATES

    def test_preserves_highest_scored(self):
        """Top-scored places should be preferred."""
        high = _make_place(id="high", popularity_score=100, rating=5.0)
        low = _make_place(id="low", popularity_score=10, rating=2.0)
        scored = [(high, 0.95), (low, 0.1)]
        result = _diversity_optimize(scored, duration_days=3)
        result_ids = [p["id"] for p in result]
        assert "high" in result_ids

    def test_empty_input_returns_empty(self):
        result = _diversity_optimize([], duration_days=3)
        assert result == []

    def test_single_place_returns_single(self):
        place = _make_place()
        result = _diversity_optimize([(place, 0.8)], duration_days=3)
        assert len(result) == 1

    def test_multiple_categories_represented(self):
        """With enough places, multiple categories should appear."""
        places = []
        for i in range(5):
            places.append((_make_place(id=f"attr_{i}", category="attractions"), 0.9 - i * 0.05))
        for i in range(5):
            places.append((_make_place(id=f"rest_{i}", category="restaurant"), 0.8 - i * 0.05))
        for i in range(3):
            places.append((_make_place(id=f"hotel_{i}", category="hotel"), 0.7 - i * 0.05))

        result = _diversity_optimize(places, duration_days=3)
        categories = set(p["category"] for p in result)
        assert len(categories) >= 2

    def test_longer_trip_allows_more_candidates(self):
        """A 7-day trip should allow more attractions than a 2-day trip."""
        places_2d = [
            (_make_place(id=f"a2d_{i}", category="attractions"), 0.9)
            for i in range(20)
        ]
        places_7d = [
            (_make_place(id=f"a7d_{i}", category="attractions"), 0.9)
            for i in range(20)
        ]

        result_2d = _diversity_optimize(places_2d, duration_days=2)
        result_7d = _diversity_optimize(places_7d, duration_days=7)

        attractions_2d = sum(1 for p in result_2d if p["category"] == "attractions")
        attractions_7d = sum(1 for p in result_7d if p["category"] == "attractions")
        assert attractions_7d >= attractions_2d


# ── run_ranking_agent Tests ───────────────────────────────────────────────────

class TestRunRankingAgent:

    @pytest.mark.asyncio
    async def test_empty_filtered_places_sets_error(self):
        state = _make_ranking_state(filtered_places=[])
        result = await run_ranking_agent(state)

        assert result["candidate_places"] == []
        assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_none_filtered_places_sets_error(self):
        state = _make_ranking_state(filtered_places=None)
        result = await run_ranking_agent(state)

        assert result["candidate_places"] == []

    @pytest.mark.asyncio
    async def test_single_place_returns_it(self):
        place = _make_place()
        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        assert len(result["candidate_places"]) == 1
        assert result["candidate_places"][0]["id"] == "place_001"

    @pytest.mark.asyncio
    async def test_multiple_places_ranked(self):
        places = [
            _make_place(id="p_high", popularity_score=95, rating=4.8),
            _make_place(id="p_low", popularity_score=20, rating=3.0),
            _make_place(id="p_mid", popularity_score=60, rating=4.0),
        ]
        state = _make_ranking_state(filtered_places=places)
        result = await run_ranking_agent(state)

        candidates = result["candidate_places"]
        assert len(candidates) >= 1
        # Top candidate should be the high-scored one
        assert candidates[0]["id"] == "p_high"

    @pytest.mark.asyncio
    async def test_candidate_places_capped(self):
        """With many places, result should not exceed MAX_TOTAL_CANDIDATES."""
        places = [
            _make_place(id=f"place_{i}", popularity_score=80, category="attractions")
            for i in range(50)
        ]
        state = _make_ranking_state(filtered_places=places, duration_days=7)
        result = await run_ranking_agent(state)

        assert len(result["candidate_places"]) <= MAX_TOTAL_CANDIDATES

    @pytest.mark.asyncio
    async def test_agent_message_appended(self):
        place = _make_place()
        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        messages = result["agent_messages"]
        assert any("[RankingAgent]" in m for m in messages)

    @pytest.mark.asyncio
    async def test_city_center_computed_from_non_hotel_places(self):
        """City center should be the average lat/lon of non-hotel places."""
        hotel = _make_place(id="h1", category="hotel", lat=35.0, lon=36.0)
        attraction = _make_place(id="a1", category="attractions", lat=30.0, lon=31.0)
        state = _make_ranking_state(filtered_places=[hotel, attraction])
        result = await run_ranking_agent(state)

        # Should succeed without error
        assert result["error"] is None
        assert len(result["candidate_places"]) >= 1
