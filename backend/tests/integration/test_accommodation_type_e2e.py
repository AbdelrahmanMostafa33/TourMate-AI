# tests/integration/test_accommodation_type_e2e.py

"""
End-to-end integration tests for the accommodation_type flow.

Tests verify the complete pipeline from user profile accommodation preferences
through to retrieval filtering:

  profile.accommodation_preferences → _map_accommodation_to_type →
  _apply_filters hotel filtering

Agent logic (accommodation mapping, rating/distance filtering) runs for real.
"""

import pytest
from unittest.mock import AsyncMock, patch

from ai_engine.tools.slot_normalizer import map_accommodation_to_type
from ai_engine.services.place_retriever import _apply_filters
from tests.unit.test_ai_engine.conftest import _make_profile, _make_hotel, _make_place


def _make_restaurant(**overrides) -> dict:
    """Create a restaurant place dict."""
    base = _make_place(
        id="rest_001",
        name="Test Restaurant",
        category="restaurant",
        lat=30.04,
        lon=31.23,
        interest_tags=["food"],
        sub_category="local cuisine",
        cuisine_type="local cuisine",
    )
    base.update(overrides)
    return base


# ── Shared Test Data ───────────────────────────────────────────────────────

MIXED_PLACES = [
    _make_place(
        id="place_001",
        name="Egyptian Museum",
        category="attractions",
        lat=30.0478,
        lon=31.2336,
        rating=4.7,
        popularity_score=90,
        interest_tags=["history", "art", "museum"],
    ),
    _make_place(
        id="place_002",
        name="Khan El Khalili",
        category="attractions",
        lat=30.0478,
        lon=31.2336,
        rating=4.5,
        popularity_score=85,
        interest_tags=["shopping", "history", "market"],
    ),
    _make_hotel(
        id="hotel_001",
        name="Marriott Mena House",
        lat=29.9758,
        lon=31.1334,
        rating=4.6,
        popularity_score=80,
        accommodation_type="luxury",
        sub_category="luxury hotel",
    ),
    _make_hotel(
        id="hotel_002",
        name="Steigenberger Tahrir",
        lat=30.0429,
        lon=31.2347,
        rating=4.3,
        popularity_score=65,
        accommodation_type="hotel",
        sub_category="boutique hotel",
    ),
    _make_hotel(
        id="hotel_003",
        name="Cairo Backpackers Hostel",
        lat=30.0512,
        lon=31.2471,
        rating=3.9,
        popularity_score=45,
        accommodation_type="hostel",
        sub_category="hostel",
    ),
    _make_hotel(
        id="hotel_004",
        name="Soma Bay Resort",
        lat=30.0100,
        lon=31.1500,
        rating=4.4,
        popularity_score=70,
        accommodation_type="resort",
        sub_category="beach resort",
    ),
    _make_restaurant(
        id="rest_001",
        name="Abu Shukri",
        lat=30.0464,
        lon=31.2325,
        rating=4.5,
        popularity_score=75,
        cuisine_type="local cuisine",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# 1. _map_accommodation_to_type Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMapAccommodationToType:
    """Natural language → canonical accommodation type mapping."""

    @pytest.mark.parametrize("preferences,expected", [
        pytest.param(["beach resort"], "resort", id="resort_keyword"),
        pytest.param(["backpacker hostel"], "hostel", id="hostel_keyword"),
        pytest.param(["boutique hotel"], "luxury", id="luxury_keyword"),
        pytest.param(["hotel"], "hotel", id="hotel_keyword"),
        pytest.param([], "", id="empty_preferences"),
        pytest.param(["all-inclusive resort"], "resort", id="all_inclusive_maps_to_resort"),
        pytest.param(["premium hotel"], "luxury", id="premium_maps_to_luxury"),
        pytest.param(["backpacker dorm"], "hostel", id="backpacker_maps_to_hostel"),
    ])
    def test_keyword_mapping(self, preferences, expected):
        assert map_accommodation_to_type(preferences) == expected


# ═══════════════════════════════════════════════════════════════════════════
# 2. Enum Mapping → Retrieval Filtering (End-to-End)
# ═══════════════════════════════════════════════════════════════════════════


class TestAccommodationTypeEndToEnd:
    """Full flow: accommodation preference → mapping → retrieval filtering."""

    def _assert_hotel_filtered_ids(self, filtered, expected_include, expected_exclude):
        """Helper to assert which hotels pass the filter."""
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        for hid in expected_include:
            assert hid in hotel_ids, f"Expected {hid} in filtered hotels"
        for hid in expected_exclude:
            assert hid not in hotel_ids, f"Expected {hid} to be filtered out"

    @pytest.mark.parametrize("preference,include,exclude", [
        pytest.param(
            ["fancy resort"],
            ["hotel_004"],
            ["hotel_001", "hotel_002", "hotel_003"],
            id="resort_preference_filters_to_resort_only",
        ),
        pytest.param(
            ["hostel"],
            ["hotel_003"],
            ["hotel_001", "hotel_002", "hotel_004"],
            id="hostel_preference_filters_to_hostels_only",
        ),
        pytest.param(
            ["luxury"],
            ["hotel_001"],
            ["hotel_002", "hotel_003", "hotel_004"],
            id="luxury_preference_filters_to_luxury_only",
        ),
        pytest.param(
            ["hotel"],
            ["hotel_002"],
            ["hotel_001", "hotel_003", "hotel_004"],
            id="standard_hotel_preference_keeps_hotel_type_only",
        ),
        pytest.param(
            ["boutique hotel"],
            ["hotel_001"],
            ["hotel_002", "hotel_003", "hotel_004"],
            id="boutique_maps_to_luxury",
        ),
        pytest.param(
            ["all-inclusive resort"],
            ["hotel_004"],
            ["hotel_001", "hotel_003"],
            id="all_inclusive_maps_to_resort",
        ),
        pytest.param(
            ["backpacker dorm"],
            ["hotel_003"],
            ["hotel_001", "hotel_002", "hotel_004"],
            id="backpacker_maps_to_hostel",
        ),
        pytest.param(
            ["premium hotel"],
            ["hotel_001"],
            ["hotel_002", "hotel_003", "hotel_004"],
            id="premium_maps_to_luxury",
        ),
    ])
    def test_accommodation_preference_filters_correctly(
        self, preference, include, exclude,
    ):
        """User accommodation preference maps to correct type and filters accordingly."""
        prefs = {"accommodation_preferences": preference}
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")
        self._assert_hotel_filtered_ids(filtered, include, exclude)

    def test_no_accommodation_pref_keeps_all_hotels(self):
        """No accommodation preference → all hotels pass through."""
        prefs = {}
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert len(hotel_ids) == 4


# ═══════════════════════════════════════════════════════════════════════════
# 3. Full Pipeline with Accommodation Type
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipelineWithAccommodationType:
    """Full pipeline runs with accommodation_type filtering at each stage."""

    @pytest.mark.asyncio
    async def test_retrieval_pipeline_filters_hotels_by_resort_type(self):
        """Place retriever filters hotels by resort type from profile."""

        state = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "user_message": "I want a beach resort in Cairo",
            "profile": _make_profile(
                accommodation_preferences=["beach resort"],
                interests=["history", "art"],
            ),
            "filtered_places": None,
            "candidate_places": None,
            "draft_itinerary": None,
            "optimized_itinerary": None,
            "is_valid": None,
            "validation": None,
            "planning_attempts": 0,
            "next_agent": None,
            "error": None,
            "intent_type": "plan_trip",
            "destination_country": None,
            "travel_dates": None,
            "special_requests": None,
            "group_size": None,
            "traveler_group_type": None,
            "missing_fields": [],
            "agent_messages": [],
            "user_id": "test_user",
            "token": None,
            "trip_id": None,
        }

        # Run retrieval node (mock places, run real filtering)
        from ai_engine.graph.nodes import retrieval_node

        with patch(
            "ai_engine.services.place_retriever.get_places_for_city",
            new_callable=AsyncMock,
            return_value=MIXED_PLACES,
        ):
            state = await retrieval_node(state)

        # Verify filtering worked
        filtered = state["filtered_places"]
        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]

        assert "hotel_004" in hotel_ids  # Soma Bay Resort
        assert "hotel_001" not in hotel_ids  # Luxury Marriott
        assert "hotel_003" not in hotel_ids  # Hostel

        attraction_ids = [
            p["id"] for p in filtered if p["category"] == "attractions"
        ]
        assert len(attraction_ids) >= 1
