# backend/tests/unit/test_ai_engine/test_ranking_agent.py

"""
Unit tests for the Ranking Agent (embedding-based scoring).

Tests cover:
    - _score_popularity(): normalizes popularity to 0-1
    - _score_preference_embedding(): cosine-similarity scoring with fallback
    - _score_proximity(): distance-based scoring with hotel exemption
    - _score_rating(): normalizes 1-5 rating to 0-1
    - _compute_composite_score(): weighted multi-signal formula (embedding path)
    - _diversity_optimize(): per-category caps and total candidate limit
    - run_ranking_agent(): full agent run (DB + embedding calls mocked)
"""

import pytest
from unittest.mock import AsyncMock, patch

from ai_engine.agents.ranking_agent import (
    _score_popularity,
    _score_preference_embedding,
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
    FALLBACK_EMBEDDING_SCORE,
)

from tests.unit.test_ai_engine.conftest import _make_state, _make_place


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_dummy_query_vector() -> list[float]:
    """A dummy 768-dim query vector (all 0.5 for neutral similarity)."""
    return [0.5] * 768


def _make_dummy_place_vectors(place_ids: list[str]) -> dict[str, list[float]]:
    """Create dummy place vectors for a list of place IDs."""
    return {pid: [0.5] * 768 for pid in place_ids}


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


# ── _score_preference_embedding Tests ─────────────────────────────────────────

class TestScorePreferenceEmbedding:

    def test_high_similarity_scores_high(self):
        """Place with identical direction to query scores ~1.0."""
        query_vec = [1.0, 0.0, 0.0]
        place_vecs = {"place_001": [1.0, 0.0, 0.0]}
        place = {"id": "place_001"}
        score = _score_preference_embedding(place, query_vec, place_vecs)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_orthogonal_similarity_scores_mid(self):
        """Orthogonal vectors (cosine=0) map to 0.5."""
        query_vec = [1.0, 0.0, 0.0]
        place_vecs = {"place_001": [0.0, 1.0, 0.0]}
        place = {"id": "place_001"}
        score = _score_preference_embedding(place, query_vec, place_vecs)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_opposite_similarity_scores_zero(self):
        """Opposite direction (cosine=-1) maps to 0.0."""
        query_vec = [1.0, 0.0, 0.0]
        place_vecs = {"place_001": [-1.0, 0.0, 0.0]}
        place = {"id": "place_001"}
        score = _score_preference_embedding(place, query_vec, place_vecs)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_no_query_vector_uses_fallback(self):
        """When query embedding failed, all places get fallback score."""
        place = {"id": "place_001"}
        score = _score_preference_embedding(place, None, {})
        assert score == FALLBACK_EMBEDDING_SCORE

    def test_missing_place_embedding_uses_fallback(self):
        """Place without a stored embedding gets fallback score."""
        query_vec = [0.5] * 768
        place = {"id": "place_001"}
        score = _score_preference_embedding(place, query_vec, {})
        assert score == FALLBACK_EMBEDDING_SCORE

    def test_empty_place_id_uses_fallback(self):
        """Place with empty ID cannot look up embedding → fallback."""
        query_vec = [0.5] * 768
        place = {"id": ""}
        score = _score_preference_embedding(place, query_vec, {"other": [0.5] * 768})
        assert score == FALLBACK_EMBEDDING_SCORE


# ── _score_proximity Tests ────────────────────────────────────────────────────

