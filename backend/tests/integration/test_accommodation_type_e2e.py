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

from ai_engine.services.place_retriever import _map_accommodation_to_type, _apply_filters
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

    def test_resort_keyword(self):
        assert _map_accommodation_to_type(["beach resort"]) == "resort"

    def test_hostel_keyword(self):
        assert _map_accommodation_to_type(["backpacker hostel"]) == "hostel"

    def test_luxury_keyword(self):
        assert _map_accommodation_to_type(["boutique hotel"]) == "luxury"

    def test_hotel_keyword(self):
        assert _map_accommodation_to_type(["hotel"]) == "hotel"

    def test_empty_preferences(self):
        assert _map_accommodation_to_type([]) == ""

    def test_all_inclusive_maps_to_resort(self):
        assert _map_accommodation_to_type(["all-inclusive resort"]) == "resort"

    def test_premium_maps_to_luxury(self):
        assert _map_accommodation_to_type(["premium hotel"]) == "luxury"

    def test_backpacker_maps_to_hostel(self):
        assert _map_accommodation_to_type(["backpacker dorm"]) == "hostel"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Enum Mapping → Retrieval Filtering (End-to-End)
# ═══════════════════════════════════════════════════════════════════════════


class TestAccommodationTypeEndToEnd:
    """Full flow: accommodation preference → mapping → retrieval filtering."""

    def test_luxury_preference_filters_to_luxury_hotels(self):
        """User says 'fancy resort' → maps to 'resort' → only resort hotels pass."""
        prefs = {
            "accommodation_preferences": ["fancy resort"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_004" in hotel_ids  # Soma Bay Resort
        assert "hotel_001" not in hotel_ids  # Marriott (luxury, not resort)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel

    def test_hostel_preference_filters_to_hostels_only(self):
        """User says 'hostel' → maps to 'hostel' → only hostels pass."""
        prefs = {
            "accommodation_preferences": ["hostel"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_003" in hotel_ids  # Cairo Backpackers Hostel
        assert "hotel_001" not in hotel_ids  # Luxury
        assert "hotel_002" not in hotel_ids  # Hotel
        assert "hotel_004" not in hotel_ids  # Resort

    def test_luxury_hotel_preference_filters_to_luxury_only(self):
        """User says 'five star hotel' → maps to 'luxury' → only luxury hotels pass."""
        prefs = {
            "accommodation_preferences": ["five star hotel"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_001" in hotel_ids  # Marriott (luxury)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel
        assert "hotel_004" not in hotel_ids  # Resort

    def test_standard_hotel_preference_keeps_all_non_luxury(self):
        """User says 'hotel' → maps to 'hotel' → hotels of type 'hotel' pass."""
        prefs = {
            "accommodation_preferences": ["hotel"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_002" in hotel_ids  # Steigenberger (hotel)
        assert "hotel_001" not in hotel_ids  # Marriott (luxury)
        assert "hotel_003" not in hotel_ids  # Hostel
        assert "hotel_004" not in hotel_ids  # Resort

    def test_no_accommodation_pref_keeps_all_hotels(self):
        """No accommodation preference → all hotels pass through."""
        prefs = {}
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert len(hotel_ids) == 4

    def test_boutique_maps_to_luxury(self):
        """'boutique hotel' → maps to 'luxury' → only luxury hotels pass."""
        prefs = {
            "accommodation_preferences": ["boutique hotel"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_001" in hotel_ids  # Marriott (luxury)
        assert "hotel_002" not in hotel_ids  # Steigenberger (hotel)
        assert "hotel_003" not in hotel_ids  # Hostel
        assert "hotel_004" not in hotel_ids  # Resort

    def test_all_inclusive_maps_to_resort(self):
        """'all-inclusive' → maps to 'resort' → only resort hotels pass."""
        prefs = {
            "accommodation_preferences": ["all-inclusive resort"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_004" in hotel_ids  # Resort
        assert "hotel_001" not in hotel_ids  # Luxury

    def test_backpacker_maps_to_hostel(self):
        """'backpacker' → maps to 'hostel' → only hostels pass."""
        prefs = {
            "accommodation_preferences": ["backpacker dorm"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_003" in hotel_ids  # Hostel
        assert "hotel_001" not in hotel_ids  # Luxury
        assert "hotel_002" not in hotel_ids  # Hotel
        assert "hotel_004" not in hotel_ids  # Resort

    def test_premium_maps_to_luxury(self):
        """'premium' → maps to 'luxury' → only luxury hotels pass."""
        prefs = {
            "accommodation_preferences": ["premium hotel"],
        }
        filtered = _apply_filters(MIXED_PLACES, prefs, "Cairo")

        hotel_ids = [p["id"] for p in filtered if p["category"] == "hotel"]
        assert "hotel_001" in hotel_ids  # Marriott (luxury)


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
