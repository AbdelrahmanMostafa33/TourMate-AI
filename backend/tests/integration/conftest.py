# tests/integration/conftest.py

"""
Shared fixtures and helpers for integration tests.

Integration tests verify that multiple agents wire together correctly
(LLM calls are mocked, but agent logic runs for real).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.graph.state import TripProfile
from tests.unit.test_ai_engine.conftest import _make_profile, _make_state, _make_place, _make_hotel, _make_restaurant


# ── Shared Mock Place Data ─────────────────────────────────────────────────

MOCK_PLACES = [
    _make_place(
        id="place_001", name="Egyptian Museum", category="attractions",
        lat=30.0478, lon=31.2336, rating=4.7, popularity_score=90,
        interest_tags=["history", "art", "museum"], sub_category="museum",
    ),
    _make_place(
        id="place_002", name="Khan El Khalili", category="attractions",
        lat=30.0478, lon=31.2336, rating=4.5, popularity_score=85,
        interest_tags=["shopping", "history", "market"], sub_category="market",
    ),
    _make_place(
        id="place_003", name="Pyramids of Giza", category="attractions",
        lat=29.9792, lon=31.1342, rating=4.8, popularity_score=95,
        interest_tags=["history", "architecture", "heritage"], sub_category="historic",
    ),
    _make_place(
        id="place_004", name="Al-Azhar Park", category="attractions",
        lat=30.0436, lon=31.2496, rating=4.4, popularity_score=70,
        interest_tags=["nature", "parks", "outdoors"], sub_category="park",
    ),
    _make_hotel(
        id="hotel_001", name="Marriott Mena House", lat=29.9758, lon=31.1334,
        rating=4.6, popularity_score=80, sub_category="luxury hotel",
    ),
    _make_hotel(
        id="hotel_002", name="Steigenberger Tahrir", lat=30.0429, lon=31.2347,
        rating=4.3, popularity_score=65, sub_category="boutique hotel",
    ),
    _make_restaurant(
        id="rest_001", name="Abu Shukri", lat=30.0464, lon=31.2325,
        rating=4.5, popularity_score=75, cuisine_type="local cuisine",
        sub_category="local cuisine",
    ),
    _make_restaurant(
        id="rest_002", name="Nubia Restaurant", lat=30.0458, lon=31.2360,
        rating=4.2, popularity_score=60, cuisine_type="local cuisine",
        sub_category="street food",
    ),
]


# ── LLM Response Builders ──────────────────────────────────────────────────

def build_preference_llm_response(refinements: dict | None = None) -> MagicMock:
    """Build a mock LLM that returns preference refinement JSON."""
    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps(refinements or {})
    llm.invoke.return_value = response
    return llm


def build_planning_llm_response(
    num_days: int = 2,
    num_stops_per_day: int = 3,
) -> MagicMock:
    """Build a mock LLM that returns a valid itinerary JSON."""
    days = []
    place_ids = ["place_001", "place_002", "place_003", "place_004"]
    place_names = ["Egyptian Museum", "Khan El Khalili", "Pyramids of Giza", "Al-Azhar Park"]
    categories = ["attractions", "attractions", "attractions", "attractions"]

    for day_num in range(1, num_days + 1):
        stops = []
        for i in range(num_stops_per_day):
            idx = (day_num - 1) * num_stops_per_day + i
            pid = place_ids[idx % len(place_ids)]
            pname = place_names[idx % len(place_names)]
            cat = categories[idx % len(categories)]
            stops.append({
                "id": pid,
                "name": pname,
                "category": cat,
                "sub_category": "museum",
                "lat": 30.0478,
                "lon": 31.2336,
                "why_recommended": f"Great {cat} spot",
                "estimated_duration_minutes": 90,
                "suggested_time_of_day": ["morning", "afternoon", "evening"][i % 3],
            })
        days.append({
            "day_number": day_num,
            "theme": f"Day {day_num} Theme",
            "stops": stops,
        })

    itinerary = {
        "destination": "Cairo",
        "duration_days": num_days,
        "accommodation_suggestions": [
            {
                "id": "hotel_001",
                "name": "Marriott Mena House",
                "sub_category": "luxury hotel",
                "lat": 29.9758,
                "lon": 31.1334,
                "why_recommended": "Luxury hotel near pyramids",
                "rating": 4.6,
            },
            {
                "id": "hotel_002",
                "name": "Steigenberger Tahrir",
                "sub_category": "boutique hotel",
                "lat": 30.0429,
                "lon": 31.2347,
                "why_recommended": "Boutique hotel in downtown",
                "rating": 4.3,
            },
        ],
        "days": days,
    }

    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps(itinerary)
    llm.invoke.return_value = response
    return llm


def build_validation_llm_response(
    is_valid: bool = True,
    score: int = 85,
) -> MagicMock:
    """Build a mock LLM that returns a validation result."""
    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps({
        "is_valid": is_valid,
        "score": score,
        "issues": [] if is_valid else ["Pacing could be improved"],
        "suggestions": ["Consider adding a lunch break"],
    })
    llm.invoke.return_value = response
    return llm


# ── State Builder ──────────────────────────────────────────────────────────

def build_pipeline_state(**overrides) -> dict:
    """Build a complete TripState ready for the pipeline."""
    base = _make_state(
        destination_city="Cairo",
        duration_days=2,
        user_message="Plan me a 2-day cultural trip to Cairo",
        profile=_make_profile(
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history", "art", "food"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        ),
    )
    base.update(overrides)
    return base


# ── Mock OSRM Matrix ──────────────────────────────────────────────────────

def make_mock_matrix(size: int = 3, travel_time: float = 10.0) -> list:
    """Build an NxN mock travel-time matrix."""
    return [[0.0 if i == j else travel_time for j in range(size)] for i in range(size)]