class TestScoreProximity:

    def test_same_location_returns_1(self):
        score = _score_proximity(
            _make_place(lat=30.0, lon=31.0),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score == 1.0

    def test_hotel_gets_neutral_score(self):
        score = _score_proximity(
            _make_place(category="hotel", lat=35.0, lon=36.0),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score == 0.5

    def test_close_place_scores_high(self):
        score = _score_proximity(
            _make_place(lat=30.03, lon=31.23),
            center_lat=30.0,
            center_lon=31.2,
        )
        assert score >= 0.8

    def test_far_place_scores_low(self):
        score = _score_proximity(
            _make_place(lat=30.5, lon=31.5),
            center_lat=30.0,
            center_lon=31.0,
        )
        assert score < 0.3

    def test_very_far_place_scores_near_zero(self):
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
        assert _score_rating({"rating": 0.0}) == 0.5


# ── _compute_composite_score Tests ────────────────────────────────────────────

class TestComputeCompositeScore:

    def test_perfect_place_scores_high(self):
        """A place with max popularity, rating, and embedding match."""
        place = _make_place(
            popularity_score=100,
            rating=5.0,
            lat=30.0,
            lon=31.0,
        )
        qv = _make_dummy_query_vector()
        pv = _make_dummy_place_vectors(["place_001"])
        cat_counts = {}
        targets = {"attractions": 6}

        score = _compute_composite_score(place, qv, pv, 30.0, 31.0, cat_counts, targets)
        assert score > 0.6

    def test_zero_popularity_low_rating_scores_low(self):
        place = _make_place(
            popularity_score=0,
            rating=1.0,
            lat=35.0,
            lon=36.0,
        )
        qv = _make_dummy_query_vector()
        pv = _make_dummy_place_vectors(["place_001"])
        cat_counts = {"attractions": 10}
        targets = {"attractions": 6}

        score = _compute_composite_score(place, qv, pv, 30.0, 31.0, cat_counts, targets)
        assert score < 0.4

    def test_fallback_embedding_when_query_missing(self):
        """When query_vector is None, composite should still work via fallback."""
        place = _make_place(popularity_score=50, rating=3.0)
        cat_counts = {}
        targets = {"attractions": 3}

        score = _compute_composite_score(place, None, {}, 30.0, 31.0, cat_counts, targets)
        # Should still compute a positive score from popularity + proximity + rating
        assert score > 0.0

    def test_diversity_bonus_for_underrepresented_category(self):
        place = _make_place(category="restaurant")
        qv = _make_dummy_query_vector()
        pv = _make_dummy_place_vectors(["place_001"])
        cat_counts = {}
        targets = {"restaurant": 3}

        score = _compute_composite_score(place, qv, pv, 30.0, 31.0, cat_counts, targets)
        assert score > 0

    def test_no_diversity_bonus_for_overrepresented_category(self):
        place = _make_place(
            category="restaurant",
            popularity_score=0,
            rating=1.0,
        )
        qv = _make_dummy_query_vector()
        pv = _make_dummy_place_vectors(["place_001"])
        cat_counts = {"restaurant": 5}
        targets = {"restaurant": 3}

        score_over = _compute_composite_score(
            place, qv, pv, 30.0, 31.0, cat_counts, targets
        )
        cat_counts_under = {}
        score_under = _compute_composite_score(
            place, qv, pv, 30.0, 31.0, cat_counts_under, targets
        )

        assert score_under >= score_over

    def test_weights_sum_to_one(self):
        total = WEIGHT_POPULARITY + WEIGHT_PREFERENCE + WEIGHT_PROXIMITY + WEIGHT_RATING + WEIGHT_DIVERSITY
        assert abs(total - 1.0) < 0.001


# ── _diversity_optimize Tests ─────────────────────────────────────────────────

class TestDiversityOptimize:

    def test_caps_total_candidates(self):
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
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_empty_filtered_places_sets_error(self, mock_embed, mock_load):
        state = _make_ranking_state(filtered_places=[])
        result = await run_ranking_agent(state)

        assert result["candidate_places"] == []
        assert result["error"] is not None
        mock_embed.assert_not_called()
        mock_load.assert_not_called()

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_none_filtered_places_sets_error(self, mock_embed, mock_load):
        state = _make_ranking_state(filtered_places=None)
        result = await run_ranking_agent(state)

        assert result["candidate_places"] == []
        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_single_place_returns_it(self, mock_embed, mock_load):
        place = _make_place()
        mock_load.return_value = {"place_001": [0.5] * 768}
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        assert len(result["candidate_places"]) == 1
        assert result["candidate_places"][0]["id"] == "place_001"
        mock_embed.assert_called_once()
        mock_load.assert_called_once()

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_multiple_places_ranked(self, mock_embed, mock_load):
        places = [
            _make_place(id="p_high", popularity_score=95, rating=4.8),
            _make_place(id="p_low", popularity_score=20, rating=3.0),
            _make_place(id="p_mid", popularity_score=60, rating=4.0),
        ]
        mock_load.return_value = {
            "p_high": [0.6] * 768,
            "p_low": [0.3] * 768,
            "p_mid": [0.5] * 768,
        }
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=places)
        result = await run_ranking_agent(state)

        candidates = result["candidate_places"]
        assert len(candidates) >= 1
        # Top candidate should be the high-scored one
        assert candidates[0]["id"] == "p_high"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_candidate_places_capped(self, mock_embed, mock_load):
        places = [
            _make_place(id=f"place_{i}", popularity_score=80, category="attractions")
            for i in range(50)
        ]
        mock_load.return_value = {f"place_{i}": [0.5] * 768 for i in range(50)}
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=places, duration_days=7)
        result = await run_ranking_agent(state)

        assert len(result["candidate_places"]) <= MAX_TOTAL_CANDIDATES

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_agent_message_appended(self, mock_embed, mock_load):
        place = _make_place()
        mock_load.return_value = {"place_001": [0.5] * 768}
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        messages = result["agent_messages"]
        assert any("[RankingAgent]" in m for m in messages)

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_city_center_computed_from_non_hotel_places(self, mock_embed, mock_load):
        hotel = _make_place(id="h1", category="hotel", lat=35.0, lon=36.0)
        attraction = _make_place(id="a1", category="attractions", lat=30.0, lon=31.0)

        mock_load.return_value = {"h1": [0.5] * 768, "a1": [0.5] * 768}
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=[hotel, attraction])
        result = await run_ranking_agent(state)

        assert result["error"] is None
        assert len(result["candidate_places"]) >= 1

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_embedding_failure_fallback(self, mock_embed, mock_load):
        """When embed_query returns None, ranking should still work with fallback."""
        place = _make_place()
        mock_load.return_value = {"place_001": [0.5] * 768}
        mock_embed.return_value = None  # embedding failed

        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        assert len(result["candidate_places"]) == 1
        assert result["error"] is None

    @pytest.mark.asyncio
    @patch("ai_engine.agents.ranking_agent.load_place_embeddings", new_callable=AsyncMock)
    @patch("ai_engine.agents.ranking_agent.embed_query")
    async def test_missing_place_embeddings_fallback(self, mock_embed, mock_load):
        """When DB has no embeddings (empty dict), ranking uses fallback."""
        place = _make_place()
        mock_load.return_value = {}  # no embeddings in DB
        mock_embed.return_value = [0.5] * 768

        state = _make_ranking_state(filtered_places=[place])
        result = await run_ranking_agent(state)

        assert result["candidate_places"]
        assert result["error"] is None


# ── Helpers for ranking agent tests ───────────────────────────────────────────

_DEFAULT_RANKING_PROFILE = {
    "budget_level": "moderate",
    "travel_style": "cultural",
    "food_preferences": ["local cuisine"],
    "accommodation_preferences": ["hotel"],
    "interests": ["history", "art"],
    "pace": "balanced",
}


def _make_ranking_state(**overrides) -> dict:
    """State with profile pre-populated for ranking tests."""
    defaults = {
        "profile": dict(_DEFAULT_RANKING_PROFILE),
        "filtered_places": [],
        "destination_city": "Cairo",
    }
    defaults.update(overrides)
    return _make_state(**defaults)
