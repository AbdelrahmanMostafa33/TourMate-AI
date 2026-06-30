"""
Expedia Rapid API client — HMAC-signed REST client for hotel search & booking.

Provides three core operations:
  - ``search_hotels``       — search for hotels by city, dates, guests
  - ``get_offer``           — get real-time pricing for a specific property
  - ``book_hotel``          — create a confirmed reservation

All methods raise ``ValueError`` with a clean message on API errors so the
service layer can handle them gracefully.

Usage outside of a service::

    from app.external.expedia_client import expedia_client
    offers = await expedia_client.search_hotels("Cairo", "2026-08-01", "2026-08-05", 2)
"""

from __future__ import annotations

import hashlib
import hmac
import time
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Base URL for the Expedia Rapid API
_RAPID_API_BASE = "https://api.expediagroup.com"

# Default timeout for API calls
_REQUEST_TIMEOUT = 15.0


class ExpediaRapidClient:
    """Async Expedia Rapid API client with SHA-256 HMAC authentication.

    The client uses API Key + API Secret from settings to sign every request.
    If credentials are missing, the client logs a warning and all methods
    raise ``ValueError`` with a clear message (graceful degradation).

    **Thread-safety:** Each public method creates its own ``httpx.AsyncClient``
    so the client is safe to use as a singleton across async requests.
    """

    def __init__(self) -> None:
        self.api_key = settings.EXPEDIA_API_KEY
        self.api_secret = settings.EXPEDIA_API_SECRET
        self._configured = bool(self.api_key and self.api_secret)

        if not self._configured:
            logger.warning(
                "[ExpediaClient] EXPEDIA_API_KEY / EXPEDIA_API_SECRET not set. "
                "Client will raise on all requests."
            )

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _build_auth_header(self) -> str:
        """Build the HMAC SHA-256 signed Authorization header.

        The Expedia Rapid API requires every request to be signed:
            Authorization: EQC-API-Key <api_key>:<hex_encoded_hmac>

        The HMAC payload is: api_key + api_secret + current_unix_timestamp
        """
        timestamp = str(int(time.time()))
        payload = self.api_key + self.api_secret + timestamp
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"EQC-API-Key {self.api_key}:{signature}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._build_auth_header(),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    def _check_configured(self) -> None:
        """Raise ``ValueError`` if the client is not configured."""
        if not self._configured:
            raise ValueError(
                "Expedia Rapid API is not configured. "
                "Set EXPEDIA_API_KEY and EXPEDIA_API_SECRET in your .env file. "
                "Get credentials at https://developers.expediagroup.com/"
            )

    @staticmethod
    def _format_error(exc: Exception, context: str = "") -> str:
        """Extract a readable error message from an API exception."""
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                body = exc.response.json()
                msg = body.get("message") or body.get("error", str(exc))
                status = exc.response.status_code
                return f"Expedia API error ({status}): {msg}"
            except Exception:
                return f"Expedia API error ({exc.response.status_code}): {exc}"
        return f"Expedia API error: {exc}"

    # ── Public API ────────────────────────────────────────────────────────────

    async def search_hotels(
        self,
        city: str,
        checkin: str,
        checkout: str,
        guests: int = 2,
        rooms: int = 1,
        max_results: int = 25,
    ) -> list[dict]:
        """Search for hotels in a city by dates and occupancy.

        Args:
            city:        City name (e.g. ``"Cairo"``, ``"Dubai"``).
            checkin:     ISO-8601 check-in date (``"2026-08-01"``).
            checkout:    ISO-8601 check-out date.
            guests:      Number of adult guests (default 2).
            rooms:       Number of rooms (default 1).
            max_results: Max properties to return (default 25).

        Returns:
            A list of property-offer dicts containing ``property_id``,
            ``name``, ``rate``, ``strikethrough_rate``, ``tax_info``,
            ``refundable``, and ``promotions``.

        Raises:
            ValueError: If the API call fails or client is unconfigured.
        """
        self._check_configured()

        url = f"{_RAPID_API_BASE}/shopping/hotel-offers"
        params = {
            "city": city,
            "checkin": checkin,
            "checkout": checkout,
            "rooms": str(rooms),
            "guests": str(guests),
            "max": str(max_results),
        }

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, params=params, headers=self._headers())
                response.raise_for_status()
                data = response.json()
                return data.get("offers", [])
            except Exception as exc:
                msg = self._format_error(exc, f"search_hotels({city})")
                logger.error("[ExpediaClient] %s", msg)
                raise ValueError(msg) from exc

    async def get_offer(
        self,
        property_id: str,
        checkin: str,
        checkout: str,
        guests: int = 2,
    ) -> dict:
        """Get real-time pricing & availability for a specific property.

        This is the endpoint to call when the user has selected a specific
        hotel from their curated list.  It returns a locked-in rate with an
        ``offer_id`` that can be used to book.

        Args:
            property_id: Expedia property ID (stored in ``booking_platforms``).
            checkin:     ISO-8601 check-in date.
            checkout:    ISO-8601 check-out date.
            guests:      Number of adult guests.

        Returns:
            A dict with keys: ``offer_id``, ``property_id``, ``name``,
            ``rate``, ``currency``, ``tax_info``, ``total``, ``refundable``.

        Raises:
            ValueError: If the API call fails, client unconfigured, or
                       property not found.
        """
        self._check_configured()

        url = f"{_RAPID_API_BASE}/shopping/hotel-offers/{property_id}"
        params = {
            "checkin": checkin,
            "checkout": checkout,
            "guests": str(guests),
        }

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.get(url, params=params, headers=self._headers())
                response.raise_for_status()
                data = response.json()

                # Extract the first available offer for this property
                offers = data.get("offers", [])
                if not offers:
                    raise ValueError(
                        f"No available offers for property {property_id} "
                        f"on {checkin}–{checkout}"
                    )

                offer = offers[0]
                return {
                    "offer_id": offer.get("id"),
                    "property_id": property_id,
                    "name": data.get("name", ""),
                    "rate": offer.get("rate"),
                    "currency": offer.get("currency", "USD"),
                    "tax_info": offer.get("tax_info", {}),
                    "total": offer.get("total", offer.get("rate")),
                    "refundable": offer.get("refundable", False),
                }
            except ValueError:
                raise
            except Exception as exc:
                msg = self._format_error(exc, f"get_offer({property_id})")
                logger.error("[ExpediaClient] %s", msg)
                raise ValueError(msg) from exc

    async def book_hotel(
        self,
        offer_id: str,
        email: str,
        payment: dict,
        phone: Optional[dict] = None,
        affiliate_reference_id: Optional[str] = None,
    ) -> dict:
        """Create a confirmed hotel reservation.

        Args:
            offer_id:               The ``offer_id`` from ``get_offer()``.
            email:                  Guest email address.
            payment:                Payment details dict:
                ``{ "type": "credit_card", "number": "...", "security_code": "...",
                   "expiration": {"month": "12", "year": "2026"},
                   "billing_contact": {"given_name": "...", "family_name": "...",
                                       "address": {"line1": "...", "city": "...",
                                                   "country_code": "..."}} }``
            phone:                  Optional phone dict:
                ``{"country_code": "20", "number": "1234567890"}``
            affiliate_reference_id: Your internal order reference (e.g. trip_id).

        Returns:
            A dict with keys: ``itinerary_id``, ``confirmation_number``,
            ``status``, ``property_id``, ``total``, ``currency``.

        Raises:
            ValueError: If the API call fails or client is unconfigured.
        """
        self._check_configured()

        url = f"{_RAPID_API_BASE}/bookings"

        body = {
            "offer_id": offer_id,
            "email": email,
            "payments": [payment],
        }
        if phone:
            body["phone"] = phone
        if affiliate_reference_id:
            body["affiliate_reference_id"] = affiliate_reference_id

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.post(url, json=body, headers=self._headers())
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "[ExpediaClient] Booked hotel: itinerary=%s, status=%s",
                    data.get("itinerary_id", "?"),
                    data.get("status", "?"),
                )
                return {
                    "itinerary_id": data.get("itinerary_id"),
                    "confirmation_number": data.get("confirmation_number"),
                    "status": data.get("status"),
                    "property_id": data.get("property_id"),
                    "total": data.get("total"),
                    "currency": data.get("currency", "USD"),
                    "raw_response": data,
                }
            except Exception as exc:
                msg = self._format_error(exc, "book_hotel")
                logger.error("[ExpediaClient] %s", msg)
                raise ValueError(msg) from exc

    async def cancel_booking(self, itinerary_id: str) -> dict:
        """Cancel a hotel reservation.

        Args:
            itinerary_id: The Expedia itinerary ID to cancel.

        Returns:
            A dict with keys: ``itinerary_id``, ``status``, ``refund``.

        Raises:
            ValueError: If the API call fails or client is unconfigured.
        """
        self._check_configured()

        url = f"{_RAPID_API_BASE}/bookings/{itinerary_id}"

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            try:
                response = await client.delete(url, headers=self._headers())
                response.raise_for_status()
                data = response.json()
                return {
                    "itinerary_id": itinerary_id,
                    "status": data.get("status", "cancelled"),
                    "refund": data.get("refund"),
                }
            except Exception as exc:
                msg = self._format_error(exc, f"cancel_booking({itinerary_id})")
                logger.error("[ExpediaClient] %s", msg)
                raise ValueError(msg) from exc


# Module-level singleton — import and use anywhere without reinstantiating.
expedia_client = ExpediaRapidClient()
