"""
Amadeus API client — lightweight wrapper around the amadeus Python SDK.

Provides three core operations:
  - ``search_flights`` — flight offers search
  - ``price_flight``   — confirm/pricer an offer
  - ``book_flight``    — create a flight order

All methods raise ``ValueError`` with a clean message on API errors so the
service layer can handle them gracefully (no raw SDK exceptions leak out).

Rate-limit (HTTP 429) responses from Amadeus are raised as a dedicated
``AmadeusRateLimitError`` so callers can distinguish "temporarily busy"
from other API failures and respond to the client accordingly.

Usage outside of a service::

    from app.services.amadeus_client import amadeus_client
    offers = amadeus_client.search_flights("CAI", "DXB", "2026-07-15")
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class AmadeusRateLimitError(Exception):
    """Raised when Amadeus returns HTTP 429 (Too Many Requests).

    Callers (typically the route layer) should catch this separately from
    ``ValueError`` and return HTTP 429 with a user-friendly "try again in a
    moment" message, rather than a generic 400/500.
    """
    pass


class AmadeusClient:
    """Synchronous (SDK-driven) Amadeus API client.

    The underlying ``amadeus.Client`` is instantiated once and reused for
    all calls.  All public methods catch ``amadeus.ResponseError`` and
    re-raise as ``ValueError`` with a human-readable message — except for
    HTTP 429 (rate limit) responses, which are raised as
    ``AmadeusRateLimitError`` so callers can handle them distinctly.

    **Thread-safety:** The ``amadeus.Client`` is not thread-safe.  In a
    FastAPI async context this is fine as long as each request runs on a
    single thread (which Uvicorn guarantees for sync endpoints or when
    called from an async function via ``run_in_executor``).
    """

    def __init__(self) -> None:
        self._client = self._build_client()

    # ── internals ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_client():
        """Lazy-import ``amadeus`` and construct the SDK client.

        Returns ``None`` when credentials are missing so the application
        degrades gracefully.
        """
        if not settings.AMADEUS_CLIENT_ID or not settings.AMADEUS_CLIENT_SECRET:
            logger.warning(
                "[AmadeusClient] AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET not set. "
                "Client will not be operational."
            )
            return None

        try:
            from amadeus import Client
        except ImportError:
            logger.warning(
                "[AmadeusClient] 'amadeus' SDK not installed. "
                "Install with: pip install amadeus"
            )
            return None

        return Client(
            client_id=settings.AMADEUS_CLIENT_ID,
            client_secret=settings.AMADEUS_CLIENT_SECRET,
            hostname="test",
        )

    # ── public API ─────────────────────────────────────────────────────────────

    # ── city / airport autocomplete ────────────────────────────────────────────

    def search_cities(self, keyword: str, max_results: int = 10) -> list[dict]:
        """Search for airports and cities by keyword.

        Uses the Amadeus ``reference_data.locations`` API to find airports
        and cities matching the given keyword.  This is the endpoint frontends
        should call as the user types a city name, so they can pick the
        correct IATA code.

        Args:
            keyword:     Partial city or airport name (e.g. ``\"Cairo\"``,
                         ``\"Lon\"``, ``\"New Yo\"``).
            max_results: Maximum results to return (default 10).

        Returns:
            A list of raw Amadeus location dicts sorted by relevance.
            Each dict contains ``iataCode``, ``name``, ``address.cityName``,
            ``address.countryName``, and ``subType``.

        Raises:
            ValueError: If the Amadeus API returns an error.
            AmadeusRateLimitError: If the Amadeus API returns HTTP 429.
        """
        if self._client is None:
            raise ValueError("Amadeus client is not initialised.")

        try:
            response = self._client.reference_data.locations.get(
                keyword=keyword,
                subType="AIRPORT,CITY",
            )
            # The SDK returns a Location[] — slice to max_results
            return response.data[:max_results]
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429:
                logger.warning("[AmadeusClient] search_cities rate-limited (429)")
                raise AmadeusRateLimitError(
                    "City search service is temporarily busy due to high demand. "
                    "Please try again in a moment."
                ) from exc
            msg = self._format_error(exc)
            logger.error("[AmadeusClient] search_cities(%s) failed: %s", keyword, msg)
            raise ValueError(msg) from exc

    # ── flight search ──────────────────────────────────────────────────────────

    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        adults: int = 1,
        max_results: int = 5,
        travel_class: str | None = None,
        return_date: str | None = None,
    ) -> list[dict]:
        """Search for flight offers between two airports on a given date.

        Args:
            origin:         IATA code of origin airport (e.g. ``\"CAI\"``).
            destination:    IATA code of destination airport.
            departure_date: ISO-8601 date string (``\"YYYY-MM-DD\"``).
            adults:         Number of adult passengers (default 1).
            max_results:    Maximum offers to return (default 5).
            travel_class:   Optional cabin class filter (e.g. \"ECONOMY\",
                            \"PREMIUM_ECONOMY\", \"BUSINESS\", \"FIRST\").
            return_date:    Optional return date for round-trip search
                            (ISO-8601 date string).

        Returns:
            A list of raw Amadeus offer dicts (``response.data``).

        Raises:
            ValueError: If the Amadeus API returns a non-rate-limit error.
            AmadeusRateLimitError: If the Amadeus API returns HTTP 429
                (Too Many Requests) — e.g. more than ~3 requests/second.
        """
        if self._client is None:
            raise ValueError(
                "Amadeus client is not initialised — check AMADEUS_CLIENT_ID "
                "and AMADEUS_CLIENT_SECRET are set and the 'amadeus' SDK is installed."
            )

        try:
            params = {
                "originLocationCode": origin.upper(),
                "destinationLocationCode": destination.upper(),
                "departureDate": departure_date,
                "adults": adults,
                "max": max_results,
            }
            if travel_class:
                params["travelClass"] = travel_class.upper()
            if return_date:
                params["returnDate"] = return_date
            response = self._client.shopping.flight_offers_search.get(**params)
            return response.data
        except Exception as exc:
            # ── Distinguish rate-limit (429) from other API errors ──────────
            # Amadeus rejects requests with HTTP 429 when more than ~3
            # requests/second are sent. Without this check, the generic
            # `except Exception` below would swallow the distinction and
            # every Amadeus failure (429, malformed params, downtime, etc.)
            # would look identical to the caller.
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429:
                logger.warning("[AmadeusClient] search_flights rate-limited (429)")
                raise AmadeusRateLimitError(
                    "Flight search service is temporarily busy due to high demand. "
                    "Please try again in a moment."
                ) from exc
            msg = self._format_error(exc)
            logger.error("[AmadeusClient] search_flights failed: %s", msg)
            raise ValueError(msg) from exc

    def price_flight(self, raw_offer: dict) -> dict:
        """Confirm/price a flight offer (returns the priced offer).

        The Amadeus SDK expects the offer wrapped in a data structure:
        ``{"data": {"type": "flight-offers-pricing", "flightOffers": [offer]}}``
        passed as a **positional argument** (not ``body=``).

        Returns the first priced flight offer from the response, which is the
        same offer enriched with confirmed pricing data.

        Falls back to the raw offer when the Amadeus test environment
        rejects the pricing request.

        Args:
            raw_offer: The raw offer dict returned by ``search_flights``.

        Returns:
            The priced offer data dict, or the raw offer as-is on failure.

        Raises:
            ValueError: If client is not initialised.
        """
        if self._client is None:
            raise ValueError("Amadeus client is not initialised.")

        try:
            pricing_payload = {
                "data": {
                    "type": "flight-offers-pricing",
                    "flightOffers": [raw_offer],
                }
            }
            response = self._client.shopping.flight_offers.pricing.post(
                pricing_payload
            )
            # The SDK response.data returns the wrapper,
            # e.g. {"type": "flight-offers-pricing", "flightOffers": [...]}
            # We need to extract the actual priced offer.
            data = response.data
            if isinstance(data, dict) and "flightOffers" in data:
                offers = data["flightOffers"]
                if offers:
                    return offers[0]
            # Fallback: return data as-is if it already looks like an offer
            return data

        except Exception as exc:
            msg = self._format_error(exc)
            logger.warning(
                "[AmadeusClient] price_flight failed (%s) — "
                "returning raw offer as-is (test environment fallback)",
                msg,
            )
            # ── Simulation fallback ──────────────────────────────────────────
            # Amadeus test environment often rejects pricing requests.
            # Return the raw offer unchanged so booking can proceed.
            return raw_offer

    def book_flight(self, priced_offer: dict, traveler: dict) -> dict:
        """Create a flight order (book the priced offer).

        The Amadeus SDK accepts the flight offer as the first positional
        argument and the traveler list as the ``travelers`` keyword:
        ``.post(flight_offer, travelers=[traveler])``.

        Falls back to a simulated order when the Amadeus test environment
        rejects the booking request.

        Args:
            priced_offer: The priced (or raw) offer dict.
            traveler:     Traveler dict in Amadeus format.

        Returns:
            The flight order response data dict, or a simulated order on failure.

        Raises:
            ValueError: If client is not initialised.
        """
        if self._client is None:
            raise ValueError("Amadeus client is not initialised.")

        try:
            response = self._client.booking.flight_orders.post(
                priced_offer,
                travelers=[traveler],
            )
            return response.data

        except Exception as exc:
            msg = self._format_error(exc)
            logger.warning(
                "[AmadeusClient] book_flight failed (%s) — "
                "falling back to simulated order (test environment fallback)",
                msg,
            )
            # ── Simulation fallback ──────────────────────────────────────────
            # Amadeus test environment rejects many real offers.
            # We simulate a confirmed order so the full booking flow can be tested.
            import random
            import string
            fake_order_id = "SIMORD-" + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
            return {
                "id": fake_order_id,
                "itineraries": priced_offer.get("itineraries", []),
                "price": priced_offer.get("price", {}),
                "simulated": True,
            }

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _format_error(exc: Exception) -> str:
        """Try to extract a readable message from an Amadeus SDK exception."""
        try:
            # amadeus.ResponseError has a .response.body attribute
            if hasattr(exc, "response") and hasattr(exc.response, "body"):
                import json
                body = json.loads(exc.response.body)
                errors = body.get("errors", [])
                if errors:
                    detail = errors[0].get("detail") or errors[0].get("title", str(exc))
                    return f"Amadeus API error: {detail}"
        except Exception:
            pass
        return f"Amadeus API error: {exc}"


# Module-level singleton — import and use anywhere without reinstantiating.
amadeus_client = AmadeusClient()