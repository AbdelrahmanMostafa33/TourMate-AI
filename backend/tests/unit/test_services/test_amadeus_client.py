"""Unit tests for amadeus_client.py — Amadeus API wrapper.

Covers:
  - _build_client: credentials missing, SDK missing, success
  - All public methods: search_cities, search_flights, price_flight, book_flight
  - Error handling: _format_error with various exception types
  - Client-not-initialised guards for every method

Mocking strategy:
  - The `client` fixture bypasses _build_client by using __new__ + setting _client
  - _build_client tests explicitly patch amadeus.Client (local import inside method)
  - _format_error tests use MagicMock instances (no dependency on real amadeus SDK)
"""

from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _patch_settings():
    """Ensure AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET are set for any
    _build_client tests, without depending on the real .env file."""
    with patch("app.services.amadeus_client.settings") as mock_settings:
        mock_settings.AMADEUS_CLIENT_ID = "test_id"
        mock_settings.AMADEUS_CLIENT_SECRET = "test_secret"
        yield mock_settings


@pytest.fixture
def client():
    """Return an AmadeusClient with _client set to a MagicMock.

    Uses __new__ to bypass _build_client entirely, avoiding any
    dependency on the real amadeus SDK or credentials.
    """
    from app.services.amadeus_client import AmadeusClient

    c = AmadeusClient.__new__(AmadeusClient)
    c._client = MagicMock()
    return c


@pytest.fixture
def raw_offer():
    """A minimal flight offer dict matching Amadeus SDK output."""
    return {
        "id": "1",
        "source": "GDS",
        "lastTicketingDate": "2026-07-01",
        "itineraries": [
            {
                "duration": "PT4H",
                "segments": [
                    {
                        "departure": {"iataCode": "CAI", "at": "2026-07-15T08:00:00"},
                        "arrival": {"iataCode": "DXB", "at": "2026-07-15T14:00:00"},
                        "carrierCode": "EK",
                        "number": "123",
                    }
                ],
            }
        ],
        "price": {"total": "350.00", "currency": "USD"},
        "travelerPricings": [
            {
                "travelerId": "1",
                "fareOption": "STANDARD",
                "travelerType": "ADULT",
                "price": {"total": "350.00"},
            }
        ],
    }


