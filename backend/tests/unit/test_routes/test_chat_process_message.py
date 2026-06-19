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


# ── Tests: process_message signature (bug fix verification) ─────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.chat.manager")
@patch("app.api.v1.routes.chat.build_trip_snapshot")
async def test_process_message_accepts_user_id_and_token(mock_snapshot, mock_manager):
    """Verify process_message now accepts user_id and token parameters."""
    from app.api.v1.routes.chat import process_message

    mock_snapshot.return_value = {"trip_id": "trip_1", "destination": "Cairo", "days": []}
    mock_manager.send = AsyncMock()

    trip = make_mock_trip()
    conv = make_mock_conversation()
    db = make_mock_db_session()

    # This should NOT raise NameError for undefined user_id/token
    # We patch handle_chat to avoid actual AI calls
    with patch("ai_engine.chat.conversation_agent.handle_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {
            "message": "Here's your plan!",
            "itinerary": None,
        }
        # If process_message doesn't accept user_id/token, this will raise TypeError
        await process_message(
            user_text="Show me my trip",
            trip=trip,
            conversation=conv,
            profile_data={},
            ws_key="test_key",
            db=db,
            user_id="user_123",
            token="test_token",
        )

    # Verify AI was called with user_id and token (not undefined)
    mock_chat.assert_called_once_with(
        user_id="user_123",
        user_message="Show me my trip",
        token="test_token",
    )


@pytest.mark.asyncio
@patch("app.api.v1.routes.chat.manager")
@patch("app.api.v1.routes.chat.build_trip_snapshot")
async def test_process_message_saves_user_message(mock_snapshot, mock_manager):
    """Verify process_message saves the user message to DB."""
    from app.api.v1.routes.chat import process_message

    mock_snapshot.return_value = {"trip_id": "trip_1", "destination": "Cairo", "days": []}
    mock_manager.send = AsyncMock()

    trip = make_mock_trip()
    conv = make_mock_conversation()
    db = make_mock_db_session()

    with patch("ai_engine.chat.conversation_agent.handle_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"message": "Reply", "itinerary": None}
        await process_message(
            user_text="Hello AI",
            trip=trip,
            conversation=conv,
            profile_data={},
            ws_key="test_key",
            db=db,
            user_id="user_123",
            token="test_token",
        )

    # Verify a message was added to the session
    db.add.assert_called()
    first_add = db.add.call_args_list[0][0][0]
    assert first_add.content == "Hello AI"
    assert first_add.sender == "user"


@pytest.mark.asyncio
@patch("app.api.v1.routes.chat.manager")
@patch("app.api.v1.routes.chat.build_trip_snapshot")
async def test_process_message_saves_ai_response(mock_snapshot, mock_manager):
    """Verify process_message saves the AI response to DB."""
    from app.api.v1.routes.chat import process_message

    mock_snapshot.return_value = {"trip_id": "trip_1", "destination": "Cairo", "days": []}
    mock_manager.send = AsyncMock()

    trip = make_mock_trip()
    conv = make_mock_conversation()
    db = make_mock_db_session()

    with patch("ai_engine.chat.conversation_agent.handle_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"message": "AI response here", "itinerary": None}
        await process_message(
            user_text="Plan trip",
            trip=trip,
            conversation=conv,
            profile_data={},
            ws_key="test_key",
            db=db,
            user_id="user_123",
            token="test_token",
        )

    # Find the AI message (second add call)
    adds = db.add.call_args_list
    ai_msg = adds[1][0][0]
    assert ai_msg.content == "AI response here"
    assert ai_msg.sender == "agent"


@pytest.mark.asyncio
@patch("app.api.v1.routes.chat.manager")
@patch("app.api.v1.routes.chat.build_trip_snapshot")
async def test_process_message_refreshes_itineraries_not_days(mock_snapshot, mock_manager):
    """Verify process_message refreshes 'itineraries' not 'days' on Trip (bug fix)."""
    from app.api.v1.routes.chat import process_message

    mock_snapshot.return_value = {"trip_id": "trip_1", "destination": "Cairo", "days": []}
    mock_manager.send = AsyncMock()

    trip = make_mock_trip()
    conv = make_mock_conversation()
    db = make_mock_db_session()

    with patch("ai_engine.chat.conversation_agent.handle_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {
            "message": "Plan",
            "itinerary": {"destination": "Cairo"},  # triggers actions
        }
        await process_message(
            user_text="Plan trip",
            trip=trip,
            conversation=conv,
            profile_data={},
            ws_key="test_key",
            db=db,
            user_id="user_123",
            token="test_token",
        )

    # Verify db.refresh was called with "itineraries", not "days"
    db.refresh.assert_called_with(trip, ["itineraries"])


# ── Tests: get_profile_data ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile_data_returns_empty_dict_when_no_profile():
    """get_profile_data should return {} when no profile exists."""
    from app.api.v1.routes.chat import get_profile_data

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    result = await get_profile_data("user_999", db)
    assert result == {}


@pytest.mark.asyncio
async def test_get_profile_data_returns_behavioral_fields():
    """get_profile_data should return the new BehavioralProfile fields."""
    from app.api.v1.routes.chat import get_profile_data

    profile = MagicMock()
    profile.pace_style = "ADVENTUROUS"
    profile.spending_style = "LUXURIOUS"
    profile.experience_lean = "CULTURE"
    profile.day_rhythm = "EARLY_BIRD"
    profile.attraction_preference = "POPULAR"
    profile.social_style = "SOCIAL"
    profile.interests = ["history"]
    profile.dining_preferences = ["fine dining"]
    profile.accommodation_preferences = ["resort"]
    profile.custom_interests = ["local markets"]
    profile.persona_title = "The Explorer"
    profile.persona_summary = "A curious traveler"

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = profile
    db.execute.return_value = mock_result

    result = await get_profile_data("user_001", db)

    assert result["pace_style"] == "ADVENTUROUS"
    assert result["spending_style"] == "LUXURIOUS"
    assert result["experience_lean"] == "CULTURE"
    assert result["day_rhythm"] == "EARLY_BIRD"
    assert result["attraction_preference"] == "POPULAR"
    assert result["social_style"] == "SOCIAL"
    assert result["interests"] == ["history"]
    assert result["persona_title"] == "The Explorer"
    assert result["persona_summary"] == "A curious traveler"
