"""Unit tests for profile_service.py — save_quiz and save_default_persona."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.models.enums import (
    PaceStyle, SpendingStyle, ExperienceLean,
    DayRhythm, AttractionPreference, SocialStyle,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_quiz_request():
    """Create a valid QuizSubmitRequest for testing."""
    from app.schemas.profile import QuizSubmitRequest
    return QuizSubmitRequest(
        pace_style=PaceStyle.ADVENTUROUS,
        spending_style=SpendingStyle.BUDGET_CONSCIOUS,
        experience_lean=ExperienceLean.CULTURE,
        day_rhythm=DayRhythm.EARLY_BIRD,
        attraction_preference=AttractionPreference.LOCAL,
        social_style=SocialStyle.SOCIAL,
        interests=["history", "art", "food"],
        dining_preferences=["local cuisine", "street food"],
        accommodation_preferences=["boutique hotel"],
        custom_interests=["hidden gems"],
    )


def make_mock_profile(user_id="test_user_123"):
    """Create a mock BehavioralProfile object."""
    profile = MagicMock()
    profile.user_id = user_id
    profile.pace_style = None
    profile.spending_style = None
    profile.experience_lean = None
    profile.day_rhythm = None
    profile.attraction_preference = None
    profile.social_style = None
    profile.interests = None
    profile.dining_preferences = None
    profile.accommodation_preferences = None
    profile.custom_interests = None
    profile.persona_title = None
    profile.persona_summary = None
    profile.quiz_completed = False
    profile.completed_at = None
    return profile


def make_mock_session(existing_profile=None):
    """Create a mock AsyncSession."""
    mock_session = AsyncMock()
    mock_result = MagicMock()

    if existing_profile:
        mock_result.scalar_one_or_none.return_value = existing_profile
    else:
        mock_result.scalar_one_or_none.return_value = None

    mock_session.execute.return_value = mock_result
    return mock_session


# ── Tests: save_quiz ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.services.profile_service.generate_persona")
async def test_save_quiz_creates_new_profile(mock_generate_persona):
    """save_quiz should create a new BehavioralProfile when none exists."""
    from app.services.profile_service import save_quiz

    mock_generate_persona.return_value = {
        "persona_name": "The Adventurous Foodie",
        "persona_bio": "You love exploring local cuisine.",
        "suggested_questions": ["Where should I eat?"],
    }

    data = make_quiz_request()
    db = make_mock_session(existing_profile=None)

    result = await save_quiz("user_001", data, db)

    # Verify new profile was created
    db.add.assert_called_once()
    new_profile = db.add.call_args[0][0]

    assert new_profile.user_id == "user_001"
    assert new_profile.pace_style == "ADVENTUROUS"
    assert new_profile.spending_style == "BUDGET_CONSCIOUS"
    assert new_profile.experience_lean == "CULTURE"
    assert new_profile.day_rhythm == "EARLY_BIRD"
    assert new_profile.attraction_preference == "LOCAL"
    assert new_profile.social_style == "SOCIAL"
    assert new_profile.interests == ["history", "art", "food"]
    assert new_profile.dining_preferences == ["local cuisine", "street food"]
    assert new_profile.accommodation_preferences == ["boutique hotel"]
    assert new_profile.custom_interests == ["hidden gems"]
    assert new_profile.quiz_completed is True
    assert new_profile.completed_at is not None


@pytest.mark.asyncio
@patch("app.services.profile_service.generate_persona")
async def test_save_quiz_updates_existing_profile(mock_generate_persona):
    """save_quiz should update an existing profile instead of creating a new one."""
    from app.services.profile_service import save_quiz

    mock_generate_persona.return_value = {
        "persona_name": "The Culture Explorer",
        "persona_bio": "A brief bio.",
        "suggested_questions": [],
    }

    existing = make_mock_profile()
    data = make_quiz_request()
    db = make_mock_session(existing_profile=existing)

    result = await save_quiz("user_001", data, db)

    # Should NOT create a new profile
    db.add.assert_not_called()

    # Should update existing profile fields
    assert existing.pace_style == "ADVENTUROUS"
    assert existing.spending_style == "BUDGET_CONSCIOUS"
    assert existing.quiz_completed is True


@pytest.mark.asyncio
@patch("app.services.profile_service.generate_persona")
async def test_save_quiz_maps_legacy_fields_for_generate_persona(mock_generate_persona):
    """save_quiz should convert enum fields to legacy slider format for generate_persona."""
    from app.services.profile_service import save_quiz

    mock_generate_persona.return_value = {
        "persona_name": "Test Persona",
        "persona_bio": "Test bio",
        "suggested_questions": [],
    }

    data = make_quiz_request()
    db = make_mock_session(existing_profile=None)

    await save_quiz("user_001", data, db)

    # Verify generate_persona was called with legacy format
    call_args = mock_generate_persona.call_args[0][0]
    assert "adventure_relaxing" in call_args
    assert "nature_culture" in call_args
    assert "budget_level" in call_args
    assert "travel_companion" in call_args
    assert isinstance(call_args["adventure_relaxing"], int)
    assert isinstance(call_args["nature_culture"], int)


@pytest.mark.asyncio
@patch("app.services.profile_service.generate_persona")
async def test_save_quiz_sets_persona_title_and_summary(mock_generate_persona):
    """save_quiz should map persona_name → persona_title, persona_bio → persona_summary."""
    from app.services.profile_service import save_quiz

    mock_generate_persona.return_value = {
        "persona_name": "The Bold Wanderer",
        "persona_bio": "You seek thrills and local food.",
        "suggested_questions": [],
    }

    data = make_quiz_request()
    db = make_mock_session(existing_profile=None)

    await save_quiz("user_001", data, db)

    new_profile = db.add.call_args[0][0]
    assert new_profile.persona_title == "The Bold Wanderer"
    assert new_profile.persona_summary == "You seek thrills and local food."


# ── Tests: save_default_persona ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_default_persona_creates_new_profile():
    """save_default_persona should create a new profile when none exists."""
    from app.services.profile_service import save_default_persona

    db = make_mock_session(existing_profile=None)

    result = await save_default_persona("user_002", db)

    db.add.assert_called_once()
    new_profile = db.add.call_args[0][0]

    assert new_profile.user_id == "user_002"
    assert new_profile.persona_title == "The Open Explorer"
    assert "free spirit" in new_profile.persona_summary
    assert new_profile.interests == []
    assert new_profile.quiz_completed is False


@pytest.mark.asyncio
async def test_save_default_persona_updates_existing_profile():
    """save_default_persona should update an existing profile."""
    from app.services.profile_service import save_default_persona

    existing = make_mock_profile()
    db = make_mock_session(existing_profile=existing)

    result = await save_default_persona("user_002", db)

    # Should NOT create new
    db.add.assert_not_called()

    # Should update existing
    assert existing.persona_title == "The Open Explorer"
    assert existing.quiz_completed is False
    assert existing.interests == []


@pytest.mark.asyncio
async def test_save_default_persona_clears_lists():
    """save_default_persona should reset all list fields to empty."""
    from app.services.profile_service import save_default_persona

    existing = make_mock_profile()
    existing.interests = ["old_interest"]
    existing.dining_preferences = ["old_dining"]
    existing.accommodation_preferences = ["old_accommodation"]
    existing.custom_interests = ["old_custom"]

    db = make_mock_session(existing_profile=existing)

    await save_default_persona("user_002", db)

    assert existing.interests == []
    assert existing.dining_preferences == []
    assert existing.accommodation_preferences == []
    assert existing.custom_interests == []
