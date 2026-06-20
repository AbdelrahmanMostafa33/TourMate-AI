"""Unit tests for trips.py route endpoints."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.enums import TripStatus, ItineraryStatus, StopStatus, TravelMode
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.models.enums import TripStatus, ItineraryStatus
from app.schemas.trip import TripCreate, TripStatusUpdate


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_trip_create_data():
    """Create a valid TripCreate request body."""
    return {
        "destination": "Cairo, Egypt",
        "trip_name": "Cairo Adventure",
        "start_date": "2026-07-01",
        "end_date": "2026-07-03",
        "number_of_travelers": 2,
        "budget": 1500.0,
    }


def make_mock_trip(trip_id="trip_001", user_id="user_001"):
    """Create a mock Trip object matching the new model."""
    trip = MagicMock(spec=Trip)
    trip.trip_id = trip_id
    trip.user_id = user_id
    trip.trip_name = "Cairo Adventure"
    trip.destination = "Cairo, Egypt"
    trip.start_date = date(2026, 7, 1)
    trip.end_date = date(2026, 7, 3)
    trip.number_of_travelers = 2
    trip.budget = 1500.0
    trip.status = TripStatus.planning
    trip.created_at = datetime.utcnow()
    trip.itineraries = []
    return trip


def make_mock_itinerary(trip_id="trip_001"):
    """Create a mock Itinerary with days and stops."""
    itinerary_id = "itin_001"

    stop = MagicMock(spec=ItineraryStop)
    stop.stop_id = 1
    stop.day_id = 1
    stop.place_id = "place_1"
    stop.place_snapshot = {}
    stop.scheduled_time = None
    stop.duration_minutes = 60
    stop.order_in_day = 1
    stop.minutes_from_prev_stop = None
    stop.travel_mode = TravelMode.walking
    stop.estimated_cost = 10.0
    stop.ai_notes = "Test"
    stop.user_notes = None
    stop.status = StopStatus.planned
    stop.created_at = datetime.utcnow()

    day = MagicMock(spec=Day)
    day.day_id = 1
    day.itinerary_id = itinerary_id
    day.day_number = 1
    day.date = date(2026, 7, 1)
    day.theme = None
    day.description = None
    day.stops = [stop]

    itinerary = MagicMock(spec=Itinerary)
    itinerary.itinerary_id = itinerary_id
    itinerary.trip_id = trip_id
    itinerary.version_number = 1
    itinerary.description = None
    itinerary.status = ItineraryStatus.draft
    itinerary.created_at = datetime.utcnow()
    itinerary.updated_at = datetime.utcnow()
    itinerary.days = [day]

    return itinerary

def make_mock_user(user_id="user_001"):
    """Create a mock User."""
    user = MagicMock()
    user.user_id = user_id
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.phone_number = "+1234567890"
    user.home_city = "New York"
    user.registration_date = datetime.utcnow()
    user.quiz_completed = True
    user.profile_id = None
    return user


def make_current_user(uid="user_001"):
    """Create a mock current_user dict from auth."""
    return {"uid": uid, "email": "test@example.com"}


def make_trip_create_obj():
    """Create a TripCreate Pydantic object for direct function calls."""
    return TripCreate(**make_trip_create_data())


# ── Tests: POST /trips/ ─────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_create_trip_success(mock_auth):
    """POST /trips/ should create trip, itinerary, days, conversation, and return response."""
    from app.api.v1.routes.trips import create_trip

    mock_auth.return_value = make_current_user()
    data = make_trip_create_obj()
    db = AsyncMock()

    # After commit, fetch returns the full trip
    fetch_result = MagicMock()
    full_trip = make_mock_trip()
    full_trip.itineraries = [make_mock_itinerary()]
    fetch_result.scalar_one.return_value = full_trip
    db.execute.return_value = fetch_result

    response = await create_trip(data=data, current_user=make_current_user(), db=db)

    # Verify trip was created with correct fields
    db.add.assert_called()
    add_calls = db.add.call_args_list

    # First add: Trip
    trip_obj = add_calls[0][0][0]
    assert trip_obj.trip_id is not None
    assert trip_obj.user_id == "user_001"
    assert trip_obj.destination == "Cairo, Egypt"
    assert trip_obj.trip_name == "Cairo Adventure"
    assert trip_obj.number_of_travelers == 2

    # Response should have auto_message and conversation_id
    assert "auto_message" in response
    assert "conversation_id" in response
    assert "Cairo" in response["auto_message"]


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_create_trip_builds_correct_auto_message(mock_auth):
    """POST /trips/ should include destination, dates, travelers, budget in auto_message."""
    from app.api.v1.routes.trips import create_trip

    mock_auth.return_value = make_current_user()
    data = make_trip_create_obj()
    db = AsyncMock()

    fetch_result = MagicMock()
    full_trip = make_mock_trip()
    full_trip.itineraries = [make_mock_itinerary()]
    fetch_result.scalar_one.return_value = full_trip
    db.execute.return_value = fetch_result

    response = await create_trip(data=data, current_user=make_current_user(), db=db)

    msg = response["auto_message"]
    assert "Cairo" in msg
    assert "2 travelers" in msg
    assert "$1500" in msg
    assert "culture" in msg


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_create_trip_creates_correct_number_of_days(mock_auth):
    """POST /trips/ should create 3 days for a 3-day trip."""
    from app.api.v1.routes.trips import create_trip

    mock_auth.return_value = make_current_user()
    data = make_trip_create_obj()
    db = AsyncMock()

    fetch_result = MagicMock()
    full_trip = make_mock_trip()
    full_trip.itineraries = [make_mock_itinerary()]
    fetch_result.scalar_one.return_value = full_trip
    db.execute.return_value = fetch_result

    await create_trip(data=data, current_user=make_current_user(), db=db)

    # Count Day objects added (3 days for July 1-3)
    day_adds = [c for c in db.add.call_args_list if "Day" in str(type(c[0][0]))]
    assert len(day_adds) == 3


# ── Tests: GET /trips/ ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_get_all_trips_returns_user_trips(mock_auth):
    """GET /trips/ should return all trips for the authenticated user."""
    from app.api.v1.routes.trips import get_all_trips

    mock_auth.return_value = make_current_user()
    trip1 = make_mock_trip(trip_id="trip_001")
    trip2 = make_mock_trip(trip_id="trip_002")

    result = MagicMock()
    result.scalars.return_value.all.return_value = [trip1, trip2]

    db = AsyncMock()
    db.execute.return_value = result

    trips = await get_all_trips(current_user=make_current_user(), db=db)
    assert len(trips) == 2


# ── Tests: GET /trips/{trip_id} ─────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_get_trip_success(mock_auth):
    """GET /trips/{trip_id} should return the trip with itineraries."""
    from app.api.v1.routes.trips import get_trip

    mock_auth.return_value = make_current_user()
    trip = make_mock_trip()
    trip.itineraries = [make_mock_itinerary()]

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    response = await get_trip(trip_id="trip_001", current_user=make_current_user(), db=db)
    assert response.trip_id == "trip_001"
    assert response.destination == "Cairo, Egypt"
    assert len(response.itineraries) == 1


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_get_trip_not_found(mock_auth):
    """GET /trips/{trip_id} should raise 404 when trip not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.trips import get_trip

    mock_auth.return_value = make_current_user()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc_info:
        await get_trip(trip_id="nonexistent", current_user=make_current_user(), db=db)
    assert exc_info.value.status_code == 404


