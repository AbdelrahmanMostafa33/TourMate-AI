"""
Unit tests for the Hotel Agent.

Tests cover:
    - _compute_daily_centroids(): computes geographic centroids from stops
    - _score_preference_match(): accommodation_type vs user preferences
    - _score_proximity_to_centroids(): distance-weighted proximity scoring
    - _score_rating(): normalizes ratings 1–5 → 0–1
    - _compute_hotel_composite(): composite score with all factors
    - run_hotel_selection(): edge cases (no itinerary, no candidates, rule-based)
    - run_hotel_selection(): LLM path with fallback on failure
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ai_engine.agents.hotel_agent import (
    _compute_daily_centroids,
    _score_preference_match,
    _score_proximity_to_centroids,
    _score_rating,
    _compute_hotel_composite,
    run_hotel_selection,
    WEIGHT_PREFERENCE,
    WEIGHT_PROXIMITY,
    WEIGHT_RATING,
)
from tests.unit.test_ai_engine.conftest import _make_state, _make_hotel, _make_place


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


def _make_hotel_candidate(**overrides) -> dict:
    """Create a hotel candidate dict as the Candidate Scorer would produce."""
    base = {
        "id": "hotel_001",
        "name": "Grand Nile Hotel",
        "category": "hotel",
        "sub_category": "luxury hotel",
        "accommodation_type": "hotel",
        "lat": 30.05,
        "lon": 31.24,
        "rating": 4.5,
        "popularity_score": 80,
        "amenities": ["wifi", "pool", "spa"],
        "photos": ["http://example.com/hotel.jpg"],
        "address": "1 Nile Corniche",
        "maps_link": "http://maps.example.com/hotel",
    }
    base.update(overrides)
    return base


def _make_2day_itinerary() -> dict:
    """Create a 2-day itinerary with 2 stops per day."""
    return {
        "destination": "Cairo",
        "duration_days": 2,
        "days": [
            {
                "day_number": 1,
                "theme": "Historic Cairo",
                "stops": [
                    {
                        "id": "place_001",
                        "name": "Egyptian Museum",
                        "lat": 30.0478,
                        "lon": 31.2336,
                    },
                    {
                        "id": "place_002",
                        "name": "Khan El Khalili",
                        "lat": 30.0478,
                        "lon": 31.2620,
                    },
                ],
            },
            {
                "day_number": 2,
                "theme": "Pyramids Day",
                "stops": [
                    {
                        "id": "place_003",
                        "name": "Pyramids of Giza",
                        "lat": 29.9792,
                        "lon": 31.1342,
                    },
                ],
            },
        ],
        "accommodation_suggestions": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
# _compute_daily_centroids Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeDailyCentroids:

    def test_computes_centroid_for_each_day(self):
        """Returns one centroid entry per day with stops."""
        itinerary = _make_2day_itinerary()
        centroids = _compute_daily_centroids(itinerary)

        assert len(centroids) == 2
        assert centroids[0]["day_number"] == 1
        assert centroids[1]["day_number"] == 2

    def test_centroid_averages_coordinates(self):
        """Centroid lat/lon is the average of all stop coordinates in a day."""
        itinerary = _make_2day_itinerary()
        centroids = _compute_daily_centroids(itinerary)

        # Day 1: (30.0478 + 30.0478) / 2 = 30.0478
        assert centroids[0]["centroid_lat"] == pytest.approx(30.0478, abs=0.001)
        # Day 1: (31.2336 + 31.2620) / 2 = 31.2478
        assert centroids[0]["centroid_lon"] == pytest.approx(31.2478, abs=0.001)
        assert centroids[0]["n_stops"] == 2

        # Day 2: single stop
        assert centroids[1]["centroid_lat"] == pytest.approx(29.9792, abs=0.001)
        assert centroids[1]["centroid_lon"] == pytest.approx(31.1342, abs=0.001)
        assert centroids[1]["n_stops"] == 1

    def test_skips_days_with_no_stops(self):
        """Days with empty stops list are skipped."""
        itinerary = {
            "days": [
                {"day_number": 1, "stops": []},
                {"day_number": 2, "stops": [{"lat": 30.0, "lon": 31.0}]},
            ]
        }
        centroids = _compute_daily_centroids(itinerary)
        assert len(centroids) == 1
        assert centroids[0]["day_number"] == 2

    def test_returns_empty_list_without_days(self):
        """Itinerary missing 'days' key returns empty list."""
        centroids = _compute_daily_centroids({})
        assert centroids == []

    def test_handles_missing_lat_lon(self):
        """Stops missing lat/lon default to 0.0 without crashing."""
        itinerary = {
            "days": [
                {"day_number": 1, "stops": [{"id": "x"}, {"id": "y", "lat": 10.0, "lon": 20.0}]},
            ]
        }
        centroids = _compute_daily_centroids(itinerary)
        # (0 + 10) / 2 = 5.0, (0 + 20) / 2 = 10.0
        assert centroids[0]["centroid_lat"] == 5.0
        assert centroids[0]["centroid_lon"] == 10.0


# ═══════════════════════════════════════════════════════════════════════════
# _score_preference_match Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScorePreferenceMatch:

    def test_exact_match_returns_1(self):
        """Same accommodation_type as preference → 1.0."""
        hotel = _make_hotel_candidate(accommodation_type="luxury")
        assert _score_preference_match(hotel, ["luxury"]) == 1.0

    def test_partial_match_returns_1(self):
        """Keyword contained in hotel type → 1.0."""
        hotel = _make_hotel_candidate(accommodation_type="boutique hotel")
        assert _score_preference_match(hotel, ["boutique"]) == 1.0

    def test_no_match_returns_0(self):
        """No overlap between preference and hotel type → 0.0."""
        hotel = _make_hotel_candidate(accommodation_type="hostel")
        assert _score_preference_match(hotel, ["luxury", "resort"]) == 0.0

    def test_no_preferences_returns_neutral(self):
        """Empty preference list → 0.5 (neutral)."""
        hotel = _make_hotel_candidate(accommodation_type="hotel")
        assert _score_preference_match(hotel, []) == 0.5

    def test_no_hotel_type_returns_neutral(self):
        """Missing accommodation_type on hotel → 0.5 (neutral)."""
        hotel = _make_hotel_candidate(accommodation_type="")
        assert _score_preference_match(hotel, ["hotel"]) == 0.5

    def test_case_insensitive_match(self):
        """Matching is case-insensitive."""
        hotel = _make_hotel_candidate(accommodation_type="RESORT")
        assert _score_preference_match(hotel, ["resort"]) == 1.0

    def test_first_preference_wins(self):
        """Match on the first preference returns 1.0 before checking others."""
        hotel = _make_hotel_candidate(accommodation_type="hostel")
        assert _score_preference_match(hotel, ["hostel", "luxury"]) == 1.0

    def test_strip_whitespace(self):
        """Whitespace in preference strings is stripped."""
        hotel = _make_hotel_candidate(accommodation_type="  resort  ")
        assert _score_preference_match(hotel, ["resort"]) == 1.0

    def test_preference_in_hotel_type(self):
        """Preference is a substring of hotel accommodation_type → match."""
        hotel = _make_hotel_candidate(accommodation_type="luxury resort")
        assert _score_preference_match(hotel, ["luxury"]) == 1.0


# ═══════════════════════════════════════════════════════════════════════════
# _score_proximity_to_centroids Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreProximityToCentroids:

    def test_same_location_returns_high_score(self):
        """Hotel at the same location as a centroid → close to 1.0."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(lat=30.05, lon=31.24)
        score = _score_proximity_to_centroids(hotel, centroids)
        assert score > 0.95

    def test_far_location_returns_low_score(self):
        """Hotel 100 km from centroid → close to 0.0."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(lat=31.0, lon=32.0)  # ~120 km away
        score = _score_proximity_to_centroids(hotel, centroids)
        assert score < 0.1

    def test_weights_by_stop_count(self):
        """Days with more stops get higher weight in the average."""
        centroids = [
            {"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 5},  # many stops
            {"centroid_lat": 29.98, "centroid_lon": 31.13, "n_stops": 1},  # few stops
        ]
        hotel = _make_hotel_candidate(lat=30.05, lon=31.24)  # right on first centroid
        score = _score_proximity_to_centroids(hotel, centroids)
        # Strongly weighted toward first centroid (5/6 weight)
        assert score > 0.7

    def test_empty_centroids_returns_neutral(self):
        """No centroids → 0.5 (neutral)."""
        hotel = _make_hotel_candidate()
        assert _score_proximity_to_centroids(hotel, []) == 0.5


# ═══════════════════════════════════════════════════════════════════════════
# _score_rating Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreRating:

    def test_rating_5_returns_1(self):
        """Highest rating → 1.0."""
        assert _score_rating({"rating": 5.0}) == 1.0

    def test_rating_1_returns_0(self):
        """Lowest rating → 0.0."""
        assert _score_rating({"rating": 1.0}) == 0.0

    def test_rating_3_returns_0_5(self):
        """Mid rating → ~0.5."""
        assert _score_rating({"rating": 3.0}) == 0.5

    def test_missing_rating_defaults_to_3(self):
        """No rating key → defaults to 3.0 → 0.5."""
        assert _score_rating({}) == 0.5

    def test_none_rating_defaults_to_3(self):
        """None rating → defaults to 3.0 → 0.5."""
        assert _score_rating({"rating": None}) == 0.5

    def test_clamps_above_5(self):
        """Ratings above 5 get clamped to 1.0."""
        assert _score_rating({"rating": 5.5}) == 1.0

    def test_clamps_below_1(self):
        """Ratings below 1 get clamped to 0.0."""
        assert _score_rating({"rating": 0.5}) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# _compute_hotel_composite Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestComputeHotelComposite:

    def test_perfect_match_returns_1(self):
        """All factors maximized → score = weight sum = 1.0."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(
            lat=30.05, lon=31.24, accommodation_type="boutique hotel", rating=5.0,
        )
        score = _compute_hotel_composite(hotel, centroids, ["boutique"])
        assert score == pytest.approx(1.0, abs=0.01)

    def test_no_match_low_rating_far_away_returns_low(self):
        """No preference match, low rating, far → score near 0."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(
            lat=31.0, lon=32.0, accommodation_type="hostel", rating=1.0,
        )
        score = _compute_hotel_composite(hotel, centroids, ["luxury"])
        assert score < 0.3

    def test_uses_correct_weights(self):
        """Composite = pref*0.35 + prox*0.40 + rating*0.25."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(
            lat=30.05, lon=31.24, accommodation_type="resort", rating=4.0,
        )
        pref = _score_preference_match(hotel, ["resort"])
        prox = _score_proximity_to_centroids(hotel, centroids)
        rat = _score_rating(hotel)
        expected = pref * WEIGHT_PREFERENCE + prox * WEIGHT_PROXIMITY + rat * WEIGHT_RATING
        assert _compute_hotel_composite(hotel, centroids, ["resort"]) == pytest.approx(expected, abs=0.001)

    def test_no_preferences_uses_neutral(self):
        """Empty preferences → 0.5 for preference factor."""
        centroids = [{"centroid_lat": 30.05, "centroid_lon": 31.24, "n_stops": 2}]
        hotel = _make_hotel_candidate(lat=30.05, lon=31.24, rating=3.0)
        score = _compute_hotel_composite(hotel, centroids, [])
        # pref=0.5, prox≈1.0, rating=0.5
        assert 0.5 < score < 0.9


