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

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base


# ── Test Database URL ─────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create a fresh in-memory SQLite async database for each test.

    Creates all tables from the SQLAlchemy metadata, then yields an
    ``AsyncSession``.  The database is fully torn down after each test.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with factory() as session:
        yield session

    await engine.dispose()


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
    """Build a mock response for invoke_with_fallback (preference refinement)."""
    response = MagicMock()
    response.content = json.dumps(refinements or {})
    return response


def build_planning_llm_response(
    num_days: int = 2,
    num_stops_per_day: int = 3,
) -> "ItineraryPlan":
    """
    Build a mock response for invoke_with_fallback (planning itinerary).

    Returns an actual ``ItineraryPlan`` Pydantic model instance because
    the planning agent now uses ``with_structured_output(ItineraryPlan)``
    instead of parsing raw LLM text output.
    """
    from ai_engine.schemas.planning_schema import ItineraryPlan, Day, Stop, AccommodationSuggestion

    place_ids = ["place_001", "place_002", "place_003", "place_004"]
    place_names = ["Egyptian Museum", "Khan El Khalili", "Pyramids of Giza", "Al-Azhar Park"]
    categories = ["attractions", "attractions", "attractions", "attractions"]
    sub_categories = ["museum", "market", "historic", "park"]

    days = []
    for day_num in range(1, num_days + 1):
        stops = []
        for i in range(num_stops_per_day):
            idx = (day_num - 1) * num_stops_per_day + i
            stops.append(Stop(
                id=place_ids[idx % len(place_ids)],
                name=place_names[idx % len(place_names)],
                category=categories[idx % len(categories)],
                sub_category=sub_categories[idx % len(sub_categories)],
                interest_tags=["history", "art", "museum"],
                lat=30.0478,
                lon=31.2336,
                why_recommended=f"Great {categories[idx % len(categories)]} spot",
                estimated_duration_minutes=90,
                suggested_time_of_day=["morning", "afternoon", "evening"][i % 3],  # type: ignore[arg-type]
            ))
        days.append(Day(
            day_number=day_num,
            theme=f"Day {day_num} Theme",
            stops=stops,
        ))

    return ItineraryPlan(
        destination="Cairo",
        duration_days=num_days,
        accommodation_suggestions=[
            AccommodationSuggestion(
                id="hotel_001",
                name="Marriott Mena House",
                sub_category="luxury hotel",
                accommodation_type="hotel",
                lat=29.9758,
                lon=31.1334,
                why_recommended="Luxury hotel near pyramids",
                rating=4.6,
            ),
            AccommodationSuggestion(
                id="hotel_002",
                name="Steigenberger Tahrir",
                sub_category="boutique hotel",
                accommodation_type="hotel",
                lat=30.0429,
                lon=31.2347,
                why_recommended="Boutique hotel in downtown",
                rating=4.3,
            ),
        ],
        days=days,
    )


def build_validation_llm_response(
    is_valid: bool = True,
    score: int = 85,
) -> MagicMock:
    """Build a mock response for invoke_with_fallback (validation)."""
    response = MagicMock()
    response.content = json.dumps({
        "is_valid": is_valid,
        "score": score,
        "issues": [] if is_valid else ["Pacing could be improved"],
        "suggestions": ["Consider adding a lunch break"],
    })
    return response


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
            pace="balanced",
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
