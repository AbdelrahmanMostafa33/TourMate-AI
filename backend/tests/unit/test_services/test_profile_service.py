"""Unit tests for profile_service.py — get_trip_profile and upsert_trip_profile."""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from app.models.enums import BudgetLevel, TravelStyle, TripPace


def make_mock_trip_profile():
    """Create a mock TripProfile."""
    profile = MagicMock()
    profile.profile_id = "prof_001"
    profile.trip_id = "trip_001"
    profile.budget_level = "moderate"
    profile.travel_style = "cultural"
    profile.pace = "balanced"
    profile.interests = ["history", "art", "food"]
    profile.food_preferences = ["local cuisine"]
    profile.accommodation_preferences = ["boutique hotel"]
    profile.generated_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()
    return profile


def make_mock_session(existing_profile=None):
    """Create a mock AsyncSession."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_profile
    mock_session.execute.return_value = mock_result
    return mock_session


# ── Tests: get_trip_profile ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trip_profile_returns_profile():
    """get_trip_profile should return the profile when it exists."""
    from app.services.profile_service import get_trip_profile

    profile = make_mock_trip_profile()
    db = make_mock_session(existing_profile=profile)

    result = await get_trip_profile("trip_001", db)

    assert result is not None
    assert result.profile_id == "prof_001"
    assert result.budget_level == "moderate"
    assert result.travel_style == "cultural"


@pytest.mark.asyncio
async def test_get_trip_profile_returns_none():
    """get_trip_profile should return None when no profile exists."""
    from app.services.profile_service import get_trip_profile

    db = make_mock_session(existing_profile=None)

    result = await get_trip_profile("trip_001", db)

    assert result is None


# ── Tests: upsert_trip_profile ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_creates_new_profile_when_none_exists():
    """upsert_trip_profile should create a new TripProfile when none exists."""
    from app.services.profile_service import upsert_trip_profile
    from app.schemas.profile import TripProfileCreate

    db = make_mock_session(existing_profile=None)
    data = TripProfileCreate(
        budget_level=BudgetLevel.MODERATE,
        travel_style=TravelStyle.CULTURAL,
        pace=TripPace.MODERATE,
        interests=["history", "art"],
        food_preferences=["local cuisine"],
        accommodation_preferences=["boutique hotel"],
    )

    result = await upsert_trip_profile("trip_001", data, db)

    # Should have added a new profile
    db.add.assert_called_once()
    new_profile = db.add.call_args[0][0]
    assert new_profile.trip_id == "trip_001"
    assert new_profile.budget_level == BudgetLevel.MODERATE.value
    assert new_profile.travel_style == TravelStyle.CULTURAL.value
    assert new_profile.interests == ["history", "art"]


@pytest.mark.asyncio
async def test_upsert_updates_existing_profile():
    """upsert_trip_profile should update an existing profile instead of creating."""
    from app.services.profile_service import upsert_trip_profile
    from app.schemas.profile import TripProfileCreate

    existing = make_mock_trip_profile()
    db = make_mock_session(existing_profile=existing)
    data = TripProfileCreate(
        budget_level=BudgetLevel.LUXURY,
        interests=["photography"],
    )

    result = await upsert_trip_profile("trip_001", data, db)

    # Should NOT create new
    db.add.assert_not_called()

    # Should update existing
    assert existing.budget_level == BudgetLevel.LUXURY.value
    assert existing.interests == ["photography"]
    # Unchanged fields should remain
    assert existing.travel_style == "cultural"


@pytest.mark.asyncio
async def test_upsert_handles_empty_lists():
    """upsert_trip_profile should not override lists with empty ones from request."""
    from app.services.profile_service import upsert_trip_profile
    from app.schemas.profile import TripProfileCreate

    existing = make_mock_trip_profile()
    db = make_mock_session(existing_profile=existing)
    # Empty lists should NOT overwrite existing values
    data = TripProfileCreate(
        interests=[],
        food_preferences=[],
        accommodation_preferences=[],
    )

    await upsert_trip_profile("trip_001", data, db)

    # Existing lists should be preserved since empty lists are falsy
    assert existing.interests == ["history", "art", "food"]
    assert existing.food_preferences == ["local cuisine"]
