# tests/unit/test_ai_engine/conftest.py

"""
Shared test fixtures for all AI engine agent tests.

Provides reusable _make_state(), _make_place(), and _make_profile() helpers
so individual test files don't drift with duplicate implementations.
"""

from ai_engine.graph.state import TripProfile


# ── Shared Profile Factory ──────────────────────────────────────────────────

def _make_profile(**overrides) -> TripProfile:
    """Create a TripProfile with sensible defaults, overridable per test."""
    base: TripProfile = {
        "profile_id": "mock_profile_001",
        "trip_id": "mock_trip_001",
        "budget_level": "moderate",
        "travel_style": "cultural",
        "pace": "moderate",
        "interests": ["history", "art", "food"],
        "food_preferences": ["local cuisine", "street food"],
        "accommodation_preferences": ["boutique hotel", "airbnb"],
        "luxury_score": 0.5,
        "culture_score": 0.75,
        "adventure_score": 0.35,
        "shopping_score": 0.15,
        "family_score": 0.2,
        "confidence": 0.83,
        "generated_at": None,
        "updated_at": None,
    }
    base.update(overrides)
    return base


# ── Shared Place Factory ────────────────────────────────────────────────────

def _make_place(**overrides) -> dict:
    """Create a minimal place dict with sensible defaults.

    Works for both ranking and retrieval tests. Override any field per test.
    """
    base = {
        "id": "place_001",
        "name": "Test Museum",
        "category": "attractions",
        "lat": 30.0444,
        "lon": 31.2357,
        "rating": 4.5,
        "popularity_score": 75,
        "interest_tags": ["history", "art"],
        "sub_category": "museum",
        "cuisine_type": "",
    }
    base.update(overrides)
    return base


def _make_hotel(**overrides) -> dict:
    """Create a hotel place dict."""
    base = _make_place(
        id="hotel_001",
        name="Test Hotel",
        category="hotel",
        lat=30.05,
        lon=31.24,
        interest_tags=[],
        sub_category="luxury hotel",
        accommodation_type="hotel",
    )
    base.update(overrides)
    return base


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


# ── Shared State Factory ────────────────────────────────────────────────────

def _make_state(**overrides) -> dict:
    """Create a minimal TripState dict for testing.

    Uses sensible defaults for all keys. Override any key via kwargs.
    """
    base = {
        "user_id": "test_user",
        "user_message": "I want a romantic trip to Paris",
        "token": None,
        "trip_id": None,
        "profile": _make_profile(),
        "extracted_preferences": None,
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
        "destination_city": "Paris",
        "destination_country": None,
        "duration_days": 3,
        "travel_dates": None,
        "special_requests": None,
        "group_size": None,
        "missing_fields": [],
        "agent_messages": [],
    }
    base.update(overrides)
    return base