# ═══════════════════════════════════════════════════════════════════════════
# run_hotel_selection Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRunHotelSelectionEdgeCases:

    @pytest.mark.asyncio
    async def test_no_itinerary_returns_early(self):
        """State with no itinerary → early return with log message."""
        state = _make_state()
        result = await run_hotel_selection(state)

        # No itinerary was created
        assert result.get("optimized_itinerary") is None
        assert result.get("draft_itinerary") is None
        # Agent message logged
        assert any("[HotelAgent] No itinerary" in m for m in result.get("agent_messages", []))

    @pytest.mark.asyncio
    async def test_no_hotel_candidates_sets_empty(self):
        """State with itinerary but no hotel candidates → empty list."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[],  # no hotels
        )
        result = await run_hotel_selection(state)

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert hotels == []
        assert any("No hotel candidates" in m for m in result.get("agent_messages", []))

    @pytest.mark.asyncio
    async def test_no_candidate_places_key_sets_empty(self):
        """State missing candidate_places key → empty list (no crash)."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
        )
        state.pop("candidate_places", None)
        result = await run_hotel_selection(state)

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert hotels == []

    @pytest.mark.asyncio
    async def test_non_hotel_candidates_ignored(self):
        """Only places with category='hotel' are considered."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_place(id="attraction_001", category="attractions"),
                _make_hotel_candidate(id="hotel_001"),
            ],
        )
        result = await run_hotel_selection(state)
        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 1
        assert hotels[0]["id"] == "hotel_001"

    @pytest.mark.asyncio
    async def test_uses_optimized_itinerary_when_available(self):
        """Prefers optimized_itinerary over draft_itinerary."""
        optimized = _make_2day_itinerary()
        draft = _make_2day_itinerary()
        draft["days"] = []  # different from optimized

        state = _make_state(
            optimized_itinerary=optimized,
            draft_itinerary=draft,
            candidate_places=[_make_hotel_candidate()],
        )
        result = await run_hotel_selection(state)
        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 1


# ═══════════════════════════════════════════════════════════════════════════
# run_hotel_selection Rule-based Path Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRunHotelSelectionRuleBased:

    @pytest.mark.asyncio
    async def test_rule_based_with_2_candidates_returns_both(self):
        """≤3 candidates → rule-based path (no LLM), returns all candidates."""
        # Use empty accommodation preferences so all candidates pass through
        # (the filter only activates when a preference is set)
        from tests.unit.test_ai_engine.conftest import _make_profile
        profile = _make_profile(accommodation_preferences=[])

        state = _make_state(
            profile=profile,
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Hotel A", accommodation_type="resort", rating=4.5),
                _make_hotel_candidate(id="hotel_002", name="Hotel B", accommodation_type="hostel", rating=4.0),
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_llm:
            result = await run_hotel_selection(state)

        # LLM should NOT be called in rule-based path
        mock_llm.assert_not_called()

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 2
        # hotel_001 (higher rating) → higher composite score → first
        assert hotels[0]["id"] == "hotel_001"
        assert hotels[1]["id"] == "hotel_002"

    @pytest.mark.asyncio
    async def test_rule_based_includes_all_required_fields(self):
        """Rule-based path returns hotels with all required fields."""
        from tests.unit.test_ai_engine.conftest import _make_profile
        state = _make_state(
            profile=_make_profile(accommodation_preferences=[]),
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(
                    id="hotel_001",
                    name="Grand Nile Hotel",
                    accommodation_type="luxury",
                    lat=30.05,
                    lon=31.24,
                    rating=4.5,
                    amenities=["wifi", "pool"],
                ),
            ],
        )
        result = await run_hotel_selection(state)
        hotel = result["optimized_itinerary"]["accommodation_suggestions"][0]

        assert hotel["id"] == "hotel_001"
        assert hotel["name"] == "Grand Nile Hotel"
        assert hotel["accommodation_type"] == "luxury"
        assert hotel["lat"] == 30.05
        assert hotel["lon"] == 31.24
        assert hotel["rating"] == 4.5
        assert hotel["amenities"] == ["wifi", "pool"]
        assert "why_recommended" in hotel

    @pytest.mark.asyncio
    async def test_rule_based_sorts_by_composite_score(self):
        """Rule-based path returns hotels sorted by composite score descending."""
        from tests.unit.test_ai_engine.conftest import _make_profile
        profile = _make_profile(accommodation_preferences=[])

        state = _make_state(
            profile=profile,
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Best Hotel", rating=5.0, accommodation_type="hotel"),
                _make_hotel_candidate(id="hotel_002", name="Worst Hotel", rating=1.0, accommodation_type="hostel"),
                _make_hotel_candidate(id="hotel_003", name="Mid Hotel", rating=3.0, accommodation_type="hotel"),
            ],
        )
        result = await run_hotel_selection(state)
        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        # All 3 should be returned (≤3 threshold)
        assert len(hotels) == 3
        # First should be highest rated
        assert hotels[0]["id"] == "hotel_001"
        assert hotels[2]["id"] == "hotel_002"

    @pytest.mark.asyncio
    async def test_rule_based_sets_why_recommended(self):
        """Each hotel gets a why_recommended explanation in rule-based path."""
        from tests.unit.test_ai_engine.conftest import _make_profile
        state = _make_state(
            profile=_make_profile(accommodation_preferences=[]),
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Hotel A", accommodation_type="resort"),
            ],
        )
        result = await run_hotel_selection(state)
        hotel = result["optimized_itinerary"]["accommodation_suggestions"][0]
        assert "resort" in hotel["why_recommended"].lower() or "accommodation" in hotel["why_recommended"].lower()


# ═══════════════════════════════════════════════════════════════════════════
# run_hotel_selection LLM Fallback Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRunHotelSelectionLLM:

    @pytest.mark.asyncio
    async def test_more_than_3_candidates_triggers_llm(self):
        """>3 candidates → LLM path is invoked."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id=f"hotel_{i:03d}", name=f"Hotel {i}",
                                      rating=4.0 + (i % 5) * 0.2,
                                      accommodation_type="hotel")
                for i in range(6)
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_llm:
            mock_response = MagicMock()
            mock_response.accommodation_suggestions = []
            mock_llm.return_value = mock_response

            result = await run_hotel_selection(state)

        # LLM should have been called
        mock_llm.assert_called_once()
        assert "hotel_selector" in str(mock_llm.call_args)

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_rule_based(self):
        """When LLM raises an exception → fallback to top 3 by composite score."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id=f"hotel_{i:03d}", name=f"Hotel {i}",
                                      rating=4.5, accommodation_type="hotel")
                for i in range(6)
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback", side_effect=Exception("API error")):
            result = await run_hotel_selection(state)

        # Should fallback to top 3 by composite score
        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 3
        assert "why_recommended" in hotels[0]

    @pytest.mark.asyncio
    async def test_llm_empty_response_falls_back(self):
        """When LLM returns empty selection → fallback to top 3 by composite score."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id=f"hotel_{i:03d}", name=f"Hotel {i}",
                                      rating=4.0 + i * 0.1, accommodation_type="hotel")
                for i in range(6)
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_llm:
            mock_response = MagicMock()
            mock_response.accommodation_suggestions = []
            mock_llm.return_value = mock_response

            result = await run_hotel_selection(state)

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 3

    @pytest.mark.asyncio
    async def test_llm_success_uses_structured_output(self):
        """Successful LLM response uses AccommodationSuggestion model output."""
        from ai_engine.schemas.planning_schema import AccommodationSuggestion
        from tests.unit.test_ai_engine.conftest import _make_profile

        # Use empty preferences so all candidates pass the filter
        profile = _make_profile(accommodation_preferences=[])

        state = _make_state(
            profile=profile,
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Hotel A",
                                      accommodation_type="luxury", rating=4.5),
                _make_hotel_candidate(id="hotel_002", name="Hotel B",
                                      accommodation_type="resort", rating=4.3),
                _make_hotel_candidate(id="hotel_003", name="Hotel C",
                                      accommodation_type="boutique", rating=4.0),
                _make_hotel_candidate(id="hotel_004", name="Hotel D",
                                      accommodation_type="hotel", rating=3.8),
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_llm:
            mock_response = MagicMock()
            mock_response.accommodation_suggestions = [
                AccommodationSuggestion(
                    id="hotel_001", name="Hotel A", sub_category="luxury",
                    accommodation_type="luxury", lat=30.05, lon=31.24,
                    why_recommended="Best luxury option", rating=4.5,
                ),
                AccommodationSuggestion(
                    id="hotel_002", name="Hotel B", sub_category="resort",
                    accommodation_type="resort", lat=30.04, lon=31.23,
                    why_recommended="Great resort option", rating=4.3,
                ),
            ]
            mock_llm.return_value = mock_response

            result = await run_hotel_selection(state)

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        assert len(hotels) == 2
        assert hotels[0]["name"] == "Hotel A"
        assert hotels[1]["why_recommended"] == "Great resort option"

    @pytest.mark.asyncio
    async def test_hydration_adds_fields_from_candidates(self):
        """After LLM selection, hotels are enriched with full metadata."""
        from ai_engine.schemas.planning_schema import AccommodationSuggestion

        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Hotel A",
                                      accommodation_type="hotel", rating=4.5,
                                      amenities=["wifi", "pool"],
                                      address="123 Street",
                                      photos=["http://example.com/photo.jpg"]),
                _make_hotel_candidate(id="hotel_002", name="Hotel B",
                                      accommodation_type="hotel", rating=4.0,
                                      amenities=["wifi"],
                                      address="456 Road",
                                      photos=["http://example.com/photo2.jpg"]),
                _make_hotel_candidate(id="hotel_003", name="Hotel C",
                                      accommodation_type="hotel", rating=3.5,
                                      amenities=[], address="789 Ave"),
            ],
        )
        with patch("ai_engine.agents.hotel_agent.invoke_with_fallback") as mock_llm:
            mock_response = MagicMock()
            mock_response.accommodation_suggestions = [
                AccommodationSuggestion(id="hotel_001", name="Hotel A",
                                        accommodation_type="hotel",
                                        lat=30.05, lon=31.24, rating=4.5),
                AccommodationSuggestion(id="hotel_002", name="Hotel B",
                                        accommodation_type="hotel",
                                        lat=30.04, lon=31.23, rating=4.0),
            ]
            mock_llm.return_value = mock_response

            result = await run_hotel_selection(state)

        hotels = result["optimized_itinerary"]["accommodation_suggestions"]
        hotel = hotels[0]
        assert hotel["amenities"] == ["wifi", "pool"]
        assert hotel["address"] == "123 Street"
        assert hotel["photos"] == ["http://example.com/photo.jpg"]
        assert hotel["category"] == "hotel"

    @pytest.mark.asyncio
    async def test_agent_message_logs_selection(self):
        """Agent messages include a summary of the hotel selection."""
        state = _make_state(
            optimized_itinerary=_make_2day_itinerary(),
            candidate_places=[
                _make_hotel_candidate(id="hotel_001", name="Hotel A"),
                _make_hotel_candidate(id="hotel_002", name="Hotel B"),
            ],
        )
        result = await run_hotel_selection(state)

        assert any("[HotelAgent]" in m for m in result.get("agent_messages", []))
        assert any("hotels selected" in m for m in result.get("agent_messages", []))
