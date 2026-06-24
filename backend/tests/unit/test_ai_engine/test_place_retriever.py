# backend/tests/unit/test_ai_engine/test_place_retriever.py

"""
Unit tests for the Place Retriever.

Tests cover:
    - _compute_city_center(): computes centroid of non-hotel places
    - _apply_filters(): rating, distance, interest relevance filters
    - _ensure_diversity(): minimum category diversity guarantees
    - retrieve_places(): full agent run with mocked places_tool
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ai_engine.services.place_retriever import (
    _compute_city_center,
    _apply_filters,
    _cap_candidates,
    retrieve_places,
    MIN_RATING,
    MAX_DISTANCE_KM,
)
from tests.unit.test_ai_engine.conftest import _make_state, _make_place, _make_hotel, _make_restaurant


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_retriever_state(**overrides) -> dict:
    """State with profile pre-populated for retrieval tests."""
    defaults = {
        "user_message": "Plan me a trip to Cairo",
        "profile": None,
        "destination_city": "Cairo",
    }
    defaults.update(overrides)
    return _make_state(**defaults)


# ── _compute_city_center Tests ────────────────────────────────────────────────

class TestComputeCityCenter:

    def test_center_of_single_place(self):
        places = [_make_place(lat=30.0, lon=31.0)]
        result = _compute_city_center(places)
        assert result == (30.0, 31.0)

    def test_center_averages_non_hotel_places(self):
        places = [
            _make_place(lat=30.0, lon=31.0),
            _make_place(lat=31.0, lon=32.0),
        ]
        result = _compute_city_center(places)
        assert result == (30.5, 31.5)

    def test_hotels_excluded_from_center(self):
        places = [
            _make_hotel(lat=35.0, lon=36.0),  # far away — should be excluded
            _make_place(lat=30.0, lon=31.0),
        ]
        result = _compute_city_center(places)
        assert result == (30.0, 31.0)

    def test_all_hotels_returns_none(self):
        places = [_make_hotel(lat=30.0, lon=31.0), _make_hotel(lat=31.0, lon=32.0)]
        result = _compute_city_center(places)
        assert result is None

    def test_empty_list_returns_none(self):
        result = _compute_city_center([])
        assert result is None


# ── _apply_filters Tests ──────────────────────────────────────────────────────

class TestApplyFilters:

    def test_low_rating_filtered_out(self):
        places = [_make_place(rating=2.0)]
        filtered = _apply_filters(places, {}, "Cairo")
        assert len(filtered) == 0

    def test_high_rating_kept(self):
        places = [_make_place(rating=4.5)]
        filtered = _apply_filters(places, {}, "Cairo")
        assert len(filtered) == 1

    def test_rating_at_threshold_kept(self):
        places = [_make_place(rating=MIN_RATING)]
        filtered = _apply_filters(places, {}, "Cairo")
        assert len(filtered) == 1

    def test_hotels_always_kept(self):
        """Hotels should pass through regardless of other filters."""
        places = [_make_hotel(rating=1.0)]  # low rating
        filtered = _apply_filters(places, {}, "Cairo")
        assert len(filtered) == 1

    def test_all_places_pass_rating_filter(self):
        """Interest filtering is soft — all rated places pass through."""
        places = [
            _make_place(id="a1", name="History Museum", interest_tags=["history"]),
            _make_place(id="a2", name="Sports Bar", interest_tags=["sports"]),
            _make_place(id="a3", name="Shopping Mall", interest_tags=["shopping"]),
        ]
        prefs = {}
        filtered = _apply_filters(places, prefs, "Cairo")
        # All 3 pass — interest matching is handled by Candidate Scorer
        assert len(filtered) == 3

    def test_low_rated_place_still_filtered(self):
        """Only rating + distance are hard filters, not interests."""
        places = [_make_place(interest_tags=["sports"], rating=1.0)]
        prefs = {}
        filtered = _apply_filters(places, prefs, "Cairo")
        # Low rating filtered out even though interest matches
        assert len(filtered) == 0

    def test_empty_profile_keeps_all(self):
        """When profile has no data, all rated places pass."""
        places = [_make_place(interest_tags=["sports"])]
        prefs = {}
        filtered = _apply_filters(places, prefs, "Cairo")
        assert len(filtered) == 1

    def test_far_place_filtered_out(self):
        """Place >50km from center should be filtered."""
        # Use many close places so the center stays near them,
        # plus one far place that gets filtered.
        close_places = [
            _make_place(id=f"c{i}", lat=30.04, lon=31.23) for i in range(5)
        ]
        # Place ~60km from the cluster center (just beyond 50km threshold)
        far_place = _make_place(id="far", lat=30.5, lon=31.6)
        prefs = {}
        filtered = _apply_filters(close_places + [far_place], prefs, "Cairo")
        ids = {p["id"] for p in filtered}
        assert "far" not in ids  # far place should be filtered out
        assert len(filtered) == len(close_places)  # all close places kept

    def test_mixed_categories_all_pass(self):
        """All rated places pass — interest matching is soft, not hard."""
        hotel = _make_hotel()
        museum = _make_place(name="Museum", interest_tags=["history"])
        bar = _make_place(name="Sports Bar", interest_tags=["sports"])
        prefs = {}
        filtered = _apply_filters([hotel, museum, bar], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Hotel" in names
        assert "Museum" in names
        assert "Sports Bar" in names  # now kept — ranking agent scores relevance

    def test_hotel_filtered_by_accommodation_preferences(self):
        """When accommodation_preferences is set, only matching hotels are kept."""
        hotel = _make_hotel(accommodation_type="hotel")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        resort = _make_hotel(id="h3", name="Test Resort", accommodation_type="resort")
        prefs = {
            "accommodation_preferences": ["resort"],
        }
        filtered = _apply_filters([hotel, hostel, resort], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Resort" in names
        assert "Test Hotel" not in names
        assert "Test Hostel" not in names

    def test_hotel_kept_when_no_accommodation_preferences(self):
        """When no accommodation_preferences is set, all hotels are kept."""
        hotel = _make_hotel(accommodation_type="hotel")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        prefs = {}
        filtered = _apply_filters([hotel, hostel], prefs, "Cairo")
        assert len(filtered) == 2

    def test_accommodation_maps_boutique_to_luxury(self):
        """'boutique hotel' should map to 'luxury' and match luxury hotels."""
        hotel = _make_hotel(accommodation_type="luxury")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        prefs = {
            "accommodation_preferences": ["boutique hotel"],
        }
        filtered = _apply_filters([hotel, hostel], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Hotel" in names
        assert "Test Hostel" not in names

    def test_empty_places_returns_empty(self):
        filtered = _apply_filters([], {}, "Cairo")
        assert filtered == []


# ── _cap_candidates Tests ────────────────────────────────────────────────────

class TestCapCandidates:

    def test_caps_attractions(self):
        """Should cap attractions at max_attractions."""
        attractions = [_make_place(id=f"a_{i}") for i in range(100)]
        result = _cap_candidates(attractions, max_attractions=30, max_restaurants=0, max_hotels=0)
        assert len(result) == 30

    def test_caps_restaurants(self):
        """Should cap restaurants at max_restaurants."""
        restaurants = [_make_restaurant(id=f"r_{i}") for i in range(20)]
        result = _cap_candidates(restaurants, max_restaurants=10, max_attractions=0, max_hotels=0)
        rest = [p for p in result if p["category"] == "restaurant"]
        assert len(rest) == 10

    def test_caps_hotels(self):
        """Should cap hotels at max_hotels."""
        hotels = [_make_hotel(id=f"h_{i}") for i in range(20)]
        result = _cap_candidates(hotels, max_hotels=5, max_attractions=0, max_restaurants=0)
        hotel = [p for p in result if p["category"] == "hotel"]
        assert len(hotel) == 5

    def test_fewer_places_returns_all(self):
        """If fewer places than cap, return all."""
        places = [_make_place(id="a1")]
        result = _cap_candidates(places, max_attractions=80)
        assert len(result) == 1

    def test_sorted_by_popularity(self):
        """Places should be sorted by popularity (descending)."""
        places = [
            _make_place(id="low", popularity_score=10),
            _make_place(id="high", popularity_score=90),
            _make_place(id="mid", popularity_score=50),
        ]
        result = _cap_candidates(places, max_attractions=3)
        scores = [p["popularity_score"] for p in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_places_returns_empty(self):
        result = _cap_candidates([])
        assert result == []


# ── retrieve_places Tests ─────────────────────────────────────────────────

class TestRunRetriever:

    @pytest.mark.asyncio
    async def test_no_places_sets_error(self):
        """When get_places_for_city returns empty, error is set."""
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=[]):
            state = _make_retriever_state()
            result = await retrieve_places(state)

        assert result["error"] is not None
        assert result["filtered_places"] == []

    @pytest.mark.asyncio
    async def test_places_filtered_and_diversified(self):
        """Places go through filtering and diversity steps."""
        places = [
            _make_hotel(id="h1"),
            _make_place(id="a1", interest_tags=["history"]),
            _make_place(id="a2", interest_tags=["art"]),
            _make_restaurant(id="r1"),
            _make_restaurant(id="r2"),
        ]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places):
            state = _make_retriever_state()
            result = await retrieve_places(state)

        assert result["filtered_places"] is not None
        assert len(result["filtered_places"]) > 0

    @pytest.mark.asyncio
    async def test_hotels_preserved_in_results(self):
        """Hotels should always appear in filtered results."""
        places = [
            _make_hotel(id="h1"),
            _make_place(id="a1", interest_tags=["history"]),
        ]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places):
            state = _make_retriever_state()
            result = await retrieve_places(state)

        categories = {p["category"] for p in result["filtered_places"]}
        assert "hotel" in categories

    @pytest.mark.asyncio
    async def test_get_places_called_with_city_only(self):
        """get_places_for_city should be called with city only (no interests)."""
        places = [_make_place(id="a1", interest_tags=["history"])]
        profile = {"interests": ["history", "food"]}

        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places) as mock_get:
            state = _make_retriever_state(profile=profile)
            await retrieve_places(state)

        # Verify only city was passed — interests handled downstream
        call_args = mock_get.call_args
        assert call_args[0][0] == "Cairo"
        assert mock_get.call_args.kwargs == {}

    @pytest.mark.asyncio
    async def test_agent_message_appended(self):
        places = [_make_place(id="a1")]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places):
            state = _make_retriever_state()
            result = await retrieve_places(state)

        messages = result["agent_messages"]
        assert any("[PlaceRetriever]" in m for m in messages)

    @pytest.mark.asyncio
    async def test_destination_city_passed_to_get_places(self):
        places = [_make_place(id="a1")]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places) as mock_get:
            state = _make_retriever_state(destination_city="Dubai")
            await retrieve_places(state)

        call_args = mock_get.call_args
        assert call_args[0][0] == "Dubai"

    @pytest.mark.asyncio
    async def test_no_profile_still_works(self):
        """Agent works even if profile is None."""
        places = [_make_place(id="a1")]
        with patch("ai_engine.services.place_retriever.get_places_for_city", new_callable=AsyncMock, return_value=places):
            state = _make_retriever_state(profile=None)
            result = await retrieve_places(state)

        assert result["filtered_places"] is not None
        # With no profile interests, get_places_for_city called with empty list
