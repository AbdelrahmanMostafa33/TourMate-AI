"""
Integration tests for Flight API routes.

Tests all flight endpoints using FastAPI TestClient with:
- In-memory SQLite database (asyncio)
- Auth dependency override (no Firebase needed)
- Mocked Amadeus client (no real API calls)

Covers public and auth-required endpoints, happy paths, and error cases.
"""

import json
from datetime import date, datetime
from unittest.mock import patch, MagicMock
from typing import AsyncGenerator

import pytest
from pytest import FixtureRequest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.user import User
from app.models.booking import Booking, Payment
from app.models.enums import BookingType, BookingProvider, BookingStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Shared test constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID = "test_user_flight_001"
OTHER_USER_ID = "other_user_flight"
NONEXISTENT_ID = "nonexistent_123"
TRIP_ID = "test_trip_flight_001"
HOME_CITY = "Alexandria"
DESTINATION = "Cairo"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Backup and restore app.dependency_overrides around each test."""
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _override_get_current_user():
    return {"uid": TEST_USER_ID}


def _override_get_other_user():
    return {"uid": OTHER_USER_ID}


@pytest.fixture
def mock_amadeus():
    """Mock the amadeus_client singleton for all API route tests.

    Provides a consistent mock that can be extended per-test via
    ``mock_amadeus.search_cities.return_value = [...]`` etc.
    """
    with patch("app.services.flight_service.amadeus_client") as mock:
        # Default behaviour: API reaches out but returns empty
        mock.search_cities.return_value = []
        mock.search_flights.return_value = []
        mock.price_flight.return_value = {}
        mock.book_flight.return_value = {}
        mock._client.reference_data.airlines.get.side_effect = \
            Exception("No airline data")
        yield mock


@pytest.fixture
async def seeded_db(db_session) -> None:
    """Seed the database with a test user and trip."""
    user = User(
        user_id=TEST_USER_ID,
        email="test_flight_user@tourmate.com",
        full_name="Test Flight User",
        home_city=HOME_CITY,
    )
    db_session.add(user)

    trip = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        destination=DESTINATION,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 10),
        number_of_travelers=2,
        trip_name="Test Cairo Trip",
    )
    db_session.add(trip)
    await db_session.commit()


@pytest.fixture
def raw_offer() -> dict:
    """A synthetic Amadeus flight offer for testing."""
    return {
        "id": "OFFER_TEST",
        "validatingAirlineCodes": ["MS"],
        "itineraries": [{
            "segments": [{
                "carrierCode": "MS",
                "number": "777",
                "departure": {"iataCode": "HBE", "at": "2026-08-01T08:00:00"},
                "arrival": {"iataCode": "CAI", "at": "2026-08-01T09:00:00"},
            }]
        }],
        "price": {"total": "150.00", "currency": "USD", "base": "130.00"},
        "travelerPricings": [
            {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
        ],
    }


@pytest.fixture
def mock_city_data() -> list[dict]:
    """Mock Amadeus location response for city autocomplete."""
    return [
        {
            "iataCode": "HBE",
            "name": "BORG EL ARAB",
            "subType": "AIRPORT",
            "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
        },
        {
            "iataCode": "ALY",
            "name": "ALEXANDRIA",
            "subType": "CITY",
            "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
        },
    ]


@pytest.fixture
def mock_offer_data() -> list[dict]:
    """Mock Amadeus flight search response."""
    return [
        {
            "id": "OFFER_SEARCH_1",
            "validatingAirlineCodes": ["MS"],
            "itineraries": [{
                "segments": [{
                    "carrierCode": "MS",
                    "number": "777",
                    "departure": {"iataCode": "HBE", "at": "2026-08-01T08:00:00"},
                    "arrival": {"iataCode": "CAI", "at": "2026-08-01T09:00:00"},
                }]
            }],
            "price": {"total": "150.00", "currency": "USD", "base": "130.00"},
            "travelerPricings": [
                {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
            ],
        }
    ]


@pytest.fixture
def mock_priced_offer_data() -> dict:
    """Mock priced offer response."""
    return {
        "price": {"total": "150.00", "currency": "USD", "base": "130.00"},
        "itineraries": [{
            "segments": [{
                "carrierCode": "MS",
                "number": "777",
                "departure": {"iataCode": "HBE", "at": "2026-08-01T08:00:00"},
                "arrival": {"iataCode": "CAI", "at": "2026-08-01T09:00:00"},
            }]
        }],
        "travelerPricings": [
            {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
        ],
    }


@pytest.fixture
def mock_order_data() -> dict:
    """Mock Amadeus flight order response."""
    return {
        "id": "AMADEUS_ORDER_001",
        "itineraries": [{
            "segments": [{
                "carrierCode": "MS",
                "number": "777",
                "departure": {"iataCode": "HBE", "at": "2026-08-01T08:00:00"},
                "arrival": {"iataCode": "CAI", "at": "2026-08-01T09:00:00"},
            }]
        }],
        "price": {"total": "150.00", "currency": "USD"},
        "travelerPricings": [
            {"fareDetailsBySegment": [{"cabin": "ECONOMY"}]}
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers: set up dependency override + TestClient per test
# ═══════════════════════════════════════════════════════════════════════════════

def _make_client(db_session, user_override=None):
    """Create a TestClient with auth + db overrides."""
    overrides = {}
    if user_override is not None:
        overrides[get_current_user] = user_override
    else:
        overrides[get_current_user] = _override_get_current_user
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Public Endpoints (no auth required)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSearchCitiesEndpoint:
    """GET /api/v1/flights/cities — City autocomplete."""

    async def test_search_cities_returns_autocomplete_results(
        self, db_session, mock_amadeus, mock_city_data,
    ):
        """Given a city keyword, return matching airports/cities with IATA."""
        mock_amadeus.search_cities.return_value = mock_city_data
        client = _make_client(db_session)

        response = client.get("/api/v1/flights/cities?q=alex&max=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["iata_code"] == "HBE"
        assert data[0]["city_name"] == "ALEXANDRIA"
        assert data[0]["airport_name"] == "BORG EL ARAB"
        assert data[0]["country_name"] == "EGYPT"
        assert data[0]["sub_type"] == "AIRPORT"

    async def test_search_cities_empty_results(
        self, db_session, mock_amadeus,
    ):
        """When no matches, return empty list."""
        mock_amadeus.search_cities.return_value = []
        client = _make_client(db_session)

        response = client.get("/api/v1/flights/cities?q=zzzzz&max=5")

        assert response.status_code == 200
        assert response.json() == []

    async def test_search_cities_requires_query(
        self, db_session,
    ):
        """Missing query parameter should return 422."""
        client = _make_client(db_session)
        response = client.get("/api/v1/flights/cities")
        assert response.status_code == 422

    async def test_search_cities_filters_no_iata(
        self, db_session, mock_amadeus,
    ):
        """Results without iataCode are filtered out."""
        mock_amadeus.search_cities.return_value = [
            {"name": "No IATA City", "subType": "CITY",
             "address": {"cityName": "NOWHERE", "countryName": "LAND"}},
            {"iataCode": "ABC", "name": "Real Airport", "subType": "AIRPORT",
             "address": {"cityName": "ABC", "countryName": "XYZ"}},
        ]
        client = _make_client(db_session)

        response = client.get("/api/v1/flights/cities?q=test&max=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["iata_code"] == "ABC"

    async def test_search_cities_amadeus_error_returns_400(
        self, db_session, mock_amadeus,
    ):
        """When Amadeus fails, endpoint returns 400."""
        mock_amadeus.search_cities.side_effect = ValueError("Amadeus API error")
        client = _make_client(db_session)

        response = client.get("/api/v1/flights/cities?q=cairo&max=5")

        assert response.status_code == 400
        assert "Amadeus" in response.json()["detail"]


@pytest.mark.asyncio
class TestSearchFlightsEndpoint:
    """POST /api/v1/flights/search — Flight offers search (public)."""

    async def test_search_flights_returns_offers(
        self, db_session, mock_amadeus, mock_offer_data,
    ):
        """Given origin/destination/date, return parsed flight offers."""
        mock_amadeus.search_flights.return_value = mock_offer_data
        mock_amadeus.search_cities.side_effect = ValueError(
            "No city found"  # Force direct IATA path
        )
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/search",
            json={
                "origin": "HBE",
                "destination": "CAI",
                "departure_date": "2026-08-01",
                "adults": 1,
                "max_results": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["airline_code"] == "MS"
        assert data[0]["flight_number"] == "MS777"
        assert data[0]["origin_iata"] == "HBE"
        assert data[0]["destination_iata"] == "CAI"
        assert data[0]["total_price"] == 150.00
        assert data[0]["currency"] == "USD"
        assert data[0]["cabin_class"] == "ECONOMY"
        assert "raw_offer" in data[0]

    async def test_search_flights_with_city_names(
        self, db_session, mock_amadeus, mock_offer_data, mock_city_data,
    ):
        """City names in origin/destination are auto-resolved to IATA."""
        def mock_search_cities(keyword, max_results=5):
            if keyword.lower() == "alexandria":
                return mock_city_data
            if keyword.lower() == "cairo":
                return [{
                    "iataCode": "CAI",
                    "name": "CAIRO INTL",
                    "subType": "AIRPORT",
                    "address": {"cityName": "CAIRO", "countryName": "EGYPT"},
                }]
            return []
        mock_amadeus.search_cities.side_effect = mock_search_cities
        mock_amadeus.search_flights.return_value = mock_offer_data
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/search",
            json={
                "origin": "alexandria",
                "destination": "cairo",
                "departure_date": "2026-08-01",
                "adults": 1,
                "max_results": 5,
            },
        )

        assert response.status_code == 200
        # Verify Amadeus was called with resolved IATA codes
        mock_amadeus.search_flights.assert_called_with(
            origin="HBE", destination="CAI",
            departure_date="2026-08-01", adults=1, max_results=5,
        )
        data = response.json()
        assert len(data) == 1

    async def test_search_flights_empty_results(
        self, db_session, mock_amadeus,
    ):
        """When no flights found, return empty list."""
        mock_amadeus.search_flights.return_value = []
        mock_amadeus.search_cities.side_effect = ValueError("No city found")
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/search",
            json={"origin": "HBE", "destination": "XXX",
                  "departure_date": "2026-08-01"},
        )

        assert response.status_code == 200
        assert response.json() == []

    async def test_search_flights_invalid_date(
        self, db_session,
    ):
        """Invalid date format returns 422."""
        client = _make_client(db_session)
        response = client.post(
            "/api/v1/flights/search",
            json={"origin": "HBE", "destination": "CAI",
                  "departure_date": "not-a-date"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestSmartSearchFlightsEndpoint:
    """POST /api/v1/flights/smart-search — City name search (public)."""

    async def test_smart_search_returns_origin_destination_and_offers(
        self, db_session, mock_amadeus, mock_offer_data, mock_city_data,
    ):
        """Given city names, returns resolved cities + flight offers."""
        def mock_search_cities(keyword, max_results=5):
            if keyword.lower() == "cairo":
                return [{
                    "iataCode": "CAI",
                    "name": "CAIRO INTL",
                    "subType": "AIRPORT",
                    "address": {"cityName": "CAIRO", "countryName": "EGYPT"},
                }]
            if keyword.lower() == "london":
                return [{
                    "iataCode": "LHR",
                    "name": "HEATHROW",
                    "subType": "AIRPORT",
                    "address": {"cityName": "LONDON", "countryName": "GB"},
                }]
            return mock_city_data
        mock_amadeus.search_cities.side_effect = mock_search_cities
        mock_amadeus.search_flights.return_value = mock_offer_data
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/smart-search",
            json={
                "origin_city": "cairo",
                "destination_city": "london",
                "departure_date": "2026-08-01",
                "adults": 1,
                "max_results": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["origin"]["iata_code"] == "CAI"
        assert data["origin"]["city_name"] == "CAIRO"
        assert data["destination"]["iata_code"] == "LHR"
        assert data["destination"]["city_name"] == "LONDON"
        assert len(data["offers"]) == 1
        assert data["offers"][0]["airline_code"] == "MS"

    async def test_smart_search_city_not_found(
        self, db_session, mock_amadeus,
    ):
        """When a city name can't be resolved, return 400."""
        mock_amadeus.search_cities.side_effect = ValueError(
            "Could not resolve city name"
        )
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/smart-search",
            json={
                "origin_city": "atlantis",
                "destination_city": "cairo",
                "departure_date": "2026-08-01",
            },
        )

        assert response.status_code == 400
        assert "Could not resolve" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Auth-Required Endpoints — Trip Context
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTripFlightContextEndpoint:
    """GET /api/v1/flights/trip/{trip_id}/context — Pre-filled search context."""

    async def test_get_trip_context_returns_all_fields(
        self, db_session, seeded_db, mock_amadeus,
    ):
        """Given a valid trip, return home_city + destination + resolved IATA."""
        def mock_search_cities(keyword, max_results=5):
            if keyword.lower() == HOME_CITY.lower():
                return [{
                    "iataCode": "HBE", "name": "BORG EL ARAB",
                    "subType": "AIRPORT",
                    "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
                }]
            if keyword.lower() == DESTINATION.lower():
                return [{
                    "iataCode": "CAI", "name": "CAIRO INTL",
                    "subType": "AIRPORT",
                    "address": {"cityName": "CAIRO", "countryName": "EGYPT"},
                }]
            return []
        mock_amadeus.search_cities.side_effect = mock_search_cities
        client = _make_client(db_session)

        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")

        assert response.status_code == 200
        data = response.json()
        assert data["trip_id"] == TRIP_ID
        assert data["home_city"] == HOME_CITY
        assert data["home_city_iata"] == "HBE"
        assert data["destination_city"] == DESTINATION
        assert data["destination_iata"] == "CAI"
        assert data["suggested_departure_date"] == "2026-08-01"
        assert data["suggested_return_date"] == "2026-08-10"
        assert data["suggested_adults"] == 2

    async def test_get_trip_context_no_home_city(
        self, db_session, mock_amadeus,
    ):
        """User with no home_city → home fields are None."""
        user = User(
            user_id=TEST_USER_ID,
            email="no_home@tourmate.com",
            full_name="No Home User",
        )
        db_session.add(user)
        trip = Trip(
            trip_id="trip_no_home", user_id=TEST_USER_ID,
            destination="Paris",
        )
        db_session.add(trip)
        await db_session.commit()

        mock_amadeus.search_cities.return_value = [{
            "iataCode": "CDG", "name": "CHARLES DE GAULLE",
            "subType": "AIRPORT",
            "address": {"cityName": "PARIS", "countryName": "FRANCE"},
        }]
        client = _make_client(db_session)

        response = client.get("/api/v1/flights/trip/trip_no_home/context")

        assert response.status_code == 200
        data = response.json()
        assert data["home_city"] is None
        assert data["home_city_iata"] is None
        assert data["destination_city"] == "Paris"
        assert data["destination_iata"] == "CDG"

    async def test_get_trip_context_trip_not_found(
        self, db_session, seeded_db,
    ):
        """Non-existent trip_id returns 404."""
        client = _make_client(db_session)
        response = client.get(
            f"/api/v1/flights/trip/{NONEXISTENT_ID}/context"
        )
        assert response.status_code == 404

    async def test_get_trip_context_wrong_user(
        self, db_session, seeded_db,
    ):
        """Trip owned by another user returns 404."""
        client = _make_client(db_session, _override_get_other_user)
        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")
        assert response.status_code == 404

    async def test_get_trip_context_unauthenticated(
        self, db_session, seeded_db,
    ):
        """No auth header returns 401/403/422."""
        # Clear auth override to test unauthenticated access
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")
        assert response.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Auth-Required Endpoints — Save / Get Offer
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSaveOfferEndpoint:
    """POST /api/v1/flights/offer — Save a selected flight offer."""

    async def test_save_offer_returns_saved_response(
        self, db_session, seeded_db, raw_offer,
    ):
        """Saving an offer returns SavedFlightOfferResponse with parsed fields."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/offer",
            json={"trip_id": TRIP_ID, "offer_index": 0, "raw_offer": raw_offer},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["offer_id"].startswith("OFR-")
        assert data["trip_id"] == TRIP_ID
        assert data["offer_index"] == 0
        assert data["origin_iata"] == "HBE"
        assert data["destination_iata"] == "CAI"
        assert data["airline_code"] == "MS"
        assert data["flight_number"] == "MS777"
        assert data["total_price"] == 150.00
        assert data["currency"] == "USD"

    async def test_save_offer_unauthenticated(
        self, db_session, seeded_db, raw_offer,
    ):
        """No auth → 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/flights/offer",
            json={"trip_id": TRIP_ID, "offer_index": 0, "raw_offer": raw_offer},
        )
        assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
