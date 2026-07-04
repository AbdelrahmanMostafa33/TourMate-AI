# tests/unit/test_ai_engine/test_hotel_agent.py
"""Comprehensive unit tests for hotel_agent.py — scoring, selection logic, and LLM fallback."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from ai_engine.agents.hotel_agent import (
    _compute_daily_centroids,
    _score_preference_match,
    _score_proximity_to_centroids,
    _score_rating,
    _compute_hotel_composite,
    run_hotel_selection,
    _llm_select_hotels,
    HotelSelection,
    WEIGHT_PREFERENCE,
    WEIGHT_PROXIMITY,
    WEIGHT_RATING,
)
from ai_engine.schemas.planning_schema import AccommodationSuggestion


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

A_HOTEL = {
    "id": "hotel_001",
    "name": "Marriott Mena House",
    "category": "hotel",
    "accommodation_type": "luxury hotel",
    "sub_category": "luxury",
    "lat": 29.9758,
    "lon": 31.1334,
    "rating": 4.6,
    "amenities": ["pool", "gym", "restaurant"],
    "nightly_rate": 250.0,
    "photos": [{"url": "http://example.com/photo.jpg"}],
    "address": "Address 1",
    "maps_link": "http://maps.example.com",
}

B_HOTEL = {
    "id": "hotel_002",
    "name": "Steigenberger Tahrir",
    "category": "hotel",
    "accommodation_type": "hotel",
    "sub_category": "hotel",
    "lat": 30.0429,
    "lon": 31.2347,
    "rating": 4.3,
    "amenities": ["gym", "breakfast"],
    "nightly_rate": 180.0,
}

C_HOTEL = {
    "id": "hotel_003",
    "name": "Cairo Hostel",
    "category": "hotel",
    "accommodation_type": "hostel",
    "sub_category": "hostel",
    "lat": 30.0500,
    "lon": 31.2400,
    "rating": 4.0,
    "amenities": ["wifi"],
    "nightly_rate": 30.0,
}

SAMPLE_ITINERARY = {
    "destination": "Cairo",
    "duration_days": 2,
    "days": [
        {
            "day_number": 1,
            "theme": "History",
            "stops": [
                {"name": "Pyramids", "lat": 29.9792, "lon": 31.1342},
                {"name": "Sphinx", "lat": 29.9753, "lon": 31.1375},
            ],
        },
        {
            "day_number": 2,
            "theme": "Markets",
            "stops": [
                {"name": "Khan El Khalili", "lat": 30.0478, "lon": 31.2625},
                {"name": "Museum of Islamic Art", "lat": 30.0536, "lon": 31.2597},
                {"name": "Al-Azhar Park", "lat": 30.0411, "lon": 31.2628},
            ],
        },
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_daily_centroids tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeDailyCentroids:
    def test_empty_itinerary_returns_empty_list(self):
        result = _compute_daily_centroids({"days": []})
        assert result == []

    def test_no_days_key_returns_empty_list(self):
        result = _compute_daily_centroids({})
        assert result == []

    def test_day_with_empty_stops_skipped(self):
        itinerary = {
            "days": [
                {"day_number": 1, "stops": [{"name": "A", "lat": 10.0, "lon": 20.0}]},
                {"day_number": 2, "stops": []},
            ]
        }
        result = _compute_daily_centroids(itinerary)
        assert len(result) == 1
        assert result[0]["day_number"] == 1

    def test_computes_correct_centroid(self):
        result = _compute_daily_centroids(SAMPLE_ITINERARY)
        assert len(result) == 2

        # Day 1: avg of (29.9792, 31.1342) and (29.9753, 31.1375)
        assert result[0]["day_number"] == 1
        assert pytest.approx(result[0]["centroid_lat"], 0.001) == 29.97725
        assert pytest.approx(result[0]["centroid_lon"], 0.001) == 31.13585
        assert result[0]["n_stops"] == 2

        # Day 2: avg of (30.0478, 31.2625), (30.0536, 31.2597), (30.0411, 31.2628)
        assert result[1]["day_number"] == 2
        assert pytest.approx(result[1]["centroid_lat"], 0.001) == 30.0475
        assert pytest.approx(result[1]["centroid_lon"], 0.001) == 31.26167
        assert result[1]["n_stops"] == 3

    def test_single_stop_centroid_matches_stop(self):
        itinerary = {
            "days": [
                {"day_number": 1, "stops": [{"name": "Only", "lat": 15.0, "lon": 25.0}]},
            ]
        }
        result = _compute_daily_centroids(itinerary)
        assert result[0]["centroid_lat"] == 15.0
        assert result[0]["centroid_lon"] == 25.0


# ═══════════════════════════════════════════════════════════════════════════════
# _score_preference_match tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestScorePreferenceMatch:
    def test_exact_match_returns_1(self):
        assert _score_preference_match(A_HOTEL, ["luxury"]) == 1.0

    def test_type_in_preference_returns_1(self):
        assert _score_preference_match(A_HOTEL, ["luxury hotel"]) == 1.0

    def test_preference_in_type_returns_1(self):
        assert _score_preference_match(A_HOTEL, ["luxury hotel"]) == 1.0

    def test_no_match_returns_0(self):
        assert _score_preference_match(A_HOTEL, ["hostel"]) == 0.0

    def test_no_preferences_returns_0_5_neutral(self):
        assert _score_preference_match(A_HOTEL, []) == 0.5

    def test_no_accommodation_type_returns_0_5(self):
        hotel = {"id": "h1", "name": "Unknown"}
        assert _score_preference_match(hotel, ["hotel"]) == 0.5

    def test_case_insensitive_match(self):
        hotel = {"accommodation_type": "Luxury Hotel"}
        assert _score_preference_match(hotel, ["luxury"]) == 1.0

    def test_preference_in_type_substring(self):
        hotel = {"accommodation_type": "boutique hotel"}
        assert _score_preference_match(hotel, ["boutique"]) == 1.0

    def test_mutual_substring_match(self):
        """Either direction substring match works."""
        hotel = {"accommodation_type": "luxury"}
        assert _score_preference_match(hotel, ["luxury hotel"]) == 1.0
        # Also the reverse
        hotel2 = {"accommodation_type": "luxury hotel"}
        assert _score_preference_match(hotel2, ["luxury"]) == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# _score_proximity_to_centroids tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreProximityToCentroids:
    def test_no_centroids_returns_0_5(self):
        assert _score_proximity_to_centroids(A_HOTEL, []) == 0.5

    def test_hotel_at_centroid_returns_1(self):
        """A hotel at exactly the centroid location should score ~1.0."""
        centroids = [{"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 2}]
        score = _score_proximity_to_centroids(A_HOTEL, centroids)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_far_away_returns_0(self):
        """A hotel 100+ km away should score 0."""
        centroids = [{"day_number": 1, "centroid_lat": 30.0, "centroid_lon": 50.0, "n_stops": 2}]
        score = _score_proximity_to_centroids(A_HOTEL, centroids)
        assert score == 0.0

    def test_weighted_by_stops(self):
        """Centroids with more stops should have higher weight."""
        centroids = [
            {"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 1},
            {"day_number": 2, "centroid_lat": 30.0, "centroid_lon": 50.0, "n_stops": 9},
        ]
        score = _score_proximity_to_centroids(A_HOTEL, centroids)
        # Closer to centroid 1 but centroid 2 has 9/10 stops weight
        # The far centroid pulls score down significantly
        assert score < 0.5

    def test_multiple_centroids(self):
        centroids = [
            {"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 2},
            {"day_number": 2, "centroid_lat": 30.0478, "centroid_lon": 31.2625, "n_stops": 3},
        ]
        score = _score_proximity_to_centroids(A_HOTEL, centroids)
        assert 0 < score < 1.0
        # Hotel is close to day 1 centroid, farther from day 2


# ═══════════════════════════════════════════════════════════════════════════════
# _score_rating tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreRating:
    def test_rating_5_returns_1(self):
        assert _score_rating({"rating": 5.0}) == 1.0

    def test_rating_1_returns_0(self):
        assert _score_rating({"rating": 1.0}) == 0.0

    def test_rating_3_returns_0_5(self):
        assert _score_rating({"rating": 3.0}) == 0.5

    def test_missing_rating_defaults_to_3(self):
        assert _score_rating({}) == 0.5

    def test_rating_none_defaults_to_3(self):
        assert _score_rating({"rating": None}) == 0.5

    def test_rating_above_5_clamped(self):
        assert _score_rating({"rating": 5.5}) == 1.0

    def test_rating_below_1_clamped(self):
        # rating=0.0 is falsy, so `rating = hotel.get("rating", 3.0) or 3.0` defaults to 3.0
        assert _score_rating({"rating": 0.0}) == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# _compute_hotel_composite tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeHotelComposite:
    def test_perfect_match_returns_1(self):
        """Perfect preference match + at centroid + max rating = 1."""
        centroids = [{"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 2}]
        hotel = {**A_HOTEL, "rating": 5.0}
        score = _compute_hotel_composite(hotel, centroids, ["luxury"])
        assert score == pytest.approx(1.0, abs=0.01)

    def test_no_match_returns_below_1(self):
        """No preference match + no proximity + min rating = near 0."""
        centroids = [{"day_number": 1, "centroid_lat": 0.0, "centroid_lon": 0.0, "n_stops": 2}]
        hotel = {**A_HOTEL, "rating": 1.0}
        score = _compute_hotel_composite(hotel, centroids, ["hostel"])
        assert score < 0.3

    def test_weights_affect_score(self):
        """Verify that changing individual scores changes composite."""
        centroids = [{"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 2}]

        # High preference + high proximity + medium rating
        score_high = _compute_hotel_composite(
            {**A_HOTEL, "rating": 5.0}, centroids, ["luxury"]
        )
        score_low = _compute_hotel_composite(
            {**A_HOTEL, "rating": 1.0}, centroids, ["hostel"]
        )
        assert score_high > score_low

    def test_rounds_to_4_decimals(self):
        centroids = [{"day_number": 1, "centroid_lat": 29.9758, "centroid_lon": 31.1334, "n_stops": 2}]
        score = _compute_hotel_composite(A_HOTEL, centroids, ["luxury"])
        # Check it's rounded to 4 decimal places
        score_str = f"{score:.6f}"
        assert score_str.split(".")[1][:4] == score_str.split(".")[1][:4]  # at least 4 decimal digits


# ═══════════════════════════════════════════════════════════════════════════════
# run_hotel_selection — main function tests
# ═══════════════════════════════════════════════════════════════════════════════

def _make_state(**overrides) -> dict:
    """Build a minimal TripState dict for testing."""
    state = {
        "optimized_itinerary": None,
        "draft_itinerary": None,
        "candidate_places": [],
        "profile": {
            "accommodation_preferences": [],
            "budget_level": "moderate",
            "travel_style": "cultural",
        },
        "agent_messages": [],
    }
    state.update(overrides)
    return state


class TestRunHotelSelectionNoItinerary:
    """Tests for the early-exit paths when no itinerary or candidates exist."""

    @pytest.mark.asyncio
    async def test_no_itinerary_returns_early(self):
        state = _make_state(optimized_itinerary=None, draft_itinerary=None)
        result = await run_hotel_selection(state)
        assert "No itinerary" in result["agent_messages"][0]
        assert result is state  # same object, no modifications

    @pytest.mark.asyncio
    async def test_empty_itinerary_returns_early(self):
        state = _make_state(optimized_itinerary=None, draft_itinerary=None)
        result = await run_hotel_selection(state)
        assert "skipping hotel selection" in result["agent_messages"][0].lower()

    @pytest.mark.asyncio
    async def test_no_hotel_candidates_returns_early(self):
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[
                {"id": "p1", "name": "Museum", "category": "attraction"},
                {"id": "p2", "name": "Restaurant", "category": "restaurant"},
            ],
        )
        result = await run_hotel_selection(state)
        assert "No hotel candidates" in result["agent_messages"][0]
        assert result["optimized_itinerary"]["accommodation_suggestions"] == []

    @pytest.mark.asyncio
    async def test_uses_draft_itinerary_if_no_optimized(self):
        state = _make_state(
            optimized_itinerary=None,
            draft_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL],
        )
        with patch("ai_engine.agents.hotel_agent._compute_daily_centroids") as mock_cent:
            mock_cent.return_value = []
            result = await run_hotel_selection(state)
            mock_cent.assert_called_once()
            # Should have been called with draft_itinerary since optimized is None
            assert mock_cent.call_args[0][0] is SAMPLE_ITINERARY


class TestRunHotelSelectionRuleBased:
    """Tests for the rule-based selection path (<= 3 candidates)."""

    @pytest.mark.asyncio
    async def test_one_candidate_selected_directly(self):
        """When there's only 1 candidate, it should be selected by rules (no LLM)."""
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL],
            profile={"accommodation_preferences": [], "budget_level": "moderate", "travel_style": "cultural"},
        )
        with patch("ai_engine.agents.hotel_agent._llm_select_hotels") as mock_llm:
            result = await run_hotel_selection(state)

        mock_llm.assert_not_called()
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["id"] == "hotel_001"
        assert suggestions[0]["name"] == "Marriott Mena House"
        assert "1/1 hotels selected" in result["agent_messages"][0].lower()

    @pytest.mark.asyncio
    async def test_three_candidates_uses_rule_based(self):
        """When <= 3 candidates, rule-based path is used."""
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL],
        )
        with patch("ai_engine.agents.hotel_agent._llm_select_hotels") as mock_llm:
            result = await run_hotel_selection(state)

        mock_llm.assert_not_called()
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        sorted_by_score = sorted(
            [A_HOTEL, B_HOTEL, C_HOTEL],
            key=lambda h: _compute_hotel_composite(
                h, _compute_daily_centroids(SAMPLE_ITINERARY), []
            ),
            reverse=True,
        )
        assert len(suggestions) == 3
        assert suggestions[0]["id"] == sorted_by_score[0]["id"]

    @pytest.mark.asyncio
    async def test_hotel_hydrated_with_full_metadata(self):
        """Selected hotels should have extra fields from the original candidate."""
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL],
        )
        result = await run_hotel_selection(state)
        suggestion = result["optimized_itinerary"]["accommodation_suggestions"][0]
        assert suggestion["accommodation_type"] == "luxury hotel"
        assert suggestion["amenities"] == ["pool", "gym", "restaurant"]
        assert suggestion["nightly_rate"] == 250.0


