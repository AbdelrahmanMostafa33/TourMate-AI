"""Unit tests for trips.py route endpoints."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime
from app.models.trip import Trip
from app.models.booking import Booking
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.enums import TripStatus, ItineraryStatus, StopStatus, TravelMode, BookingStatus, BookingType
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
    trip.status = TripStatus.planning
    trip.created_at = datetime.utcnow()
    trip.conversation_id = None
    trip.itineraries = []
    trip.updated_at = None
    trip.approved_at = None
    return trip


def make_mock_itinerary(trip_id="trip_001"):
    """Create a mock Itinerary with days and stops."""
    itinerary_id = "itin_001"

    stop = MagicMock(spec=ItineraryStop)
    stop.stop_id = "stop_001"
    stop.day_id = "day_001"
    stop.place_id = "place_1"
    stop.place_snapshot = {}
    stop.time_of_day = None
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
    day.day_id = "day_001"
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
    assert response["trip_id"] == "trip_001"
    assert response["destination"] == "Cairo, Egypt"
    assert len(response["itineraries"]) == 1


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
async def test_update_trip_status_sets_approved_at(mock_auth):
    """PATCH /trips/{trip_id}/status should set approved_at when status → active."""
    from app.api.v1.routes.trips import update_trip_status

    mock_auth.return_value = make_current_user()
    trip = make_mock_trip()

    assert trip.approved_at is None

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    body = TripStatusUpdate(status=TripStatus.active)
    response = await update_trip_status(
        trip_id="trip_001", body=body,
        current_user=make_current_user(), db=db,
    )

    # approved_at should be set
    assert trip.approved_at is not None
    assert response["approved_at"] is not None


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_update_trip_status_does_not_overwrite_approved_at(mock_auth):
    """PATCH /trips/{trip_id}/status should NOT overwrite existing approved_at."""
    from app.api.v1.routes.trips import update_trip_status

    mock_auth.return_value = make_current_user()
    trip = make_mock_trip()

    # Simulate already-approved trip
    existing_approved_at = datetime(2026, 6, 1, 12, 0, 0)
    trip.approved_at = existing_approved_at

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    body = TripStatusUpdate(status=TripStatus.active)
    await update_trip_status(
        trip_id="trip_001", body=body,
        current_user=make_current_user(), db=db,
    )

    # approved_at should remain unchanged
    assert trip.approved_at == existing_approved_at


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_update_trip_status_non_active_does_not_set_approved_at(mock_auth):
    """PATCH /trips/{trip_id}/status should NOT set approved_at for non-active status."""
    from app.api.v1.routes.trips import update_trip_status

    mock_auth.return_value = make_current_user()
    trip = make_mock_trip()

    assert trip.approved_at is None

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    # Set status to planning (not active)
    body = TripStatusUpdate(status=TripStatus.planning)
    response = await update_trip_status(
        trip_id="trip_001", body=body,
        current_user=make_current_user(), db=db,
    )

    # approved_at should NOT be set
    assert trip.approved_at is None
    assert response["approved_at"] is None


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


def test_build_auto_message_no_budget():
    """build_auto_message should not include budget section when None."""
    from app.api.v1.routes.trips import build_auto_message
    from app.schemas.trip import TripCreate

    data = TripCreate(destination="Tokyo, Japan")
    msg = build_auto_message(data, delta=3)
    assert "Tokyo" in msg


# ═════════════════════════════════════════════════════════════════════════════
# ── Tests: POST /trips/{trip_id}/cancel
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_trip_not_found(mock_auth):
    """POST /trips/{trip_id}/cancel should raise 404 when trip not found."""
    from fastapi import HTTPException
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc_info:
        await cancel_trip(
            trip_id="nonexistent",
            current_user=make_current_user(),
            db=db,
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_already_cancelled(mock_auth):
    """POST /trips/{trip_id}/cancel should raise 400 when trip is already cancelled."""
    from fastapi import HTTPException
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.cancelled

    result = MagicMock()
    result.scalar_one_or_none.return_value = trip

    db = AsyncMock()
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc_info:
        await cancel_trip(
            trip_id="trip_001",
            current_user=make_current_user(),
            db=db,
        )
    assert exc_info.value.status_code == 400
    assert "already cancelled" in exc_info.value.detail.lower()


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_with_hotel_booking_no_payment(mock_auth):
    """Cancel trip with one hotel booking (no payment) — should cancel and revert status."""
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    # Hotel booking with no payment
    hotel_booking = MagicMock(spec=Booking)
    hotel_booking.booking_id = "BK-HOTEL-001"
    hotel_booking.booking_type = BookingType.hotel
    hotel_booking.payment = None
    hotel_booking.status = BookingStatus.confirmed

    # execute returns trip first, then bookings list
    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [hotel_booking]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    # Mock the service methods so we can verify they're called
    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        mock_booking_svc.cancel_booking = AsyncMock()

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            response = await cancel_trip(
                trip_id="trip_001",
                current_user=make_current_user(),
                db=db,
            )

    # Verify hotel booking was cancelled
    mock_booking_svc.cancel_booking.assert_called_once_with("BK-HOTEL-001")
    mock_flight_svc.cancel_flight_booking.assert_not_called()

    # Verify trip status was reverted
    assert trip.status == TripStatus.cancelled

    # Verify response
    assert response["success"] is True
    assert response["trip_id"] == "trip_001"
    assert response["status"] == "cancelled"
    assert response["cancelled_bookings"] == ["BK-HOTEL-001"]
    assert response["refunded_payments"] == []

    db.commit.assert_called_once()


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_with_hotel_and_payment_refund(mock_auth):
    """Cancel trip with hotel booking that has a linked payment — should refund payment."""
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    # Hotel booking with linked payment
    payment = MagicMock()
    payment.payment_id = "PAY-001"

    hotel_booking = MagicMock(spec=Booking)
    hotel_booking.booking_id = "BK-HOTEL-001"
    hotel_booking.booking_type = BookingType.hotel
    hotel_booking.payment = payment
    hotel_booking.status = BookingStatus.confirmed

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [hotel_booking]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        mock_booking_svc.cancel_booking = AsyncMock()

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            response = await cancel_trip(
                trip_id="trip_001",
                current_user=make_current_user(),
                db=db,
            )

    mock_booking_svc.cancel_booking.assert_called_once_with("BK-HOTEL-001")

    assert response["cancelled_bookings"] == ["BK-HOTEL-001"]
    assert response["refunded_payments"] == ["PAY-001"]
    assert trip.status == TripStatus.cancelled


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_with_flight_booking(mock_auth):
    """Cancel trip with flight booking — should cancel flight and revert status."""
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    flight_booking = MagicMock(spec=Booking)
    flight_booking.booking_id = "BK-FLIGHT-001"
    flight_booking.booking_type = BookingType.flight
    flight_booking.payment = None
    flight_booking.status = BookingStatus.confirmed

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [flight_booking]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        mock_booking_svc.cancel_booking = AsyncMock()

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            response = await cancel_trip(
                trip_id="trip_001",
                current_user=make_current_user(),
                db=db,
            )

    # Verify flight booking was cancelled
    mock_flight_svc.cancel_flight_booking.assert_called_once_with(
        "BK-FLIGHT-001", "user_001"
    )
    mock_booking_svc.cancel_booking.assert_not_called()

    assert response["cancelled_bookings"] == ["BK-FLIGHT-001"]
    assert response["refunded_payments"] == []
    assert trip.status == TripStatus.cancelled


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_with_both_hotel_and_flight(mock_auth):
    """Cancel trip with both hotel and flight bookings — should cancel both and refund all payments."""
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    # Hotel with payment
    hotel_payment = MagicMock()
    hotel_payment.payment_id = "PAY-HOTEL"
    hotel_booking = MagicMock(spec=Booking)
    hotel_booking.booking_id = "BK-HOTEL"
    hotel_booking.booking_type = BookingType.hotel
    hotel_booking.payment = hotel_payment
    hotel_booking.status = BookingStatus.confirmed

    # Flight with payment
    flight_payment = MagicMock()
    flight_payment.payment_id = "PAY-FLIGHT"
    flight_booking = MagicMock(spec=Booking)
    flight_booking.booking_id = "BK-FLIGHT"
    flight_booking.booking_type = BookingType.flight
    flight_booking.payment = flight_payment
    flight_booking.status = BookingStatus.confirmed

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [
        hotel_booking, flight_booking,
    ]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        mock_booking_svc.cancel_booking = AsyncMock()

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            response = await cancel_trip(
                trip_id="trip_001",
                current_user=make_current_user(),
                db=db,
            )

    # Verify both services called with correct args
    mock_booking_svc.cancel_booking.assert_called_once_with("BK-HOTEL")
    mock_flight_svc.cancel_flight_booking.assert_called_once_with(
        "BK-FLIGHT", "user_001"
    )

    # Verify response includes both bookings and payments
    assert set(response["cancelled_bookings"]) == {"BK-HOTEL", "BK-FLIGHT"}
    assert set(response["refunded_payments"]) == {"PAY-HOTEL", "PAY-FLIGHT"}
    assert trip.status == TripStatus.cancelled


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_skips_already_cancelled_booking(mock_auth):
    """Cancel trip — should gracefully handle already-cancelled bookings without raising."""
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    # One cancelled booking
    cancelled_booking = MagicMock(spec=Booking)
    cancelled_booking.booking_id = "BK-CANCEL"
    cancelled_booking.booking_type = BookingType.hotel
    cancelled_booking.payment = None
    cancelled_booking.status = BookingStatus.cancelled

    # One active booking
    active_booking = MagicMock(spec=Booking)
    active_booking.booking_id = "BK-ACTIVE"
    active_booking.booking_type = BookingType.hotel
    active_booking.payment = None
    active_booking.status = BookingStatus.confirmed

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [
        cancelled_booking, active_booking,
    ]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        # First call raises ValueError (already cancelled), second succeeds
        mock_booking_svc.cancel_booking = AsyncMock(side_effect=[
            ValueError("already cancelled"),
            None,
        ])

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            response = await cancel_trip(
                trip_id="trip_001",
                current_user=make_current_user(),
                db=db,
            )

    # Both bookings should appear as cancelled (graceful handling)
    assert set(response["cancelled_bookings"]) == {"BK-CANCEL", "BK-ACTIVE"}
    assert response["trip_id"] == "trip_001"
    assert trip.status == TripStatus.cancelled


@pytest.mark.asyncio
@patch("app.api.v1.routes.trips.get_current_user")
async def test_cancel_trip_fails_on_unexpected_booking_error(mock_auth):
    """Cancel trip — should raise 400 if a booking fails with an unexpected error."""
    from fastapi import HTTPException
    from app.api.v1.routes.trips import cancel_trip

    mock_auth.return_value = make_current_user()

    trip = make_mock_trip()
    trip.status = TripStatus.booking_confirmed

    hotel_booking = MagicMock(spec=Booking)
    hotel_booking.booking_id = "BK-HOTEL"
    hotel_booking.booking_type = BookingType.hotel
    hotel_booking.payment = None
    hotel_booking.status = BookingStatus.confirmed

    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = trip

    bookings_result = MagicMock()
    bookings_result.scalars.return_value.all.return_value = [hotel_booking]

    db = AsyncMock()
    db.execute.side_effect = [trip_result, bookings_result]

    with patch("app.api.v1.routes.trips.BookingService") as mock_booking_svc_cls:
        mock_booking_svc = MagicMock()
        mock_booking_svc_cls.return_value = mock_booking_svc
        mock_booking_svc.cancel_booking = AsyncMock(
            side_effect=ValueError("Booking cannot be cancelled in its current state")
        )

        with patch("app.api.v1.routes.trips.FlightService") as mock_flight_svc_cls:
            mock_flight_svc = MagicMock()
            mock_flight_svc_cls.return_value = mock_flight_svc
            mock_flight_svc.cancel_flight_booking = AsyncMock()

            with pytest.raises(HTTPException) as exc_info:
                await cancel_trip(
                    trip_id="trip_001",
                    current_user=make_current_user(),
                    db=db,
                )

    assert exc_info.value.status_code == 400
    assert "Failed to cancel booking" in exc_info.value.detail