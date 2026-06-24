"""Unit tests for users.py route endpoints — current ERD-aligned version."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


def make_mock_user(user_id="user_001"):
    """Create a mock User."""
    user = MagicMock()
    user.user_id = user_id
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.phone_number = "+1234567890"
    user.home_city = "Cairo"
    user.registration_date = datetime.utcnow()
    user.traveler_persona = "The Curious Explorer"
    return user


def make_mock_trip_profile():
    """Create a mock TripProfile."""
    profile = MagicMock()
    profile.profile_id = "prof_001"
    profile.trip_id = "trip_001"
    profile.budget_level = "moderate"
    profile.travel_style = "cultural"
    profile.pace = "moderate"
    profile.interests = ["history", "art", "food"]
    profile.generated_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()
    return profile


def make_mock_trip_profile():
    """Create a mock TripProfile."""
    profile = MagicMock()
    profile.profile_id = "prof_001"
    profile.trip_id = "trip_001"
    profile.budget_level = "moderate"
    profile.travel_style = "cultural"
    profile.pace = "moderate"
    profile.food_preferences = ["local cuisine"]
    profile.accommodation_preferences = ["boutique hotel"]
    profile.generated_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()
    return profile


def make_current_user(uid="user_001"):
    """Create a mock current_user dict from auth."""
    return {"uid": uid, "email": "test@example.com"}


def make_db_that_returns(result_list):
    """Create a mock AsyncSession that returns items from result_list in order."""
    db = AsyncMock()
    call_count = [0]

    async def side_effect(*args, **kwargs):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(result_list):
            r = MagicMock()
            r.scalar_one_or_none.return_value = result_list[idx]
            return r
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        return r

    db.execute.side_effect = side_effect
    return db


# ── Tests: GET /profile ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_user_profile_returns_user_without_trip_profile():
    """GET /profile should return user data when no trip_id is given."""
    from app.api.v1.routes.users import get_user_profile

    user = make_mock_user()
    db = make_db_that_returns([user])

    response = await get_user_profile(
        current_user=make_current_user(), db=db, trip_id=None
    )

    assert response.user_id == "user_001"
    assert response.email == "test@example.com"
    assert response.full_name == "Test User"
    assert response.traveler_persona == "The Curious Explorer"
    assert response.trip_profile is None


@pytest.mark.asyncio
async def test_get_user_profile_with_trip_profile():
    """GET /profile with trip_id should include the trip profile."""
    from app.api.v1.routes.users import get_user_profile

    user = make_mock_user()
    trip_profile = make_mock_trip_profile()
    db = make_db_that_returns([user, trip_profile])

    response = await get_user_profile(
        current_user=make_current_user(), db=db, trip_id="trip_001"
    )

    assert response.user_id == "user_001"
    assert response.trip_profile is not None
    assert response.trip_profile.budget_level == "moderate"
    assert response.trip_profile.travel_style == "cultural"


@pytest.mark.asyncio
async def test_get_user_profile_not_found():
    """GET /profile should raise 404 when user not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import get_user_profile

    db = make_db_that_returns([None])

    with pytest.raises(HTTPException) as exc_info:
        await get_user_profile(
            current_user=make_current_user(), db=db, trip_id=None
        )
    assert exc_info.value.status_code == 404


# ── Tests: GET /profile/full ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_full_profile_success():
    """GET /profile/full should return user data."""
    from app.api.v1.routes.users import get_full_profile

    user = make_mock_user()
    db = make_db_that_returns([user])

    response = await get_full_profile(
        current_user=make_current_user(), db=db
    )

    assert response.user_id == "user_001"
    assert response.email == "test@example.com"
    assert response.full_name == "Test User"
    assert response.traveler_persona == "The Curious Explorer"


@pytest.mark.asyncio
async def test_get_full_profile_user_not_found():
    """GET /profile/full should raise 404 when user not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import get_full_profile

    db = make_db_that_returns([None])

    with pytest.raises(HTTPException) as exc_info:
        await get_full_profile(current_user=make_current_user(), db=db)
    assert exc_info.value.status_code == 404


# ── Tests: PUT /profile ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_user_profile_updates_fields():
    """PUT /profile should update all provided fields."""
    from app.api.v1.routes.users import update_user_profile
    from app.schemas.user import UserUpdate

    user = make_mock_user()
    db = make_db_that_returns([user])

    body = UserUpdate(
        full_name="Updated Name",
        phone_number="+9876543210",
        home_city="Alexandria",
        traveler_persona="The Beach Lover",
    )

    response = await update_user_profile(
        body=body, current_user=make_current_user(), db=db
    )

    assert user.full_name == "Updated Name"
    assert user.phone_number == "+9876543210"
    assert user.home_city == "Alexandria"
    assert user.traveler_persona == "The Beach Lover"
    db.commit.assert_called_once()
    assert response.full_name == "Updated Name"
    assert response.traveler_persona == "The Beach Lover"


@pytest.mark.asyncio
async def test_update_user_profile_partial_update():
    """PUT /profile should only update provided fields."""
    from app.api.v1.routes.users import update_user_profile
    from app.schemas.user import UserUpdate

    user = make_mock_user()
    original_full_name = user.full_name
    original_traveler_persona = user.traveler_persona
    db = make_db_that_returns([user])

    body = UserUpdate(home_city="Luxor")

    response = await update_user_profile(
        body=body, current_user=make_current_user(), db=db
    )

    assert user.home_city == "Luxor"
    assert user.full_name == original_full_name  # unchanged
    assert user.traveler_persona == original_traveler_persona  # unchanged


@pytest.mark.asyncio
async def test_update_user_profile_not_found():
    """PUT /profile should raise 404 when user not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import update_user_profile
    from app.schemas.user import UserUpdate

    db = make_db_that_returns([None])

    body = UserUpdate(full_name="Nobody")

    with pytest.raises(HTTPException) as exc_info:
        await update_user_profile(
            body=body, current_user=make_current_user(), db=db
        )
    assert exc_info.value.status_code == 404
