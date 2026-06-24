"""Unit tests for chat.py — process_message and get_profile_data."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_mock_trip():
    """Create a mock Trip with itineraries/days/stops."""
    stop = MagicMock()
    stop.stop_id = 1
    stop.place_id = "place_1"
    stop.scheduled_time = None
    stop.duration_minutes = 60
    stop.order_in_day = 1
    stop.travel_mode = MagicMock()
    stop.travel_mode.value = "walking"
    stop.estimated_cost = 10.0
    stop.ai_notes = "Test note"
    stop.user_notes = None
    stop.status = MagicMock()
    stop.status.value = "planned"

    day = MagicMock()
    day.day_id = 1
    day.day_number = 1
    day.date = datetime(2026, 7, 1).date()
    day.stops = [stop]

    itinerary = MagicMock()
    itinerary.itinerary_id = "itin_1"
    itinerary.days = [day]

    trip = MagicMock()
    trip.trip_id = "trip_1"
    trip.destination = "Cairo, Egypt"
    trip.itineraries = [itinerary]

    return trip


def make_mock_conversation():
    """Create a mock Conversation."""
    conv = MagicMock()
    conv.conversation_id = "conv_1"
    return conv


def make_mock_message(content="test", sender="user"):
    """Create a mock Message."""
    msg = MagicMock()
    msg.sender = sender
    msg.content = content
    msg.timestamp = datetime.utcnow()
    return msg


def make_mock_db_session(messages=None):
    """Create a mock AsyncSession."""
    db = AsyncMock()

    if messages is None:
        messages = [make_mock_message("Hello", "user")]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = messages
    db.execute.return_value = mock_result

    return db


# ── Tests: process_message_stream signature ────────────────────────────────
# NOTE: process_message was replaced by process_message_stream during the
# ERD sync refactor. Tests for the old non-streaming function are removed.


# ── Tests: get_profile_data ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile_data_returns_empty_dict_when_no_profile():
    """get_profile_data should return {} when no profile exists."""
    from app.api.v1.routes.chat import get_profile_data

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    result = await get_profile_data("user_999", "trip_999", db)
    assert result == {}


@pytest.mark.asyncio
async def test_get_profile_data_returns_behavioral_fields():
    """get_profile_data should return the new BehavioralProfile fields."""
    from app.api.v1.routes.chat import get_profile_data

    profile = MagicMock()
    profile.budget_level = "moderate"
    profile.travel_style = "cultural"
    profile.pace = "moderate"
    profile.interests = ["history"]
    profile.food_preferences = ["fine dining"]
    profile.accommodation_preferences = ["resort"]

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = profile
    db.execute.return_value = mock_result

    result = await get_profile_data("user_001", "trip_001", db)

    assert result["budget_level"] == profile.budget_level
    assert result["travel_style"] == profile.travel_style
    assert result["pace"] == profile.pace
    assert result["interests"] == ["history"]
    assert result["food_preferences"] == ["fine dining"]
    assert result["accommodation_preferences"] == ["resort"]
