"""Unit tests for users.py route endpoints."""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.models.enums import (
    PaceStyle, SpendingStyle, ExperienceLean,
    DayRhythm, AttractionPreference, SocialStyle,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_quiz_request_data():
    """Create a valid QuizSubmitRequest body."""
    return {
        "pace_style": "ADVENTUROUS",
        "spending_style": "BUDGET_CONSCIOUS",
        "experience_lean": "CULTURE",
        "day_rhythm": "EARLY_BIRD",
        "attraction_preference": "LOCAL",
        "social_style": "SOCIAL",
        "interests": ["history", "art"],
        "dining_preferences": ["local cuisine"],
        "accommodation_preferences": ["boutique hotel"],
        "custom_interests": ["hidden gems"],
    }


def make_mock_profile(user_id="user_001"):
    """Create a mock BehavioralProfile."""
    profile = MagicMock()
    profile.user_id = user_id
    profile.pace_style = "ADVENTUROUS"
    profile.spending_style = "BUDGET_CONSCIOUS"
    profile.experience_lean = "CULTURE"
    profile.day_rhythm = "EARLY_BIRD"
    profile.attraction_preference = "LOCAL"
    profile.social_style = "SOCIAL"
    profile.interests = ["history", "art"]
    profile.dining_preferences = ["local cuisine"]
    profile.accommodation_preferences = ["boutique hotel"]
    profile.custom_interests = ["hidden gems"]
    profile.persona_title = "The Adventurous Explorer"
    profile.persona_summary = "You love adventure and culture."
    profile.quiz_completed = True
    profile.completed_at = datetime.utcnow()
    profile.updated_at = datetime.utcnow()
    return profile


def make_mock_user(user_id="user_001"):
    """Create a mock User."""
    user = MagicMock()
    user.user_id = user_id
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.phone_number = "+1234567890"
    user.home_city = "Cairo"
    user.registration_date = datetime.utcnow()
    user.quiz_completed = True
    user.profile_id = None
    return user


def make_current_user(uid="user_001"):
    """Create a mock current_user dict from auth."""
    return {"uid": uid, "email": "test@example.com"}


def make_db_with_profile(profile=None):
    """Create a mock AsyncSession that returns a profile."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    db.execute.return_value = result
    return db


# ── Tests: POST /quiz ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.users.save_quiz")
async def test_submit_quiz_returns_persona_response(mock_save_quiz):
    """POST /quiz should return PersonaResponse with persona_title and persona_summary."""
    from app.api.v1.routes.users import submit_quiz
    from app.schemas.profile import QuizSubmitRequest

    mock_profile = make_mock_profile()
    mock_save_quiz.return_value = mock_profile

    body = QuizSubmitRequest(**make_quiz_request_data())
    db = make_db_with_profile()

    response = await submit_quiz(
        body=body, current_user=make_current_user(), db=db,
    )

    assert response.persona_title == "The Adventurous Explorer"
    assert response.persona_summary == "You love adventure and culture."
    assert response.interests == ["history", "art"]
    assert response.quiz_completed is True
    mock_save_quiz.assert_called_once()


# ── Tests: POST /quiz/skip ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.users.save_default_persona")
async def test_skip_quiz_returns_default_persona(mock_save_default):
    """POST /quiz/skip should return default persona with quiz_completed=False."""
    from app.api.v1.routes.users import skip_quiz

    mock_profile = make_mock_profile()
    mock_profile.persona_title = "The Open Explorer"
    mock_profile.persona_summary = "A free spirit."
    mock_profile.interests = []
    mock_save_default.return_value = mock_profile

    db = make_db_with_profile()

    response = await skip_quiz(current_user=make_current_user(), db=db)

    assert response.persona_title == "The Open Explorer"
    assert response.quiz_completed is False
    mock_save_default.assert_called_once()


# ── Tests: POST /quiz/test ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.users.save_quiz")
async def test_test_submit_quiz_uses_fake_user_id(mock_save_quiz):
    """POST /quiz/test should use a fake user_id and not require auth."""
    from app.api.v1.routes.users import test_submit_quiz
    from app.schemas.profile import QuizSubmitRequest

    mock_profile = make_mock_profile(user_id="newuser123")
    mock_save_quiz.return_value = mock_profile

    body = QuizSubmitRequest(**make_quiz_request_data())
    db = make_db_with_profile()

    response = await test_submit_quiz(body=body, db=db)

    assert response.persona_title == "The Adventurous Explorer"
    mock_save_quiz.assert_called_once_with("newuser123", body, db)


# ── Tests: GET /profile ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile_success():
    """GET /profile should return persona data from BehavioralProfile."""
    from app.api.v1.routes.users import get_profile

    profile = make_mock_profile()
    db = make_db_with_profile(profile)

    response = await get_profile(current_user=make_current_user(), db=db)

    assert response.persona_title == "The Adventurous Explorer"
    assert response.interests == ["history", "art"]
    assert response.quiz_completed is True


@pytest.mark.asyncio
async def test_get_profile_not_found():
    """GET /profile should raise 404 when profile not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import get_profile

    db = make_db_with_profile(profile=None)

    with pytest.raises(HTTPException) as exc_info:
        await get_profile(current_user=make_current_user(), db=db)
    assert exc_info.value.status_code == 404


# ── Tests: PATCH /profile/interests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_interests_success():
    """PATCH /profile/interests should update interests and persona fields."""
    from app.api.v1.routes.users import update_interests

    profile = make_mock_profile()
    db = make_db_with_profile(profile)

    body = {
        "user_id": "user_001",
        "interests": ["music", "hiking"],
        "persona_title": "The Music Hiker",
        "persona_summary": "You love music and hiking.",
    }

    response = await update_interests(body=body, db=db)

    assert profile.interests == ["music", "hiking"]
    assert profile.persona_title == "The Music Hiker"
    assert profile.persona_summary == "You love music and hiking."
    db.commit.assert_called_once()
    assert response["message"] == "Profile updated successfully"


@pytest.mark.asyncio
async def test_update_interests_not_found():
    """PATCH /profile/interests should raise 404 when profile not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import update_interests

    db = make_db_with_profile(profile=None)

    body = {"user_id": "nonexistent", "interests": []}
    with pytest.raises(HTTPException) as exc_info:
        await update_interests(body=body, db=db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_interests_partial_update():
    """PATCH /profile/interests should only update provided fields."""
    from app.api.v1.routes.users import update_interests

    profile = make_mock_profile()
    original_title = profile.persona_title
    original_summary = profile.persona_summary

    db = make_db_with_profile(profile)

    body = {"user_id": "user_001", "interests": ["new_interest"]}
    await update_interests(body=body, db=db)

    assert profile.interests == ["new_interest"]
    # Persona fields should NOT be changed when not provided
    assert profile.persona_title == original_title
    assert profile.persona_summary == original_summary


# ── Tests: GET /profile/full ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_full_profile_success():
    """GET /profile/full should return combined User + BehavioralProfile data."""
    from app.api.v1.routes.users import get_full_profile

    user = make_mock_user()
    profile = make_mock_profile()

    # Need to return user first, then profile
    call_count = [0]
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    profile_result = MagicMock()
    profile_result.scalar_one_or_none.return_value = profile

    async def mock_execute(query, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return user_result
        return profile_result

    db = AsyncMock()
    db.execute.side_effect = mock_execute

    response = await get_full_profile(current_user=make_current_user(), db=db)

    # User fields
    assert response.user_id == "user_001"
    assert response.email == "test@example.com"
    assert response.full_name == "Test User"
    assert response.phone_number == "+1234567890"
    assert response.home_city == "Cairo"

    # Profile fields
    assert response.quiz_completed is True
    assert response.persona_title == "The Adventurous Explorer"
    assert response.pace_style == "ADVENTUROUS"
    assert response.spending_style == "BUDGET_CONSCIOUS"
    assert response.interests == ["history", "art"]
    assert response.completed_at is not None


@pytest.mark.asyncio
async def test_get_full_profile_user_not_found():
    """GET /profile/full should raise 404 when user not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.users import get_full_profile

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc_info:
        await get_full_profile(current_user=make_current_user(), db=db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_full_profile_no_profile():
    """GET /profile/full should return user data with profile fields as None/defaults."""
    from app.api.v1.routes.users import get_full_profile

    user = make_mock_user()

    call_count = [0]
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user

    no_profile_result = MagicMock()
    no_profile_result.scalar_one_or_none.return_value = None

    async def mock_execute(query, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return user_result
        return no_profile_result

    db = AsyncMock()
    db.execute.side_effect = mock_execute

    response = await get_full_profile(current_user=make_current_user(), db=db)

    assert response.user_id == "user_001"
    assert response.quiz_completed is False
    assert response.persona_title is None
    assert response.pace_style is None
    assert response.interests is None