@pytest.fixture
def traveler():
    """A minimal traveler dict in Amadeus format."""
    return {
        "id": "1",
        "firstName": "JOHN",
        "lastName": "DOE",
        "dateOfBirth": "1990-01-15",
        "gender": "MALE",
        "contact": {
            "emailAddress": "john@example.com",
            "phone": {"deviceType": "MOBILE", "countryCallingCode": "1", "number": "555123456"},
        },
        "documents": [
            {
                "documentType": "PASSPORT",
                "birthPlace": "CAIRO",
                "issuanceLocation": "CAIRO",
                "issuanceDate": "2020-01-01",
                "number": "AB123456",
                "expiryDate": "2030-01-01",
                "issuanceCountry": "EG",
                "validityCountry": "EG",
                "nationality": "EG",
                "holder": True,
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# _build_client — constructor internals
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildClient:
    """Tests for the static _build_client method.

    Notes:
      - Must patch amadeus.Client (the import is local: ``from amadeus import Client``)
      - Must patch settings via mock (not the autouse fixture since we override it)
    """

    def test_missing_client_id_returns_none(self):
        """When AMADEUS_CLIENT_ID is empty, _build_client should return None."""
        with patch("app.services.amadeus_client.settings") as mock_settings:
            mock_settings.AMADEUS_CLIENT_ID = ""
            mock_settings.AMADEUS_CLIENT_SECRET = "test_secret"

            from app.services.amadeus_client import AmadeusClient

            result = AmadeusClient._build_client()
            assert result is None

    def test_missing_client_secret_returns_none(self):
        """When AMADEUS_CLIENT_SECRET is empty, _build_client should return None."""
        with patch("app.services.amadeus_client.settings") as mock_settings:
            mock_settings.AMADEUS_CLIENT_ID = "test_id"
            mock_settings.AMADEUS_CLIENT_SECRET = ""

            from app.services.amadeus_client import AmadeusClient

            result = AmadeusClient._build_client()
            assert result is None

    def test_missing_both_returns_none(self):
        """When both credentials are empty, _build_client should return None."""
        with patch("app.services.amadeus_client.settings") as mock_settings:
            mock_settings.AMADEUS_CLIENT_ID = ""
            mock_settings.AMADEUS_CLIENT_SECRET = ""

            from app.services.amadeus_client import AmadeusClient

            result = AmadeusClient._build_client()
            assert result is None

    def test_sdk_not_installed_returns_none(self):
        """When the 'amadeus' package is not installed, _build_client should return None.

        We patch builtins.__import__ to raise ImportError for the 'amadeus' module.
        """
        with patch("app.services.amadeus_client.settings") as mock_settings:
            mock_settings.AMADEUS_CLIENT_ID = "test_id"
            mock_settings.AMADEUS_CLIENT_SECRET = "test_secret"

            original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

            def mock_import(name, *args, **kwargs):
                if name == "amadeus":
                    raise ImportError("No module named 'amadeus'")
                return original_import(name, *args, **kwargs)

            # Only patch __import__ when the test needs it
            import builtins
            with patch.object(builtins, "__import__", side_effect=mock_import):
                from app.services.amadeus_client import AmadeusClient

                result = AmadeusClient._build_client()
                assert result is None

    def test_success_returns_client_instance(self):
        """When credentials are set and SDK is available, _build_client should return
        a Client instance constructed with the right arguments."""
        with patch("app.services.amadeus_client.settings") as mock_settings:
            mock_settings.AMADEUS_CLIENT_ID = "test_id"
            mock_settings.AMADEUS_CLIENT_SECRET = "test_secret"

            mock_instance = MagicMock()

            # Patch amadeus.Client directly since _build_client uses
            # ``from amadeus import Client`` as a local import.
            with patch("amadeus.Client") as mock_client_cls:
                mock_client_cls.return_value = mock_instance

                from app.services.amadeus_client import AmadeusClient

                result = AmadeusClient._build_client()
                assert result is mock_instance
                mock_client_cls.assert_called_once_with(
                    client_id="test_id",
                    client_secret="test_secret",
                    hostname="test",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# Client-not-initialised guards (when _client is None)
# ═══════════════════════════════════════════════════════════════════════════════


class TestClientNotInitialised:
    """All public methods should raise ValueError when _client is None."""

    @pytest.fixture
    def dead_client(self):
        """Return an AmadeusClient with _client = None."""
        from app.services.amadeus_client import AmadeusClient

        c = AmadeusClient.__new__(AmadeusClient)
        c._client = None
        return c

    def test_search_cities_raises_value_error(self, dead_client):
        with pytest.raises(ValueError, match="not initialised"):
            dead_client.search_cities("Cairo")

    def test_search_flights_raises_value_error(self, dead_client):
        with pytest.raises(ValueError, match="not initialised"):
            dead_client.search_flights("CAI", "DXB", "2026-07-15")

    def test_price_flight_raises_value_error(self, dead_client):
        with pytest.raises(ValueError, match="not initialised"):
            dead_client.price_flight({})

    def test_book_flight_raises_value_error(self, dead_client):
        with pytest.raises(ValueError, match="not initialised"):
            dead_client.book_flight({}, {})


# ═══════════════════════════════════════════════════════════════════════════════
# search_cities
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchCities:
    """Tests for search_cities — city/airport autocomplete."""

    def test_returns_results_sliced_to_max_results(self, client):
        """search_cities should return results limited to max_results."""
        mock_data = [{"iataCode": f"AIR{i}"} for i in range(20)]
        client._client.reference_data.locations.get.return_value.data = mock_data

        result = client.search_cities("Cairo", max_results=5)

        assert len(result) == 5
        assert result[0]["iataCode"] == "AIR0"
        assert result[4]["iataCode"] == "AIR4"
        client._client.reference_data.locations.get.assert_called_once_with(
            keyword="Cairo",
            subType="AIRPORT,CITY",
        )

    def test_fewer_results_than_max(self, client):
        mock_data = [{"iataCode": "LHR"}, {"iataCode": "LGW"}]
        client._client.reference_data.locations.get.return_value.data = mock_data

        result = client.search_cities("Lon", max_results=10)

        assert len(result) == 2

    def test_empty_results(self, client):
        client._client.reference_data.locations.get.return_value.data = []

        result = client.search_cities("Xyzxyz", max_results=5)

        assert result == []

    def test_api_error_raises_value_error(self, client):
        """When the Amadeus API returns an error, ValueError should be raised."""
        client._client.reference_data.locations.get.side_effect = RuntimeError("Invalid keyword")

        with pytest.raises(ValueError, match="Invalid keyword"):
            client.search_cities("!")

    def test_generic_exception_raises_value_error(self, client):
        client._client.reference_data.locations.get.side_effect = RuntimeError("Connection refused")

        with pytest.raises(ValueError, match="Connection refused"):
            client.search_cities("Cairo")


# ═══════════════════════════════════════════════════════════════════════════════
# search_flights
# ═══════════════════════════════════════════════════════════════════════════════


class TestSearchFlights:
    """Tests for search_flights — flight offer search."""

    def test_basic_search(self, client):
        """Basic one-way flight search should pass correct params."""
        mock_offers = [{"id": "offer1"}, {"id": "offer2"}]
        client._client.shopping.flight_offers_search.get.return_value.data = mock_offers

        result = client.search_flights("CAI", "DXB", "2026-07-15")

        assert result == mock_offers
        client._client.shopping.flight_offers_search.get.assert_called_once_with(
            originLocationCode="CAI",
            destinationLocationCode="DXB",
            departureDate="2026-07-15",
            adults=1,
            max=5,
        )

    def test_uppercases_iata_codes(self, client):
        """IATA codes should be uppercased automatically."""
        client._client.shopping.flight_offers_search.get.return_value.data = []

        client.search_flights("cai", "dxb", "2026-07-15")

        call_kwargs = client._client.shopping.flight_offers_search.get.call_args[1]
        assert call_kwargs["originLocationCode"] == "CAI"
        assert call_kwargs["destinationLocationCode"] == "DXB"

    def test_with_travel_class(self, client):
        client._client.shopping.flight_offers_search.get.return_value.data = []

        client.search_flights("CAI", "DXB", "2026-07-15", travel_class="BUSINESS")

        call_kwargs = client._client.shopping.flight_offers_search.get.call_args[1]
        assert call_kwargs["travelClass"] == "BUSINESS"

    def test_with_return_date(self, client):
        client._client.shopping.flight_offers_search.get.return_value.data = []

        client.search_flights("CAI", "DXB", "2026-07-15", return_date="2026-07-20")

        call_kwargs = client._client.shopping.flight_offers_search.get.call_args[1]
        assert call_kwargs["returnDate"] == "2026-07-20"

    def test_with_all_params(self, client):
        client._client.shopping.flight_offers_search.get.return_value.data = []

        client.search_flights(
            "CAI", "DXB", "2026-07-15",
            adults=2, max_results=3, travel_class="ECONOMY",
            return_date="2026-07-22",
        )

        call_kwargs = client._client.shopping.flight_offers_search.get.call_args[1]
        assert call_kwargs["adults"] == 2
        assert call_kwargs["max"] == 3
        assert call_kwargs["travelClass"] == "ECONOMY"
        assert call_kwargs["returnDate"] == "2026-07-22"

    def test_api_error_raises_value_error(self, client):
        client._client.shopping.flight_offers_search.get.side_effect = RuntimeError("Server Error")

        with pytest.raises(ValueError, match="Server Error"):
            client.search_flights("CAI", "DXB", "2026-07-15")

    def test_empty_results(self, client):
        client._client.shopping.flight_offers_search.get.return_value.data = []

        result = client.search_flights("CAI", "XXX", "2026-07-15")

        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# price_flight
# ═══════════════════════════════════════════════════════════════════════════════


class TestPriceFlight:
    """Tests for price_flight — confirm/price a flight offer."""

    def test_returns_first_priced_offer(self, client, raw_offer):
        """Should return the first priced offer from the response."""
        mock_response = MagicMock()
        mock_response.data = {
            "type": "flight-offers-pricing",
            "flightOffers": [
                {**raw_offer, "price": {"total": "355.00", "currency": "USD"}},
            ],
        }
        client._client.shopping.flight_offers.pricing.post.return_value = mock_response

        result = client.price_flight(raw_offer)

        assert result["price"]["total"] == "355.00"

    def test_returns_data_when_no_flight_offers_key(self, client, raw_offer):
        """When response lacks 'flightOffers' key, return data as-is."""
        mock_response = MagicMock()
        mock_response.data = {"id": "priced_1", "price": {"total": "360.00"}}
        client._client.shopping.flight_offers.pricing.post.return_value = mock_response

        result = client.price_flight(raw_offer)

        assert result["id"] == "priced_1"
        assert result["price"]["total"] == "360.00"

    def test_returns_data_when_flight_offers_empty(self, client, raw_offer):
        """When flightOffers is an empty list, return the wrapper dict as-is."""
        mock_response = MagicMock()
        wrapper = {"type": "flight-offers-pricing", "flightOffers": []}
        mock_response.data = wrapper
        client._client.shopping.flight_offers.pricing.post.return_value = mock_response

        result = client.price_flight(raw_offer)

        # The code returns data as-is when flightOffers is falsy (empty list)
        assert result == wrapper
        assert result["flightOffers"] == []

    def test_api_error_falls_back_to_raw_offer(self, client, raw_offer):
        """When the Amadeus API rejects pricing, the raw offer should be returned."""
        client._client.shopping.flight_offers.pricing.post.side_effect = RuntimeError("Price unavailable")

        result = client.price_flight(raw_offer)

        assert result is raw_offer
        assert result["price"]["total"] == "350.00"

    def test_generic_exception_falls_back_to_raw_offer(self, client, raw_offer):
        client._client.shopping.flight_offers.pricing.post.side_effect = RuntimeError("Timeout")

        result = client.price_flight(raw_offer)

        assert result is raw_offer

    def test_pricing_payload_structure(self, client, raw_offer):
        """Verify the pricing payload is sent in the correct nested structure."""
        mock_response = MagicMock()
        mock_response.data = {"type": "flight-offers-pricing", "flightOffers": [raw_offer]}
        client._client.shopping.flight_offers.pricing.post.return_value = mock_response

        client.price_flight(raw_offer)

        payload = client._client.shopping.flight_offers.pricing.post.call_args[0][0]
        assert payload["data"]["type"] == "flight-offers-pricing"
        assert payload["data"]["flightOffers"] == [raw_offer]


# ═══════════════════════════════════════════════════════════════════════════════
# book_flight
# ═══════════════════════════════════════════════════════════════════════════════


class TestBookFlight:
    """Tests for book_flight — create a flight order."""

    def test_returns_order_data(self, client, raw_offer, traveler):
        """Should return the flight order response data."""
        mock_response = MagicMock()
        mock_response.data = {
            "id": "ORD-12345",
            "type": "flight-order",
            "queuingOfficeId": "NCEXXXXX",
            "itineraries": raw_offer["itineraries"],
        }
        client._client.booking.flight_orders.post.return_value = mock_response

        result = client.book_flight(raw_offer, traveler)

        assert result["id"] == "ORD-12345"
        assert result["type"] == "flight-order"
        client._client.booking.flight_orders.post.assert_called_once_with(
            raw_offer,
            travelers=[traveler],
        )

    def test_api_error_falls_back_to_simulated_order(self, client, raw_offer, traveler):
        """When booking fails, a simulated order should be returned."""
        client._client.booking.flight_orders.post.side_effect = RuntimeError("Booking rejected")

        result = client.book_flight(raw_offer, traveler)

        assert result["simulated"] is True
        assert result["itineraries"] == raw_offer["itineraries"]
        assert result["price"] == raw_offer["price"]
        assert result["id"].startswith("SIMORD-")
        assert len(result["id"]) == len("SIMORD-") + 8

    def test_generic_exception_falls_back_to_simulated_order(self, client, raw_offer, traveler):
        client._client.booking.flight_orders.post.side_effect = RuntimeError("Service unavailable")

        result = client.book_flight(raw_offer, traveler)

        assert result["simulated"] is True
        assert result["id"].startswith("SIMORD-")

    def test_simulated_order_preserves_itineraries_and_price(self, client, raw_offer, traveler):
        client._client.booking.flight_orders.post.side_effect = RuntimeError("Any error")

        result = client.book_flight(raw_offer, traveler)

        assert result["itineraries"] == raw_offer["itineraries"]
        assert result["price"] == raw_offer["price"]


# ═══════════════════════════════════════════════════════════════════════════════
# _format_error — helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatError:
    """Tests for _format_error — extracting messages from Amadeus exceptions.

    These tests construct mock exceptions with the relevant attributes
    (``.response.body``) rather than importing the real ``amadeus.ResponseError``,
    which may not be available in all test environments.
    """

    def test_response_error_with_detail(self):
        """When the error has a response body with errors[].detail, use it."""
        exc = MagicMock()
        exc.response.body = '{"errors": [{"detail": "Invalid airport code", "title": "Bad Request"}]}'

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: Invalid airport code"

    def test_response_error_with_title_when_no_detail(self):
        """When the error lacks detail but has title, use the title."""
        exc = MagicMock()
        exc.response.body = '{"errors": [{"title": "Internal Server Error"}]}'

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: Internal Server Error"

    def test_response_error_with_empty_errors_list(self):
        """When errors list is empty, fall back to str(exc)."""
        exc = MagicMock()
        exc.response.body = '{"errors": []}'
        # Make str(exc) return something meaningful
        exc.__str__.return_value = "AmadeusResponseError"

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: AmadeusResponseError"

    def test_response_error_no_body(self):
        """When the exception lacks .response, use str(exc)."""
        exc = MagicMock(spec=Exception)
        # Don't add .response attribute — hasattr will be False
        del exc.response

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert "Amadeus API error" in result

    def test_generic_exception(self):
        """A non-Amadeus exception should use str(exc)."""
        exc = RuntimeError("Connection timed out")

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: Connection timed out"

    def test_exception_without_response_attribute(self):
        """An exception without a .response attribute at all."""
        exc = ValueError("Something went wrong")

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: Something went wrong"

    def test_response_error_unparsable_body(self):
        """When the response body is not valid JSON, fall back to str(exc)."""
        exc = MagicMock()
        exc.response.body = "not json"
        exc.__str__.return_value = "AmadeusResponseError"

        from app.services.amadeus_client import AmadeusClient

        result = AmadeusClient._format_error(exc)
        assert result == "Amadeus API error: AmadeusResponseError"