class TestGetSavedOfferEndpoint:
    """GET /api/v1/flights/offer/{offer_id} — Retrieve a saved offer."""

    async def test_get_saved_offer_success(
        self, db_session, seeded_db, raw_offer,
    ):
        """After saving an offer, it can be retrieved by ID."""
        client = _make_client(db_session)

        # First save the offer
        save_resp = client.post(
            "/api/v1/flights/offer",
            json={"trip_id": TRIP_ID, "offer_index": 0, "raw_offer": raw_offer},
        )
        offer_id = save_resp.json()["offer_id"]

        # Then retrieve it
        response = client.get(f"/api/v1/flights/offer/{offer_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["offer_id"] == offer_id
        assert data["trip_id"] == TRIP_ID
        assert data["origin_iata"] == "HBE"
        assert data["total_price"] == 150.00

    async def test_get_saved_offer_not_found(
        self, db_session,
    ):
        """Non-existent offer_id returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/flights/offer/OFR-NONEXIST")
        assert response.status_code == 404

    async def test_get_saved_offer_wrong_user(
        self, db_session, seeded_db, raw_offer,
    ):
        """Offer saved by one user can't be retrieved by another."""
        client = _make_client(db_session)
        save_resp = client.post(
            "/api/v1/flights/offer",
            json={"trip_id": TRIP_ID, "offer_index": 0, "raw_offer": raw_offer},
        )
        offer_id = save_resp.json()["offer_id"]

        other_client = _make_client(db_session, _override_get_other_user)
        response = other_client.get(f"/api/v1/flights/offer/{offer_id}")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Auth-Required Endpoints — Book / Get / List / Cancel
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestBookFlightEndpoint:
    """POST /api/v1/flights/book — Book a flight."""

    async def test_book_flight_creates_confirmed_booking(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Given traveler details + raw offer, create a confirmed booking."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID,
                "raw_offer": raw_offer,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"].startswith("FL-")
        assert data["trip_id"] == TRIP_ID
        assert data["user_id"] == TEST_USER_ID
        assert data["status"] == "confirmed"
        assert data["total_cost"] == 150.00
        assert data["currency"] == "USD"
        assert data["origin_iata"] == "HBE"
        assert data["destination_iata"] == "CAI"
        assert data["airline_name"] is not None
        assert data["flight_number"] == "MS777"
        assert data["cabin_class"] == "ECONOMY"
        assert data["confirmation_number"] is not None
        assert data["amadeus_order_id"] == "AMADEUS_ORDER_001"

    async def test_book_flight_pricing_fallback(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """When pricing fails, fall back to direct booking from raw offer."""
        mock_amadeus.price_flight.side_effect = ValueError("Pricing failed")
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID,
                "raw_offer": raw_offer,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        # Verify fallback: book_flight was called once after pricing failed
        assert mock_amadeus.book_flight.call_count == 1

    async def test_book_flight_invalid_gender(
        self, db_session, seeded_db, raw_offer,
    ):
        """Invalid gender returns 422."""
        client = _make_client(db_session)
        response = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID,
                "raw_offer": raw_offer,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "INVALID",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )
        assert response.status_code == 422

    async def test_book_flight_amadeus_error(
        self, db_session, seeded_db, raw_offer, mock_amadeus,
    ):
        """When both pricing AND booking fail, return 400."""
        # The service catches ValueError from price_flight and falls back
        # to direct booking. So we need BOTH to fail for the error to propagate.
        mock_amadeus.price_flight.side_effect = ValueError(
            "Amadeus API error: Could not price"
        )
        mock_amadeus.book_flight.side_effect = ValueError(
            "Amadeus API error: Could not book"
        )
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID,
                "raw_offer": raw_offer,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )

        assert response.status_code == 400
        assert "Amadeus" in response.json()["detail"]

    async def test_book_flight_unauthenticated(
        self, db_session, seeded_db, raw_offer,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID,
                "raw_offer": raw_offer,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )
        assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
class TestBookFromOfferEndpoint:
    """POST /api/v1/flights/offer/{offer_id}/book — Book from saved offer."""

    async def test_book_from_offer_creates_confirmed_booking(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Book a flight using a previously saved offer ID."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        # First save the offer
        save_resp = client.post(
            "/api/v1/flights/offer",
            json={"trip_id": TRIP_ID, "offer_index": 0, "raw_offer": raw_offer},
        )
        offer_id = save_resp.json()["offer_id"]

        # Then book from it (no raw_offer in request)
        response = client.post(
            f"/api/v1/flights/offer/{offer_id}/book",
            json={
                "trip_id": TRIP_ID,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"].startswith("FL-")
        assert data["status"] == "confirmed"
        assert data["origin_iata"] == "HBE"
        assert data["destination_iata"] == "CAI"
        assert data["total_cost"] == 150.00

    async def test_book_from_offer_not_found(
        self, db_session,
    ):
        """Non-existent offer_id returns 400 (ValueError from service)."""
        client = _make_client(db_session)
        response = client.post(
            "/api/v1/flights/offer/OFR-NONEXIST/book",
            json={
                "trip_id": "trip_x",
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com",
                "traveler_phone": "+201234567890",
            },
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestGetFlightBookingEndpoint:
    """GET /api/v1/flights/{booking_id} — Get booking details."""

    async def test_get_flight_booking_returns_details(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """After booking, retrieve full booking details."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        book_resp = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID, "raw_offer": raw_offer,
                "traveler_first_name": "A", "traveler_last_name": "B",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com", "traveler_phone": "+201234567890",
            },
        )
        booking_id = book_resp.json()["booking_id"]

        response = client.get(f"/api/v1/flights/{booking_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["booking_id"] == booking_id
        assert data["trip_id"] == TRIP_ID
        assert data["user_id"] == TEST_USER_ID
        assert data["status"] == "confirmed"
        assert data["origin_iata"] == "HBE"
        assert data["destination_iata"] == "CAI"

    async def test_get_flight_booking_not_found(
        self, db_session,
    ):
        """Non-existent booking_id returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/flights/FL-NONEXIST")
        assert response.status_code == 404

    async def test_get_flight_booking_wrong_user(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Booking owned by another user returns 404."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        book_resp = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID, "raw_offer": raw_offer,
                "traveler_first_name": "A", "traveler_last_name": "B",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com", "traveler_phone": "+201234567890",
            },
        )
        booking_id = book_resp.json()["booking_id"]

        other_client = _make_client(db_session, _override_get_other_user)
        response = other_client.get(f"/api/v1/flights/{booking_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListTripFlightBookingsEndpoint:
    """GET /api/v1/flights/trip/{trip_id} — List trip flight bookings."""

    async def test_list_trip_flight_bookings(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """List all flight bookings for a trip."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        # Create 2 bookings
        for i in range(2):
            client.post(
                "/api/v1/flights/book",
                json={
                    "trip_id": TRIP_ID, "raw_offer": raw_offer,
                    "traveler_first_name": f"A{i}", "traveler_last_name": "B",
                    "traveler_date_of_birth": "1995-06-15",
                    "traveler_gender": "MALE",
                    "traveler_email": f"a{i}@b.com",
                    "traveler_phone": "+201234567890",
                },
            )

        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        assert all(b["trip_id"] == TRIP_ID for b in data)
        assert all(b["status"] == "confirmed" for b in data)

    async def test_list_trip_flight_bookings_empty(
        self, db_session, seeded_db,
    ):
        """Trip with no bookings returns empty list."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
class TestCancelFlightBookingEndpoint:
    """POST /api/v1/flights/{booking_id}/cancel — Cancel a flight booking."""

    async def test_cancel_flight_booking(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Cancel a confirmed booking → status becomes cancelled."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        book_resp = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID, "raw_offer": raw_offer,
                "traveler_first_name": "A", "traveler_last_name": "B",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com", "traveler_phone": "+201234567890",
            },
        )
        booking_id = book_resp.json()["booking_id"]

        cancel_resp = client.post(f"/api/v1/flights/{booking_id}/cancel")

        assert cancel_resp.status_code == 200
        data = cancel_resp.json()
        assert data["status"] == "cancelled"
        assert data["booking_id"] == booking_id

    async def test_cancel_flight_booking_already_cancelled(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Cancelling an already cancelled booking returns 400."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        book_resp = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID, "raw_offer": raw_offer,
                "traveler_first_name": "A", "traveler_last_name": "B",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com", "traveler_phone": "+201234567890",
            },
        )
        booking_id = book_resp.json()["booking_id"]

        # Cancel once
        client.post(f"/api/v1/flights/{booking_id}/cancel")
        # Cancel again
        cancel_resp = client.post(f"/api/v1/flights/{booking_id}/cancel")

        assert cancel_resp.status_code == 400
        assert "already cancelled" in cancel_resp.json()["detail"].lower()

    async def test_cancel_flight_booking_not_found(
        self, db_session,
    ):
        """Non-existent booking returns 400."""
        client = _make_client(db_session)
        response = client.post("/api/v1/flights/FL-NONEXIST/cancel")
        assert response.status_code == 400

    async def test_cancel_flight_booking_wrong_user(
        self, db_session, seeded_db, raw_offer,
        mock_amadeus, mock_priced_offer_data, mock_order_data,
    ):
        """Booking owned by another user returns 400."""
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data
        client = _make_client(db_session)

        book_resp = client.post(
            "/api/v1/flights/book",
            json={
                "trip_id": TRIP_ID, "raw_offer": raw_offer,
                "traveler_first_name": "A", "traveler_last_name": "B",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "a@b.com", "traveler_phone": "+201234567890",
            },
        )
        booking_id = book_resp.json()["booking_id"]

        other_client = _make_client(db_session, _override_get_other_user)
        response = other_client.post(f"/api/v1/flights/{booking_id}/cancel")
        assert response.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Cross-Feature: Full Booking Lifecycle (search → save → book → get → cancel)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFullFlightLifecycle:
    """End-to-end flow: search → save → book → get → cancel."""

    async def test_full_lifecycle(
        self, db_session, seeded_db,
        mock_amadeus, mock_offer_data,
        mock_priced_offer_data, mock_order_data,
    ):
        """Complete happy path for the flight booking feature."""
        client = _make_client(db_session)

        # ── 1. Search flights ──────────────────────────────────────────
        mock_amadeus.search_flights.return_value = mock_offer_data
        mock_amadeus.search_cities.side_effect = ValueError("Direct IATA")

        search_resp = client.post(
            "/api/v1/flights/search",
            json={
                "origin": "HBE", "destination": "CAI",
                "departure_date": "2026-08-01", "adults": 1, "max_results": 5,
            },
        )
        assert search_resp.status_code == 200
        offers = search_resp.json()
        assert len(offers) == 1

        # ── 2. Save offer ──────────────────────────────────────────────
        save_resp = client.post(
            "/api/v1/flights/offer",
            json={
                "trip_id": TRIP_ID,
                "offer_index": 0,
                "raw_offer": offers[0]["raw_offer"],
            },
        )
        assert save_resp.status_code == 200
        offer_id = save_resp.json()["offer_id"]

        # ── 3. Get saved offer ─────────────────────────────────────────
        get_offer_resp = client.get(f"/api/v1/flights/offer/{offer_id}")
        assert get_offer_resp.status_code == 200
        assert get_offer_resp.json()["offer_id"] == offer_id

        # ── 4. Book flight ─────────────────────────────────────────────
        mock_amadeus.price_flight.return_value = mock_priced_offer_data
        mock_amadeus.book_flight.return_value = mock_order_data

        book_resp = client.post(
            f"/api/v1/flights/offer/{offer_id}/book",
            json={
                "trip_id": TRIP_ID,
                "traveler_first_name": "Ahmed",
                "traveler_last_name": "Hassan",
                "traveler_date_of_birth": "1995-06-15",
                "traveler_gender": "MALE",
                "traveler_email": "ahmed@example.com",
                "traveler_phone": "+201234567890",
            },
        )
        assert book_resp.status_code == 200
        booking_data = book_resp.json()
        booking_id = booking_data["booking_id"]
        assert booking_data["status"] == "confirmed"
        assert booking_data["origin_iata"] == "HBE"
        assert booking_data["total_cost"] == 150.00

        # ── 5. Get booking details ─────────────────────────────────────
        get_resp = client.get(f"/api/v1/flights/{booking_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "confirmed"

        # ── 6. Cancel booking ──────────────────────────────────────────
        cancel_resp = client.post(f"/api/v1/flights/{booking_id}/cancel")
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

        # ── 7. Verify cancelled in get ─────────────────────────────────
        final_resp = client.get(f"/api/v1/flights/{booking_id}")
        assert final_resp.status_code == 200
        assert final_resp.json()["status"] == "cancelled"