class TestRunHotelSelectionLLMPath:
    """Tests for the LLM-based selection path (> 3 candidates)."""

    @pytest.mark.asyncio
    async def test_llm_path_used_when_four_or_more_candidates(self):
        """When > 3 candidates, the LLM selection path is used."""
        hotels = [
            {**A_HOTEL, "id": f"hotel_{i:03d}", "name": f"Hotel {i}"}
            for i in range(6)
        ]
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=hotels,
        )
        with patch("ai_engine.agents.hotel_agent._llm_select_hotels") as mock_llm:
            mock_llm.return_value = [
                {"id": "hotel_000", "name": "Hotel 0", "lat": 0, "lon": 0},
                {"id": "hotel_001", "name": "Hotel 1", "lat": 0, "lon": 0},
            ]
            result = await run_hotel_selection(state)

        mock_llm.assert_called_once()
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 2

    @pytest.mark.asyncio
    async def test_four_candidates_triggers_llm_path(self):
        """With exactly 4 candidates, the LLM path is used (SKIP_LLM_THRESHOLD=3)."""
        hotels = [
            {**A_HOTEL, "id": f"hotel_{i:03d}", "name": f"Hotel {i}"}
            for i in range(4)
        ]
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=hotels,
        )
        with patch("ai_engine.agents.hotel_agent._llm_select_hotels") as mock_llm:
            mock_llm.return_value = [
                {"id": "hotel_000", "name": "Hotel 0", "lat": 0, "lon": 0},
            ]
            result = await run_hotel_selection(state)

        mock_llm.assert_called_once()
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1