# ── Tests: PATCH /trips/{trip_id}/status ────────────────────────────────────

@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_update_trip_status_success(mock_auth):
    """PATCH /trips/{trip_id}/status should update trip status."""
    from app.api.v1.routes.trips import update_trip_status

    mock_auth.return_value = make_current_user()  # ← fixed: removed extra indent
    trip = make_mock_trip()

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    body = TripStatusUpdate(status=TripStatus.active)
    response = await update_trip_status(
        trip_id="trip_001", body=body,
        current_user=make_current_user(), db=db,
    )

    assert trip.status == TripStatus.active
    assert response["status"] == TripStatus.active
    db.commit.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_update_trip_status_not_found(mock_auth):
    """PATCH /trips/{trip_id}/status should raise 404 when trip not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.trips import update_trip_status

    mock_auth.return_value = make_current_user()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = result

    body = TripStatusUpdate(status=TripStatus.active)
    with pytest.raises(HTTPException) as exc_info:
        await update_trip_status(
            trip_id="nonexistent", body=body,
            current_user=make_current_user(), db=db,
        )
    assert exc_info.value.status_code == 404


# ── Tests: build_auto_message helper ─────────────────────────────────────────

def test_build_auto_message_includes_budget():
    """build_auto_message should include budget when provided."""
    from app.api.v1.routes.trips import build_auto_message
    from app.schemas.trip import TripCreate

    data = TripCreate(
        destination="Paris, France",
        budget=2000.0,
    )
    msg = build_auto_message(data, delta=2)
    assert "Paris" in msg
    assert "$2000" in msg


def test_build_auto_message_no_budget():
    """build_auto_message should not include budget section when None."""
    from app.api.v1.routes.trips import build_auto_message
    from app.schemas.trip import TripCreate

    data = TripCreate(destination="Tokyo, Japan")
    msg = build_auto_message(data, delta=3)
    assert "Tokyo" in msg