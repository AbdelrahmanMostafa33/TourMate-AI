# backend/tests/unit/test_ai_engine/test_retrieval_agent.py

"""
Unit tests for the Retrieval Agent.

Tests cover:
    - _compute_city_center(): computes centroid of non-hotel places
    - _apply_filters(): rating, distance, interest relevance filters
    - _ensure_diversity(): minimum category diversity guarantees
    - run_retrieval_agent(): full agent run with mocked places_tool
"""

import pytest
from unittest.mock import patch, MagicMock

from ai_engine.agents.retrieval_agent import (
    _compute_city_center,
    _apply_filters,
    _ensure_diversity,
    run_retrieval_agent,
    MIN_RATING,
    MAX_DISTANCE_KM,
)
from tests.unit.test_ai_engine.conftest import _make_state, _make_place, _make_hotel, _make_restaurant


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_retrieval_state(**overrides) -> dict:
    """State with extracted_preferences pre-populated for retrieval tests."""
    defaults = {
        "user_message": "Plan me a trip to Cairo",
        "profile": None,
        "extracted_preferences": {
            "interests_from_conversation": ["history", "art"],
            "walking_tolerance": "medium",
        },
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
        filtered = _apply_filters(places, {"interests_from_conversation": []}, "Cairo")
        assert len(filtered) == 0

    def test_high_rating_kept(self):
        places = [_make_place(rating=4.5)]
        filtered = _apply_filters(places, {"interests_from_conversation": []}, "Cairo")
        assert len(filtered) == 1

    def test_rating_at_threshold_kept(self):
        places = [_make_place(rating=MIN_RATING)]
        filtered = _apply_filters(places, {"interests_from_conversation": []}, "Cairo")
        assert len(filtered) == 1

    def test_hotels_always_kept(self):
        """Hotels should pass through regardless of other filters."""
        places = [_make_hotel(rating=1.0)]  # low rating
        filtered = _apply_filters(places, {"interests_from_conversation": ["history"]}, "Cairo")
        assert len(filtered) == 1

    def test_interest_match_by_category(self):
        places = [_make_place(category="history")]
        prefs = {"interests_from_conversation": ["history"]}
        filtered = _apply_filters(places, prefs, "Cairo")
        assert len(filtered) == 1

    def test_interest_match_by_tag(self):
        places = [_make_place(interest_tags=["food", "local"])]
        prefs = {"interests_from_conversation": ["food"]}
        filtered = _apply_filters(places, prefs, "Cairo")
        assert len(filtered) == 1

    def test_interest_match_by_name(self):
        places = [_make_place(name="History Museum")]
        prefs = {"interests_from_conversation": ["history"]}
        filtered = _apply_filters(places, prefs, "Cairo")
        assert len(filtered) == 1

    def test_no_interest_match_filtered_out(self):
        places = [_make_place(interest_tags=["sports"])]
        prefs = {"interests_from_conversation": ["history", "art"]}
        filtered = _apply_filters(places, prefs, "Cairo")
        assert len(filtered) == 0

    def test_empty_interests_keeps_all(self):
        """When no interests specified, all places pass interest filter."""
        places = [_make_place(interest_tags=["sports"])]
        prefs = {"interests_from_conversation": []}
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
        prefs = {"interests_from_conversation": []}
        filtered = _apply_filters(close_places + [far_place], prefs, "Cairo")
        ids = {p["id"] for p in filtered}
        assert "far" not in ids  # far place should be filtered out
        assert len(filtered) == len(close_places)  # all close places kept

    def test_mixed_categories_with_hotel(self):
        """Hotels pass through, attractions need interest match."""
        hotel = _make_hotel()
        museum = _make_place(name="Museum", interest_tags=["history"])
        bar = _make_place(name="Sports Bar", interest_tags=["sports"])
        prefs = {"interests_from_conversation": ["history"]}
        filtered = _apply_filters([hotel, museum, bar], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Hotel" in names
        assert "Museum" in names
        assert "Sports Bar" not in names

    def test_hotel_filtered_by_accommodation_type(self):
        """When accommodation_style is set, only matching hotels are kept."""
        hotel = _make_hotel(accommodation_type="hotel")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        resort = _make_hotel(id="h3", name="Test Resort", accommodation_type="resort")
        prefs = {
            "interests_from_conversation": [],
            "accommodation_style": "resort",
        }
        filtered = _apply_filters([hotel, hostel, resort], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Resort" in names
        assert "Test Hotel" not in names
        assert "Test Hostel" not in names

    def test_hotel_kept_when_no_accommodation_style(self):
        """When no accommodation_style is set, all hotels are kept."""
        hotel = _make_hotel(accommodation_type="hotel")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        prefs = {
            "interests_from_conversation": [],
        }
        filtered = _apply_filters([hotel, hostel], prefs, "Cairo")
        assert len(filtered) == 2

    def test_accommodation_style_partial_match(self):
        """'boutique hotel' should match a hotel with type 'hotel'."""
        hotel = _make_hotel(accommodation_type="hotel")
        hostel = _make_hotel(id="h2", name="Test Hostel", accommodation_type="hostel")
        prefs = {
            "interests_from_conversation": [],
            "accommodation_style": "boutique hotel",
        }
        filtered = _apply_filters([hotel, hostel], prefs, "Cairo")
        names = {p["name"] for p in filtered}
        assert "Test Hotel" in names
        assert "Test Hostel" not in names

    def test_empty_places_returns_empty(self):
        filtered = _apply_filters([], {"interests_from_conversation": []}, "Cairo")
        assert filtered == []


# ── _ensure_diversity Tests ───────────────────────────────────────────────────

class TestEnsureDiversity:

    def test_returns_attractions_up_to_min(self):
        places = [_make_place(id=f"a_{i}", category="attractions") for i in range(10)]
        result = _ensure_diversity(places, duration_days=3)
        attractions = [p for p in result if p["category"] == "attractions"]
        # min attractions = max(3*2, 4) = 6
        assert len(attractions) <= 6

    def test_returns_restaurants_up_to_min(self):
        places = [_make_restaurant(id=f"r_{i}") for i in range(10)]
        result = _ensure_diversity(places, duration_days=3)
        restaurants = [p for p in result if p["category"] == "restaurant"]
        # min restaurants = max(3, 3) = 3
        assert len(restaurants) <= 3

    def test_returns_hotels_up_to_min(self):
        places = [_make_hotel(id=f"h_{i}") for i in range(10)]
        result = _ensure_diversity(places, duration_days=3)
        hotels = [p for p in result if p["category"] == "hotel"]
        # min hotels = max(3//2+1, 2) = 2
        assert len(hotels) <= 2

    def test_fewer_places_than_min_returns_all(self):
        """If fewer places than minimum, return all of them."""
        places = [_make_place(id="a1", category="attractions")]
        result = _ensure_diversity(places, duration_days=3)
        assert len(result) == 1

    def test_other_categories_preserved(self):
        """Categories not in min_per_category should be fully preserved."""
        places = [
            _make_place(id=f"shop_{i}", category="shopping") for i in range(5)
        ]
        result = _ensure_diversity(places, duration_days=3)
        shopping = [p for p in result if p["category"] == "shopping"]
        assert len(shopping) == 5

    def test_sorted_by_popularity(self):
        """Within a category, places should be sorted by popularity (descending)."""
        places = [
            _make_place(id="a_low", category="attractions", popularity_score=10),
            _make_place(id="a_high", category="attractions", popularity_score=90),
            _make_place(id="a_mid", category="attractions", popularity_score=50),
        ]
        result = _ensure_diversity(places, duration_days=3)
        attractions = [p for p in result if p["category"] == "attractions"]
        # Should be sorted by popularity descending
        scores = [p["popularity_score"] for p in attractions]
        assert scores == sorted(scores, reverse=True)

    def test_empty_places_returns_empty(self):
        result = _ensure_diversity([], duration_days=3)
        assert result == []

    def test_longer_trip_requests_more(self):
        """Duration 7 should request more attractions than duration 2."""
        places_2d = [_make_place(id=f"a_{i}", category="attractions", popularity_score=80) for i in range(20)]
        places_7d = [_make_place(id=f"a_{i}", category="attractions", popularity_score=80) for i in range(20)]

        result_2d = _ensure_diversity(places_2d, duration_days=2)
        result_7d = _ensure_diversity(places_7d, duration_days=7)

        assert len(result_7d) > len(result_2d)


# ── run_retrieval_agent Tests ─────────────────────────────────────────────────

class TestRunRetrievalAgent:

    @pytest.mark.asyncio
    async def test_no_places_sets_error(self):
        """When get_places_for_city returns empty, error is set."""
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=[]):
            state = _make_retrieval_state()
            result = await run_retrieval_agent(state)

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
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places):
            state = _make_retrieval_state()
            result = await run_retrieval_agent(state)

        assert result["filtered_places"] is not None
        assert len(result["filtered_places"]) > 0

    @pytest.mark.asyncio
    async def test_hotels_preserved_in_results(self):
        """Hotels should always appear in filtered results."""
        places = [
            _make_hotel(id="h1"),
            _make_place(id="a1", interest_tags=["history"]),
        ]
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places):
            state = _make_retrieval_state()
            result = await run_retrieval_agent(state)

        categories = {p["category"] for p in result["filtered_places"]}
        assert "hotel" in categories

    @pytest.mark.asyncio
    async def test_interests_from_profile_used(self):
        """Profile interests should be passed to get_places_for_city."""
        places = [_make_place(id="a1", interest_tags=["history"])]
        profile = {"interests": ["history", "food"]}

        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places) as mock_get:
            state = _make_retrieval_state(profile=profile)
            await run_retrieval_agent(state)

        # Verify interests were passed
        call_args = mock_get.call_args
        assert call_args[1]["interests"] == ["history", "food"]

    @pytest.mark.asyncio
    async def test_agent_message_appended(self):
        places = [_make_place(id="a1")]
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places):
            state = _make_retrieval_state()
            result = await run_retrieval_agent(state)

        messages = result["agent_messages"]
        assert any("[RetrievalAgent]" in m for m in messages)

    @pytest.mark.asyncio
    async def test_destination_city_passed_to_get_places(self):
        places = [_make_place(id="a1")]
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places) as mock_get:
            state = _make_retrieval_state(destination_city="Dubai")
            await run_retrieval_agent(state)

        call_args = mock_get.call_args
        assert call_args[0][0] == "Dubai"

    @pytest.mark.asyncio
    async def test_empty_interests_from_conversation_still_works(self):
        """Agent works when extracted_preferences has no interests."""
        places = [_make_place(id="a1")]
        prefs = {"interests_from_conversation": []}
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places):
            state = _make_retrieval_state(extracted_preferences=prefs)
            result = await run_retrieval_agent(state)

        assert result["filtered_places"] is not None

    @pytest.mark.asyncio
    async def test_no_profile_still_works(self):
        """Agent works even if profile is None."""
        places = [_make_place(id="a1")]
        with patch("ai_engine.agents.retrieval_agent.get_places_for_city", return_value=places):
            state = _make_retrieval_state(profile=None)
            result = await run_retrieval_agent(state)

        assert result["filtered_places"] is not None
        # With no profile interests, get_places_for_city called with empty list