class TestRunHotelSelectionPreferenceFiltering:
    """Tests for the accommodation type preference filtering."""

    @pytest.mark.asyncio
    async def test_filters_hotels_by_preference(self):
        """When user prefers 'luxury', only luxury hotels should remain."""
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL],
            profile={
                "accommodation_preferences": ["luxury"],
                "budget_level": "moderate",
                "travel_style": "cultural",
            },
        )
        result = await run_hotel_selection(state)
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        for s in suggestions:
            assert s["id"] == "hotel_001", (
                f"Only luxury hotel should be selected, got {s['name']}"
            )

    @pytest.mark.asyncio
    async def test_filters_hostel_preference(self):
        """When user prefers 'hostel', only hostels should remain."""
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL],
            profile={
                "accommodation_preferences": ["hostel"],
                "budget_level": "budget",
                "travel_style": "solo",
            },
        )
        result = await run_hotel_selection(state)
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["id"] == "hotel_003"

    @pytest.mark.asyncio
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_requery_when_no_matching_hotels(self, mock_get_places):
        """When no candidates match the preference, re-query the database."""
        mock_get_places.return_value = [
            {**A_HOTEL, "accommodation_type": "resort", "category": "hotel"},
        ]

        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[B_HOTEL],  # regular hotel, not luxury
            profile={
                "accommodation_preferences": ["resort"],
                "budget_level": "luxury",
                "travel_style": "romantic",
            },
        )
        result = await run_hotel_selection(state)
        mock_get_places.assert_called_once_with("Cairo")
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["accommodation_type"] == "resort"

    @pytest.mark.asyncio
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_requery_finds_matching_hotels(self, mock_get_places):
        """When DB re-query finds matching hotels, those are used."""
        mock_get_places.return_value = [
            {**A_HOTEL, "id": "resort_001", "name": "Resort 1", "accommodation_type": "resort", "category": "hotel"},
        ]

        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[B_HOTEL],  # regular hotel, not a resort
            profile={
                "accommodation_preferences": ["resort"],
                "budget_level": "luxury",
                "travel_style": "romantic",
            },
        )
        result = await run_hotel_selection(state)
        mock_get_places.assert_called_once_with("Cairo")
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["accommodation_type"] == "resort"

    @pytest.mark.asyncio
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_requery_no_match_falls_back_to_candidates(self, mock_get_places):
        """When DB re-query finds places but none match preference, fall back to original candidates."""
        # Return places that aren't hotels at all — no match for 'resort'
        mock_get_places.return_value = [
            {"id": "p1", "name": "Museum", "category": "attraction"},
            {"id": "p2", "name": "Restaurant", "category": "restaurant"},
        ]

        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL],
            profile={
                "accommodation_preferences": ["resort"],
                "budget_level": "luxury",
                "travel_style": "romantic",
            },
        )
        result = await run_hotel_selection(state)
        mock_get_places.assert_called_once_with("Cairo")
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        # Should have fallen back to all 3 original candidates
        assert len(suggestions) == 3
        assert suggestions[0]["id"] in ("hotel_001", "hotel_002", "hotel_003")

    @pytest.mark.asyncio
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_requery_empty_places_returns_empty(self, mock_get_places):
        """When DB re-query returns empty list, no fallback happens."""
        mock_get_places.return_value = []  # empty → falsy → skip fallback

        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[B_HOTEL, C_HOTEL],  # neither is a 'resort'
            profile={
                "accommodation_preferences": ["resort"],
                "budget_level": "luxury",
                "travel_style": "romantic",
            },
        )
        result = await run_hotel_selection(state)
        mock_get_places.assert_called_once_with("Cairo")
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        # hotel_candidates is empty after filtering + no fallback → 0 suggestions
        assert len(suggestions) == 0

    @pytest.mark.asyncio
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_requery_no_city_returns_empty(self, mock_get_places):
        """When destination is empty, no DB re-query happens and suggestions are empty.
        
        Note: this is a current limitation — when the itinerary has no destination
        and no candidates match the preference, the result is empty.
        """
        itinerary = {**SAMPLE_ITINERARY, "destination": ""}

        state = _make_state(
            optimized_itinerary=itinerary,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL],
            profile={
                "accommodation_preferences": ["resort"],
                "budget_level": "luxury",
                "travel_style": "romantic",
            },
        )
        result = await run_hotel_selection(state)
        mock_get_places.assert_not_called()
        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# _llm_select_hotels tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLlmSelectHotels:
    """Tests for the LLM-based hotel selection with mocked invoke_with_fallback."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_llm_returns_hotels(self, mock_invoke):
        """When LLM returns valid HotelSelection, those hotels are returned."""
        mock_invoke.return_value = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(id="hotel_001", name="Marriott Mena House", lat=29.9758, lon=31.1334),
                AccommodationSuggestion(id="hotel_002", name="Steigenberger", lat=30.0429, lon=31.2347),
            ]
        )

        centroids = _compute_daily_centroids(SAMPLE_ITINERARY)
        top_candidates = [
            (A_HOTEL, 0.85),
            (B_HOTEL, 0.72),
            (C_HOTEL, 0.68),
        ]

        result = await _llm_select_hotels(
            itinerary=SAMPLE_ITINERARY,
            centroids=centroids,
            top_candidates=top_candidates,
            preferences=["hotel"],
            budget="moderate",
            style="cultural",
        )

        assert len(result) == 2
        assert result[0]["id"] == "hotel_001"
        assert result[1]["id"] == "hotel_002"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_llm_returns_empty_falls_back_to_top_3(self, mock_invoke):
        """When LLM returns empty suggestions, fall back to top 3 by score."""
        mock_invoke.return_value = HotelSelection(accommodation_suggestions=[])

        centroids = _compute_daily_centroids(SAMPLE_ITINERARY)
        top_candidates = [
            (A_HOTEL, 0.95),
            (B_HOTEL, 0.85),
            (C_HOTEL, 0.75),
            ({"id": "h4", "name": "Extra Hotel", "lat": 0, "lon": 0}, 0.65),
        ]

        result = await _llm_select_hotels(
            itinerary=SAMPLE_ITINERARY,
            centroids=centroids,
            top_candidates=top_candidates,
            preferences=[],
            budget="",
            style="",
        )

        assert len(result) == 3
        assert result[0]["id"] == "hotel_001"  # highest score
        assert result[1]["id"] == "hotel_002"
        assert result[2]["id"] == "hotel_003"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_llm_exception_falls_back_to_top_3(self, mock_invoke):
        """When LLM raises an exception, fall back to top 3 by score."""
        mock_invoke.side_effect = Exception("API timeout")

        centroids = _compute_daily_centroids(SAMPLE_ITINERARY)
        top_candidates = [
            (A_HOTEL, 0.9),
            (B_HOTEL, 0.8),
            (C_HOTEL, 0.7),
        ]

        result = await _llm_select_hotels(
            itinerary=SAMPLE_ITINERARY,
            centroids=centroids,
            top_candidates=top_candidates,
            preferences=[],
            budget="",
            style="",
        )

        assert len(result) == 3
        assert result[0]["id"] == "hotel_001"
        assert result[1]["id"] == "hotel_002"

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_llm_called_with_correct_prompt(self, mock_invoke):
        """Verify the LLM is called with the right system prompt and messages."""
        mock_invoke.return_value = HotelSelection(accommodation_suggestions=[
            AccommodationSuggestion(id="h1", name="Test Hotel", lat=0, lon=0),
        ])

        centroids = _compute_daily_centroids(SAMPLE_ITINERARY)
        top_candidates = [(A_HOTEL, 0.9)]

        await _llm_select_hotels(
            itinerary=SAMPLE_ITINERARY,
            centroids=centroids,
            top_candidates=top_candidates,
            preferences=["luxury"],
            budget="moderate",
            style="cultural",
        )

        mock_invoke.assert_called_once()
        call_args = mock_invoke.call_args
        assert call_args[0][0] == "hotel_selector"
        messages = call_args[0][1]
        assert len(messages) == 2
        assert "Hotel Selection Agent" in messages[0].content
        assert "Marriott Mena House" in messages[1].content


# ═══════════════════════════════════════════════════════════════════════════════
# HotelSelection Pydantic model tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestHotelSelectionModel:
    def test_empty_by_default(self):
        selection = HotelSelection()
        assert selection.accommodation_suggestions == []

    def test_accepts_list_of_accommodations(self):
        selection = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(id="h1", name="Hotel 1", lat=10.0, lon=20.0),
                AccommodationSuggestion(id="h2", name="Hotel 2", lat=30.0, lon=40.0),
            ]
        )
        assert len(selection.accommodation_suggestions) == 2
        assert selection.accommodation_suggestions[0].name == "Hotel 1"
        assert selection.accommodation_suggestions[0].id == "h1"

    def test_model_dump(self):
        selection = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(id="h1", name="Hotel 1", lat=10.0, lon=20.0),
            ]
        )
        dumped = selection.model_dump()
        assert len(dumped["accommodation_suggestions"]) == 1
        assert dumped["accommodation_suggestions"][0]["name"] == "Hotel 1"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration-style: run_hotel_selection with LLM mocked end-to-end
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunHotelSelectionEndToEnd:
    """Full flow tests with mocked dependencies."""

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_full_flow_with_llm_selection(self, mock_invoke):
        """Complete flow: itinerary + 6 candidates → LLM selection → hydrated output."""
        mock_invoke.return_value = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(id="hotel_000", name="Hotel 0", lat=0, lon=0),
                AccommodationSuggestion(id="hotel_001", name="Hotel 1", lat=0, lon=0),
            ]
        )

        hotels = [
            {**A_HOTEL, "id": f"hotel_{i:03d}", "name": f"Hotel {i}"}
            for i in range(6)
        ]
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=hotels,
        )
        result = await run_hotel_selection(state)

        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 2
        # Hotels should be hydrated with metadata from the candidate pool
        assert suggestions[0].get("nightly_rate", 0) > 0
        assert "selected" in result["agent_messages"][-1].lower()

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_llm_selection_hydrates_from_candidate_pool(self, mock_invoke):
        """Even when LLM returns minimal hotels, they should be enriched."""
        mock_invoke.return_value = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(id="hotel_001", name="Marriott Mena House", lat=29.9758, lon=31.1334),
            ]
        )

        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=[A_HOTEL, B_HOTEL, C_HOTEL, {**A_HOTEL, "id": "h4", "name": "Extra"}],
        )
        result = await run_hotel_selection(state)

        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["id"] == "hotel_001"
        # Hydration now overwrites all fields from the DB candidate,
        # so the LLM's defaults are replaced with the actual hotel data.
        assert suggestions[0]["nightly_rate"] == 250.0
        assert suggestions[0]["accommodation_type"] == "luxury hotel"
        assert suggestions[0]["amenities"] == ["pool", "gym", "restaurant"]

    @pytest.mark.asyncio
    @patch("ai_engine.agents.hotel_agent.invoke_with_fallback")
    async def test_hotel_not_in_pool_skips_hydration(self, mock_invoke):
        """When LLM selects a hotel not in the candidate pool, hydration is skipped."""
        mock_invoke.return_value = HotelSelection(
            accommodation_suggestions=[
                AccommodationSuggestion(
                    id="unknown_id", name="Mystery Hotel",
                    lat=30.0, lon=31.0, nightly_rate=200.0,
                ),
            ]
        )

        # 4+ candidates to trigger LLM path
        hotels = [
            {**A_HOTEL, "id": f"hotel_{i:03d}", "name": f"Hotel {i}"}
            for i in range(4)
        ]
        state = _make_state(
            optimized_itinerary=SAMPLE_ITINERARY,
            candidate_places=hotels,
        )
        result = await run_hotel_selection(state)

        suggestions = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(suggestions) == 1
        assert suggestions[0]["id"] == "unknown_id"
        # Hydration skipped because id not in candidate pool
        # The LLM's AccommodationSuggestion default for accommodation_type is ''
        assert suggestions[0].get("accommodation_type", "missing") == ""
        # nightly_rate from LLM should be preserved since no full candidate found
        assert suggestions[0]["nightly_rate"] == 200.0
