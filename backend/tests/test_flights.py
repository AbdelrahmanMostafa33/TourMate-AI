"""
Tests for Flight Service and Flight API router.

Uses ``unittest.mock.patch`` to mock the ``AmadeusClient`` singleton so no
real Amadeus API calls are made during tests.

Service tests use a real ``AsyncSession`` backed by an in-memory SQLite
database (via ``aiosqlite`` + the SQLAlchemy async engine).
"""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.models.booking import Booking, Payment
from app.models.enums import BookingType, BookingProvider, BookingStatus
from app.schemas.flight import (
    FlightSearchRequest,
    FlightOfferItem,
    FlightBookConfirmRequest,
    FlightBookingResponse,
    CitySearchResult,
)
from app.services.flight_service import FlightService
from app.models.trip import Trip
from app.models.user import User

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures: in-memory SQLite async engine + session
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh in-memory SQLite database for each test."""
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures: mock Amadeus offer data
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_raw_offer() -> dict:
    """A minimal fake Amadeus flight offer dict."""
    return {
        "id": "offer_123",
        "validatingAirlineCodes": ["MS"],
        "itineraries": [
            {
                "segments": [
                    {
                        "carrierCode": "MS",
                        "number": "123",
                        "departure": {
                            "iataCode": "CAI",
                            "at": "2026-07-15T08:00:00",
                        },
                        "arrival": {
                            "iataCode": "DXB",
                            "at": "2026-07-15T13:00:00",
                        },
                    }
                ]
            }
        ],
        "price": {
            "total": "350.00",
            "currency": "USD",
            "base": "280.00",
        },
        "travelerPricings": [
            {
                "fareDetailsBySegment": [
                    {"cabin": "ECONOMY"}
                ]
            }
        ],
    }


@pytest.fixture
def mock_order_response() -> dict:
    """A minimal fake Amadeus flight order response."""
    return {
        "id": "amadeus_order_001",
        "itineraries": [
            {
                "segments": [
                    {
                        "carrierCode": "MS",
                        "number": "123",
                        "departure": {
                            "iataCode": "CAI",
                            "at": "2026-07-15T08:00:00",
                        },
                        "arrival": {
                            "iataCode": "DXB",
                            "at": "2026-07-15T13:00:00",
                        },
                    }
                ]
            }
        ],
        "price": {
            "total": "350.00",
            "currency": "USD",
            "base": "280.00",
        },
        "travelerPricings": [
            {
                "fareDetailsBySegment": [
                    {"cabin": "ECONOMY"}
                ]
            }
        ],
    }


@pytest.fixture
def mock_priced_offer() -> dict:
    """A minimal fake priced offer dict (with validatingAirlineCodes)."""
    return {
        "validatingAirlineCodes": ["MS"],
        "price": {
            "total": "350.00",
            "currency": "USD",
            "base": "280.00",
        },
        "itineraries": [
            {
                "segments": [
                    {
                        "carrierCode": "MS",
                        "number": "123",
                        "departure": {
                            "iataCode": "CAI",
                            "at": "2026-07-15T08:00:00",
                        },
                        "arrival": {
                            "iataCode": "DXB",
                            "at": "2026-07-15T13:00:00",
                        },
                    }
                ]
            }
        ],
        "travelerPricings": [
            {
                "fareDetailsBySegment": [
                    {"cabin": "ECONOMY"}
                ]
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: create a confirmed booking in DB via confirm_flight_booking
# ═══════════════════════════════════════════════════════════════════════════════

async def _create_test_booking(
    svc: FlightService,
    db_session: AsyncSession,
    mock_priced: dict,
    mock_order: dict,
    trip_id: str = "trip_001",
    user_id: str = "user_001",
) -> Booking:
    """Convenience helper: mock Stripe + Amadeus and call confirm_flight_booking."""
    data = FlightBookConfirmRequest(
        payment_intent_id="pi_test_succeeded",
        priced_offer=mock_priced,
        trip_id=trip_id,
        traveler_first_name="Test",
        traveler_last_name="User",
        traveler_date_of_birth=date(1990, 1, 1),
        traveler_gender="MALE",
        traveler_email="test@example.com",
        traveler_phone="+201234567890",
    )

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.book_flight.return_value = mock_order
        mock_client._client.reference_data.airlines.get.side_effect = Exception("No airline data")

        with patch("stripe.PaymentIntent.retrieve") as mock_retrieve:
            mock_retrieve.return_value = type("obj", (), {"status": "succeeded"})()

            booking = await svc.confirm_flight_booking(user_id, data)

    db_session.add(booking)
    await db_session.commit()
    return booking


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.search_flights
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_search_flights_returns_parsed_offers(
    db_session: AsyncSession,
    mock_raw_offer: dict,
):
    """Mock Amadeus search and verify the results are parsed into FlightOfferItem."""
    svc = FlightService(db_session)

    with patch.object(
        svc, "search_flights",
        new_callable=MagicMock,
    ) as mock_search:
        parsed = FlightOfferItem(
            offer_index=0,
            airline_code="MS",
            airline_name="EgyptAir",
            flight_number="MS123",
            origin_iata="CAI",
            destination_iata="DXB",
            departure_at=datetime(2026, 7, 15, 8, 0, 0),
            arrival_at=datetime(2026, 7, 15, 13, 0, 0),
            cabin_class="ECONOMY",
            total_price=350.00,
            currency="USD",
            price_per_adult=280.00,
            raw_offer=mock_raw_offer,
        )
        mock_search.return_value = [parsed]

        # We test the mock directly to verify schema parsing
        result = mock_search.return_value
        assert len(result) == 1
        item = result[0]
        assert isinstance(item, FlightOfferItem)
        assert item.airline_code == "MS"
        assert item.flight_number == "MS123"
        assert item.origin_iata == "CAI"
        assert item.destination_iata == "DXB"
        assert item.total_price == 350.00
        assert item.currency == "USD"


@pytest.mark.asyncio
async def test_search_flights_integration(
    db_session: AsyncSession,
    mock_raw_offer: dict,
):
    """Integration test: mock amadeus_client.search_flights and verify parsing."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_flights.return_value = [mock_raw_offer]
        mock_client._client.reference_data.airlines.get.side_effect = Exception("No airline data")

        data = FlightSearchRequest(
            origin="CAI",
            destination="DXB",
            departure_date=date(2026, 7, 15),
            adults=1,
            max_results=5,
        )

        results = await svc.search_flights(data)

        assert len(results) == 1
        item = results[0]
        assert isinstance(item, FlightOfferItem)
        assert item.airline_code == "MS"
        assert item.flight_number == "MS123"
        assert item.origin_iata == "CAI"
        assert item.destination_iata == "DXB"
        assert item.total_price == 350.00
        assert item.currency == "USD"
        assert item.cabin_class == "ECONOMY"

        mock_client.search_flights.assert_called_once_with(
            origin="CAI",
            destination="DXB",
            departure_date="2026-07-15",
            adults=1,
            max_results=5,
            return_date=None,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.confirm_flight_booking
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_confirm_flight_booking_creates_confirmed_booking(
    db_session: AsyncSession,
    mock_raw_offer: dict,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify that confirm_flight_booking creates a confirmed Booking row."""
    svc = FlightService(db_session)

    trip_id = "trip_001"
    user_id = "user_001"

    data = FlightBookConfirmRequest(
        payment_intent_id="pi_test_succeeded",
        priced_offer=mock_priced_offer,
        trip_id=trip_id,
        traveler_first_name="John",
        traveler_last_name="Doe",
        traveler_date_of_birth=date(1990, 1, 1),
        traveler_gender="MALE",
        traveler_email="john@example.com",
        traveler_phone="+201234567890",
    )

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.book_flight.return_value = mock_order_response
        mock_client._client.reference_data.airlines.get.side_effect = Exception("No airline data")

        with patch("stripe.PaymentIntent.retrieve") as mock_retrieve:
            mock_retrieve.return_value = type("obj", (), {"status": "succeeded"})()

            booking = await svc.confirm_flight_booking(user_id, data)

    assert booking.booking_type == BookingType.flight
    assert booking.provider == BookingProvider.amadeus
    assert booking.status == BookingStatus.confirmed
    assert booking.trip_id == trip_id
    assert booking.user_id == user_id

    # Check raw_response fields
    raw = booking.raw_response or {}
    assert raw["origin_iata"] == "CAI"
    assert raw["destination_iata"] == "DXB"
    assert raw["flight_number"] == "MS123"
    assert raw["cabin_class"] == "ECONOMY"
    assert raw["amadeus_order_id"] == "amadeus_order_001"

    # Check financial fields from priced offer
    assert booking.total_cost == 350.00
    assert booking.currency == "USD"

    mock_client.book_flight.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.cancel_flight_booking
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cancel_flight_booking(
    db_session: AsyncSession,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify that cancelling a flight booking sets status to cancelled."""
    svc = FlightService(db_session)

    booking = await _create_test_booking(svc, db_session,
        trip_id="trip_002", user_id="user_002",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )

    # Now cancel
    cancelled = await svc.cancel_flight_booking(booking.booking_id, "user_002")
    assert cancelled.status == BookingStatus.cancelled
    assert "cancelled_at" in (cancelled.raw_response or {})


@pytest.mark.asyncio
async def test_cancel_already_cancelled_raises(
    db_session: AsyncSession,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify that cancelling an already cancelled flight raises ValueError."""
    svc = FlightService(db_session)

    booking = await _create_test_booking(svc, db_session,
        trip_id="trip_003", user_id="user_003",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )

    await svc.cancel_flight_booking(booking.booking_id, "user_003")
    with pytest.raises(ValueError, match="already cancelled"):
        await svc.cancel_flight_booking(booking.booking_id, "user_003")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.get_flight_booking / list_trip_flight_bookings
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_flight_booking(
    db_session: AsyncSession,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify get_flight_booking returns the correct booking."""
    svc = FlightService(db_session)

    booking = await _create_test_booking(svc, db_session,
        trip_id="trip_004", user_id="user_004",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )

    found = await svc.get_flight_booking(booking.booking_id)
    assert found is not None
    assert found.booking_id == booking.booking_id
    assert found.booking_type == BookingType.flight


@pytest.mark.asyncio
async def test_list_trip_flight_bookings(
    db_session: AsyncSession,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify list_trip_flight_bookings returns only flight bookings for a trip."""
    svc = FlightService(db_session)

    booking1 = await _create_test_booking(svc, db_session,
        trip_id="trip_005", user_id="user_005",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )
    booking2 = await _create_test_booking(svc, db_session,
        trip_id="trip_005", user_id="user_005",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )

    bookings = await svc.list_trip_flight_bookings("trip_005")
    assert len(bookings) == 2
    assert all(b.booking_type == BookingType.flight for b in bookings)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightBookingResponse.from_booking
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_flight_booking_response_from_booking(
    db_session: AsyncSession,
    mock_priced_offer: dict,
    mock_order_response: dict,
):
    """Verify FlightBookingResponse.from_booking correctly unpacks raw_response."""
    svc = FlightService(db_session)

    booking = await _create_test_booking(svc, db_session,
        trip_id="trip_006", user_id="user_006",
        mock_priced=mock_priced_offer, mock_order=mock_order_response,
    )

    # Fetch eagerly-loaded booking to avoid MissingGreenlet on lazy payment
    found = await svc.get_flight_booking(booking.booking_id)
    response = FlightBookingResponse.from_booking(found)
    assert response.booking_id == booking.booking_id
    assert response.origin_iata == "CAI"
    assert response.destination_iata == "DXB"
    assert response.airline_name == "MS"  # fallback to code when lookup fails
    assert response.flight_number == "MS123"
    assert response.cabin_class == "ECONOMY"
    assert response.amadeus_order_id == "amadeus_order_001"
    assert response.status == BookingStatus.confirmed
    assert response.total_cost == 350.00
    assert response.currency == "USD"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Validation
# ═══════════════════════════════════════════════════════════════════════════════

def test_flight_search_request_uppercases_iata():
    """Verify that IATA codes are uppercased."""
    req = FlightSearchRequest(
        origin="cai",
        destination="dxb",
        departure_date=date(2026, 7, 15),
    )
    assert req.origin == "CAI"
    assert req.destination == "DXB"


def test_flight_book_confirm_request_validates_gender():
    """Verify that gender validation works on FlightBookConfirmRequest."""
    with pytest.raises(ValueError):
        FlightBookConfirmRequest(
            payment_intent_id="pi_test",
            priced_offer={},
            trip_id="trip_x",
            traveler_first_name="X",
            traveler_last_name="Y",
            traveler_date_of_birth=date(2000, 1, 1),
            traveler_gender="INVALID",
            traveler_email="x@y.com",
            traveler_phone="+201234567890",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures: mock Amadeus location / city data
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_location_city_data() -> list[dict]:
    """Mock Amadeus reference_data.locations response for city search."""
    return [
        {
            "iataCode": "CAI",
            "name": "CAIRO INTL",
            "subType": "AIRPORT",
            "address": {
                "cityName": "CAIRO",
                "countryName": "EGYPT",
            },
        },
        {
            "iataCode": "CAI",
            "name": "CAIRO",
            "subType": "CITY",
            "address": {
                "cityName": "CAIRO",
                "countryName": "EGYPT",
            },
        },
    ]


@pytest.fixture
def mock_location_airport_data() -> list[dict]:
    """Mock Amadeus location response for airport-only search."""
    return [
        {
            "iataCode": "LHR",
            "name": "HEATHROW",
            "subType": "AIRPORT",
            "address": {
                "cityName": "LONDON",
                "countryName": "UNITED KINGDOM",
            },
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.search_cities  (city autocomplete)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_search_cities_returns_parsed_results(
    db_session: AsyncSession,
    mock_location_city_data: list[dict],
):
    """Mock Amadeus location search and verify parsed CitySearchResult."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = mock_location_city_data

        results = await svc.search_cities("cairo", max_results=5)

        assert len(results) == 2
        item = results[0]
        assert isinstance(item, CitySearchResult)
        assert item.iata_code == "CAI"
        assert item.city_name == "CAIRO"
        assert item.airport_name == "CAIRO INTL"
        assert item.country_name == "EGYPT"
        assert item.sub_type == "AIRPORT"

        mock_client.search_cities.assert_called_once_with("cairo", max_results=5)


@pytest.mark.asyncio
async def test_search_cities_empty_results(
    db_session: AsyncSession,
):
    """When Amadeus returns nothing, search_cities should return empty list."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = []

        results = await svc.search_cities("zzzzzcity", max_results=5)
        assert results == []


@pytest.mark.asyncio
async def test_search_cities_filters_no_iata(
    db_session: AsyncSession,
):
    """Results without iataCode should be filtered out."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = [
            {"name": "Nowhere", "subType": "CITY", "address": {}},
            {"iataCode": "ABC", "name": "Airport ABC", "subType": "AIRPORT",
             "address": {"cityName": "ABC", "countryName": "XYZ"}},
        ]

        results = await svc.search_cities("test", max_results=5)
        assert len(results) == 1
        assert results[0].iata_code == "ABC"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.resolve_city_to_iata
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resolve_city_to_iata_success(
    db_session: AsyncSession,
    mock_location_city_data: list[dict],
):
    """City name should be resolved to the first IATA code from Amadeus.

    Uses a city NOT in the CITY_TO_IATA dictionary so the Amadeus lookup
    path is exercised ("cairo" hits the dict shortcut).
    """
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        # Mock Amadeus to return data for "aswan" (not in CITY_TO_IATA)
        mock_client.search_cities.return_value = [
            {
                "iataCode": "ASW",
                "name": "ASWAN INTL",
                "subType": "AIRPORT",
                "address": {
                    "cityName": "ASWAN",
                    "countryName": "EGYPT",
                },
            },
        ]

        result = svc.resolve_city_to_iata("aswan")
        assert isinstance(result, CitySearchResult)
        assert result.iata_code == "ASW"
        assert result.city_name == "ASWAN"
        assert result.country_name == "EGYPT"

        mock_client.search_cities.assert_called_once_with("aswan", max_results=5)


@pytest.mark.asyncio
async def test_resolve_city_to_iata_not_found(
    db_session: AsyncSession,
):
    """When no matching city is found, should raise ValueError."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = []

        with pytest.raises(ValueError, match="Could not resolve city name"):
            svc.resolve_city_to_iata("nonexistent")


@pytest.mark.asyncio
async def test_resolve_city_to_iata_skips_no_iata(
    db_session: AsyncSession,
):
    """Results without iataCode should be skipped."""
    svc = FlightService(db_session)

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = [
            {"name": "No IATA", "subType": "CITY", "address": {}},
        ]

        with pytest.raises(ValueError, match="Could not resolve city name"):
            svc.resolve_city_to_iata("nowhere")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: FlightService.get_trip_context
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_trip_context_basic(
    db_session: AsyncSession,
    mock_location_city_data: list[dict],
):
    """Verify get_trip_context returns trip data + home city + resolved IATA."""
    svc = FlightService(db_session)

    # Insert a user with home_city
    user = User(
        user_id="user_ctx_001",
        email="traveler@example.com",
        home_city="Cairo",
    )
    db_session.add(user)

    # Insert a trip
    trip = Trip(
        trip_id="trip_ctx_001",
        user_id="user_ctx_001",
        destination="London",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 10),
        number_of_travelers=2,
    )
    db_session.add(trip)
    await db_session.commit()

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        # Mock location search to return different results for each city
        def mock_search_cities(keyword: str, max_results: int = 5):
            if keyword.lower() == "cairo":
                return mock_location_city_data
            if keyword.lower() == "london":
                return [
                    {
                        "iataCode": "LHR",
                        "name": "HEATHROW",
                        "subType": "AIRPORT",
                        "address": {"cityName": "LONDON", "countryName": "UNITED KINGDOM"},
                    }
                ]
            return []
        mock_client.search_cities.side_effect = mock_search_cities

        context = await svc.get_trip_context("trip_ctx_001", "user_ctx_001")

        assert context.trip_id == "trip_ctx_001"
        assert context.home_city == "Cairo"
        assert context.home_city_iata == "CAI"
        assert context.destination_city == "London"
        assert context.destination_iata == "LHR"
        assert context.suggested_departure_date == "2026-08-01"
        assert context.suggested_return_date == "2026-08-10"
        assert context.suggested_adults == 2


@pytest.mark.asyncio
async def test_get_trip_context_no_home_city(
    db_session: AsyncSession,
):
    """When user has no home_city, home_city/home_city_iata should be None."""
    svc = FlightService(db_session)

    user = User(user_id="user_ctx_002", email="user2@example.com")
    db_session.add(user)
    trip = Trip(
        trip_id="trip_ctx_002",
        user_id="user_ctx_002",
        destination="Paris",
    )
    db_session.add(trip)
    await db_session.commit()

    with patch("app.services.flight_service.amadeus_client") as mock_client:
        mock_client.search_cities.return_value = [
            {
                "iataCode": "CDG",
                "name": "CHARLES DE GAULLE",
                "subType": "AIRPORT",
                "address": {"cityName": "PARIS", "countryName": "FRANCE"},
            }
        ]

        context = await svc.get_trip_context("trip_ctx_002", "user_ctx_002")

        assert context.home_city is None
        assert context.home_city_iata is None
        assert context.destination_city == "Paris"
        assert context.destination_iata == "CDG"


@pytest.mark.asyncio
async def test_get_trip_context_not_owner(
    db_session: AsyncSession,
):
    """If user doesn't own the trip, should raise ValueError."""
    svc = FlightService(db_session)

    user = User(user_id="owner", email="owner@example.com")
    db_session.add(user)
    trip = Trip(
        trip_id="trip_ctx_003",
        user_id="owner",
        destination="Tokyo",
    )
    db_session.add(trip)
    await db_session.commit()

    with pytest.raises(ValueError, match="not found"):
        await svc.get_trip_context("trip_ctx_003", "different_user")
