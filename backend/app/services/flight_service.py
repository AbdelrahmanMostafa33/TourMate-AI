"""
Flight Service — Amadeus flight booking simulation.

Reuses the existing ``Booking`` table (``booking_type=flight``,
``provider=amadeus``) to store flight bookings.  Flight-specific data is
stored in the ``raw_response`` JSON column so no new tables are needed.

Flow:
  1. ``search_cities()``              → Amadeus API city/airport autocomplete → parsed list
  2. ``resolve_city_to_iata()``       → single city name → IATA code
  3. ``search_flights()``             → Amadeus API flight offers search → parsed offers
  4. ``smart_search()``               → resolve city names + search (all-in-one)
  5. ``get_trip_context()``           → trip data → pre-filled search suggestions
  6. ``initiate_flight_booking()``    → price offer + Stripe PaymentIntent (no DB save)
  7. ``confirm_flight_booking()``     → verify Stripe + book via Amadeus → Booking + Payment + Receipt
  8. ``cancel_flight_booking()``      → status transition to cancelled

All service methods follow the same async patterns as ``BookingService``:
never commit inside the service, always use ``selectinload``, raise
``ValueError`` for business-logic failures.
"""

from __future__ import annotations

import re
import random
import string
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.user import User
from app.schemas.flight import (
    FlightSearchRequest,
    FlightOfferItem,
    CitySearchResult,
    SmartFlightSearchRequest,
    SmartFlightSearchResponse,
    TripFlightContext,
    FlightBookInitiateRequest,
    FlightBookInitiateResponse,
    FlightBookConfirmRequest,
)
from app.models.enums import (
    BookingType,
    BookingProvider,
    BookingStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from app.models.booking import Booking, Payment, Receipt
from app.services.amadeus_client import amadeus_client

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _generate_flight_booking_id() -> str:
    """Short ID like ``FL-A3F9C2``."""
    return "FL-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _generate_confirmation_number() -> str:
    """Confirmation number like ``FLT-8X2M-9K1P``."""
    def _seg() -> str:
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"FLT-{_seg()}-{_seg()}"


# ── flight service ────────────────────────────────────────────────────────
# Flutter stores the raw_offer and priced_offer locally on the client side.
# No server-side in-memory offer storage is needed.


_IATA_RE = re.compile(r"^[A-Z]{3}$")


def _looks_like_iata_code(s: str) -> bool:
    """``True`` if the string looks like a 3-letter IATA code (e.g. ``\"CAI\"``)."""
    return bool(_IATA_RE.match(s))


def _parse_city_result(raw: dict) -> CitySearchResult:
    """Parse a single raw Amadeus location dict into a ``CitySearchResult``."""
    addr = raw.get("address", {})
    return CitySearchResult(
        iata_code=raw.get("iataCode", ""),
        city_name=addr.get("cityName", raw.get("name", "")),
        airport_name=raw.get("name") if raw.get("subType") == "AIRPORT" else None,
        country_name=addr.get("countryName", ""),
        sub_type=raw.get("subType", "CITY"),
    )


# ── service ───────────────────────────────────────────────────────────────────

class FlightService:
    """Business logic for flight booking simulation via Amadeus."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── public helpers (used by router) ───────────────────────────────────────

    def resolve_city_to_iata(self, city_name: str) -> CitySearchResult:
        """Convert a city name (or partial name) to the best-matching IATA code.

        Calls the Amadeus ``reference_data.locations`` API and returns the
        *first* result that has an IATA code.

        Args:
            city_name: City name (e.g. ``\"Cairo\"``, ``\"London\"``).

        Returns:
            A ``CitySearchResult`` with the resolved IATA code.

        Raises:
            ValueError: If no matching city/airport is found.
        """
        raw_results = amadeus_client.search_cities(city_name, max_results=5)
        for raw in raw_results:
            iata = raw.get("iataCode", "")
            if iata:
                return _parse_city_result(raw)
        raise ValueError(f"Could not resolve city name '{city_name}' to an IATA code")

    # ── search_cities ─────────────────────────────────────────────────────────

    async def search_cities(self, query: str, max_results: int = 10) -> list[CitySearchResult]:
        """Autocomplete cities / airports by keyword.

        Args:
            query:       Partial city or airport name.
            max_results: Max results to return.

        Returns:
            A list of ``CitySearchResult`` objects sorted by Amadeus relevance.

        Raises:
            ValueError: If the Amadeus API call fails.
        """
        raw_results = amadeus_client.search_cities(query, max_results=max_results)
        return [_parse_city_result(r) for r in raw_results if r.get("iataCode")]

    # ── search_flights ────────────────────────────────────────────────────────

    async def search_flights(self, data: FlightSearchRequest) -> list[FlightOfferItem]:
        """Search for flight offers and return parsed results.

        ``origin`` and ``destination`` in the request are auto-resolved:
        if they look like city names (not 3-letter IATA codes), they will
        be converted to IATA codes via the Amadeus locations API before
        the flight search.

        Args:
            data: Search parameters including origin, destination, date.

        Returns:
            A list of parsed ``FlightOfferItem`` objects.

        Raises:
            ValueError: If the Amadeus API call fails or a city name cannot
                       be resolved.
        """
        # ── Auto-resolve city names to IATA codes ──
        origin_iata = data.origin
        dest_iata = data.destination

        if not _looks_like_iata_code(origin_iata):
            resolved = self.resolve_city_to_iata(origin_iata)
            origin_iata = resolved.iata_code
            logger.info(
                "[FlightService] Resolved origin '%s' → IATA '%s'",
                data.origin, origin_iata,
            )

        if not _looks_like_iata_code(dest_iata):
            resolved = self.resolve_city_to_iata(dest_iata)
            dest_iata = resolved.iata_code
            logger.info(
                "[FlightService] Resolved destination '%s' → IATA '%s'",
                data.destination, dest_iata,
            )

        raw_offers = amadeus_client.search_flights(
            origin=origin_iata,
            destination=dest_iata,
            departure_date=data.departure_date.isoformat(),
            adults=data.adults,
            max_results=data.max_results,
        )

        if not raw_offers:
            return []

        # Amadeus airline codes → name mapping (built-in via SDK)
        airline_names: dict[str, str] = {}
        try:
            # The SDK provides a reference data API for airline codes
            response = amadeus_client._client.reference_data.airlines.get(
                airlineCodes=",".join(
                    o.get("validatingAirlineCodes", [""])[0]
                    for o in raw_offers if o.get("validatingAirlineCodes")
                )
            )
            for airline in response.data:
                airline_names[airline.get("iataCode", "")] = airline.get("businessName", "")
        except Exception:
            # Fallback: use IATA code as name if lookup fails
            pass

        items: list[FlightOfferItem] = []
        for idx, offer in enumerate(raw_offers):
            try:
                item = self._parse_offer(offer, idx, airline_names)
                items.append(item)
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                logger.warning(
                    "[FlightService] Skipping malformed offer %d: %s", idx, exc
                )
                continue

        return items

    # ── smart_search ──────────────────────────────────────────────────────────

    async def smart_search(self, data: SmartFlightSearchRequest) -> SmartFlightSearchResponse:
        """Resolve city names + search flights in one call.

        This is the recommended endpoint for frontends.  It returns the
        resolved origin/destination info alongside flight offers so the
        UI can show which airports were matched.

        Args:
            data: Search by city name (not IATA code).

        Returns:
            Resolved origin + destination + flight offers.
        """
        origin = self.resolve_city_to_iata(data.origin_city)
        destination = self.resolve_city_to_iata(data.destination_city)

        # Build a FlightSearchRequest with resolved IATA codes
        search_req = FlightSearchRequest(
            origin=origin.iata_code,
            destination=destination.iata_code,
            departure_date=data.departure_date,
            adults=data.adults,
            max_results=data.max_results,
        )
        offers = await self.search_flights(search_req)

        return SmartFlightSearchResponse(
            origin=origin,
            destination=destination,
            offers=offers,
        )

    # ── get_trip_context ──────────────────────────────────────────────────────

    async def get_trip_context(self, trip_id: str, user_id: str) -> TripFlightContext:
        """Get flight search context pre-filled from an existing trip + user profile.

        Reads:
        - The **trip's** destination, start date, and traveler count
        - The **user's** home city (from their profile)

        Both destination and home city are resolved to IATA codes automatically
        so the frontend can pre-populate the entire flight search form without
        asking the user for anything they've already told us.

        The user can still click any field to change it — we're just being
        friendly and remembering what we already know.

        Args:
            trip_id: The trip to derive context from.
            user_id: The authenticated user (for ownership check).

        Returns:
            A ``TripFlightContext`` with pre-filled suggestions.

        Raises:
            ValueError: If the trip is not found or doesn't belong to this user.
        """
        # ── Fetch trip ──
        result = await self.db.execute(
            select(Trip).where(
                Trip.trip_id == trip_id,
                Trip.user_id == user_id,
            )
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        # ── Fetch user's home city ──
        user_result = await self.db.execute(
            select(User).where(User.user_id == user_id)
        )
        user = user_result.scalar_one_or_none()
        home_city = user.home_city if user else None

        # ── Resolve home city → IATA ──
        home_iata: str | None = None
        if home_city:
            try:
                resolved = self.resolve_city_to_iata(home_city)
                home_iata = resolved.iata_code
            except ValueError:
                pass  # Nice-to-have, not critical

        # ── Resolve destination city → IATA ──
        dest_iata: str | None = None
        if trip.destination:
            try:
                resolved = self.resolve_city_to_iata(trip.destination)
                dest_iata = resolved.iata_code
            except ValueError:
                pass  # Nice-to-have, not critical

        return TripFlightContext(
            trip_id=trip.trip_id,
            trip_name=trip.trip_name,
            home_city=home_city,
            home_city_iata=home_iata,
            destination_city=trip.destination,
            destination_iata=dest_iata,
            suggested_departure_date=trip.start_date.isoformat() if trip.start_date else None,
            suggested_return_date=trip.end_date.isoformat() if trip.end_date else None,
            suggested_adults=trip.number_of_travelers or 1,
        )

    # ── initiate_flight_booking ───────────────────────────────────────────────

    async def initiate_flight_booking(
        self,
        data: FlightBookInitiateRequest,
    ) -> FlightBookInitiateResponse:
        """Initiate a flight booking — price the raw offer and create a Stripe PaymentIntent.

        Accepts the ``raw_offer`` dict directly from search results.  Prices
        the flight via Amadeus, creates a Stripe PaymentIntent with
        ``automatic_payment_methods`` enabled, and returns the parsed
        ``priced_offer`` (Flutter stores this and sends it back in confirm).

        Does NOT touch the database — the actual booking happens in
        ``confirm_flight_booking()`` after Stripe confirms payment.

        Args:
            data: Initiate request (raw_offer + trip_id).

        Returns:
            A ``FlightBookInitiateResponse`` with ``client_secret`` for
            Flutter's Stripe Payment Sheet, the parsed ``priced_offer``
            (needed for the confirm step), and flight summary fields.

        Raises:
            ValueError: If parsing the offer fails.
        """
        # 1. Price the offer via Amadeus (has fallback internally)
        priced_offer = amadeus_client.price_flight(data.raw_offer)

        # 2. Parse from priced offer (handle both wrapped and unwrapped structure)
        if "flightOffers" in priced_offer:
            flight_offer = priced_offer["flightOffers"][0]
        else:
            flight_offer = priced_offer

        total_price = float(flight_offer["price"]["total"])
        currency = flight_offer["price"]["currency"]
        segment = flight_offer["itineraries"][0]["segments"][0]
        last_segment = flight_offer["itineraries"][0]["segments"][-1]
        origin = segment["departure"]["iataCode"]
        destination = last_segment["arrival"]["iataCode"]
        departure_at = datetime.fromisoformat(segment["departure"]["at"].replace("Z", "+00:00"))
        arrival_at = datetime.fromisoformat(last_segment["arrival"]["at"].replace("Z", "+00:00"))
        airline_code = flight_offer["validatingAirlineCodes"][0]
        flight_number = f"{segment['carrierCode']}{segment['number']}"
        cabin_class = flight_offer["travelerPricings"][0]["fareDetailsBySegment"][0]["cabin"]

        # 3. Get airline name from Amadeus reference data
        airline_name = airline_code
        try:
            r = amadeus_client._client.reference_data.airlines.get(
                airlineCodes=airline_code
            )
            airline_name = r.data[0]["businessName"]
        except Exception:
            pass

        # 4. Create Stripe PaymentIntent
        import stripe
        from app.core.config import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY

        intent = stripe.PaymentIntent.create(
            amount=int(total_price * 100),
            currency=currency.lower(),
            automatic_payment_methods={"enabled": True},
            metadata={
                "trip_id": data.trip_id,
                "origin": origin,
                "destination": destination,
                "flight_number": flight_number,
            },
        )

        # 5. Do NOT touch DB
        # 6. Return response with priced_offer for Flutter to keep
        logger.info(
            "[FlightService] Initiated flight booking (flight=%s, cost=%.2f %s, stripe_pi=%s)",
            flight_number, total_price, currency, intent["id"],
        )

        return FlightBookInitiateResponse(
            client_secret=intent["client_secret"],
            payment_intent_id=intent["id"],
            priced_offer=flight_offer,
            amount=total_price,
            currency=currency,
            origin_iata=origin,
            destination_iata=destination,
            departure_at=departure_at,
            arrival_at=arrival_at,
            airline_name=airline_name,
            flight_number=flight_number,
            cabin_class=cabin_class,
        )

    # ── confirm_flight_booking ────────────────────────────────────────────────

    async def confirm_flight_booking(
        self,
        user_id: str,
        data: FlightBookConfirmRequest,
    ) -> Booking:
        """Confirm a flight booking after Stripe payment succeeded.

        Verifies the Stripe PaymentIntent status is ``succeeded``, calls
        Amadeus to create the order with the ``priced_offer`` from the client,
        then creates Booking + Payment + Receipt records.  Nothing is saved
        to the DB unless BOTH Stripe and Amadeus succeed.

        Args:
            user_id: The authenticated user.
            data:    Confirm request with payment_intent_id, priced_offer,
                     and traveler info.

        Returns:
            The created ``Booking`` ORM object (not yet committed).

        Raises:
            ValueError: If Stripe payment failed or Amadeus booking fails
                       (with special "PAYMENT_RECEIVED_BOOKING_FAILED" message
                       so the router can return a 402).
        """
        # ── 1. Verify Stripe PaymentIntent ──
        import stripe
        from app.core.config import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY

        intent = stripe.PaymentIntent.retrieve(data.payment_intent_id)
        if intent.status != "succeeded":
            raise ValueError("Payment not completed")

        # ── 2. Use the priced_offer from the client (Flutter stored it) ──
        priced_offer = data.priced_offer

        # ── 3. Build traveler dict in Amadeus format ──
        traveler = {
            "id": "1",
            "dateOfBirth": data.traveler_date_of_birth.isoformat(),
            "gender": data.traveler_gender,
            "name": {
                "firstName": data.traveler_first_name,
                "lastName": data.traveler_last_name,
            },
            "contact": {
                "emailAddress": data.traveler_email,
                "phones": [
                    {
                        "number": data.traveler_phone,
                        "deviceType": "MOBILE",
                        "countryCallingCode": "20",
                    },
                ],
            },
            "documents": [],
        }

        # ── 4. Call Amadeus Create Order ──
        try:
            order = amadeus_client.book_flight(priced_offer, traveler)
            amadeus_order_id = order.get("id", "UNKNOWN")
        except Exception:
            raise ValueError("PAYMENT_RECEIVED_BOOKING_FAILED")

        # ── 5. Parse flight details from priced_offer ──
        if "flightOffers" in priced_offer:
            flight_offer = priced_offer["flightOffers"][0]
        else:
            flight_offer = priced_offer

        total_price = float(flight_offer["price"]["total"])
        currency = flight_offer["price"]["currency"]
        segment = flight_offer["itineraries"][0]["segments"][0]
        last_segment = flight_offer["itineraries"][0]["segments"][-1]
        origin = segment["departure"]["iataCode"]
        destination = last_segment["arrival"]["iataCode"]
        departure_at = datetime.fromisoformat(segment["departure"]["at"].replace("Z", "+00:00"))
        arrival_at = datetime.fromisoformat(last_segment["arrival"]["at"].replace("Z", "+00:00"))
        airline_code = flight_offer["validatingAirlineCodes"][0]
        flight_number = f"{segment['carrierCode']}{segment['number']}"
        cabin_class = flight_offer["travelerPricings"][0]["fareDetailsBySegment"][0]["cabin"]

        # Airline name via Amadeus reference data
        try:
            response = amadeus_client._client.reference_data.airlines.get(
                airlineCodes=airline_code
            )
            airline_name = response.data[0]["businessName"]
        except Exception:
            airline_name = airline_code

        # ── 6. Generate IDs ──
        booking_id = _generate_flight_booking_id()
        confirmation_number = _generate_confirmation_number()
        payment_id = "PAY-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        receipt_id = "REC-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        seg1 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        seg2 = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        receipt_number = f"RCPT-{seg1}-{seg2}"

        # ── 7. Create Booking ORM ──
        booking = Booking(
            booking_id=booking_id,
            trip_id=data.trip_id,
            user_id=user_id,
            booking_type=BookingType.flight,
            provider=BookingProvider.amadeus,
            provider_reference=amadeus_order_id,
            confirmation_number=confirmation_number,
            start_datetime=departure_at,
            end_datetime=arrival_at,
            total_cost=total_price,
            currency=currency,
            status=BookingStatus.confirmed,
            raw_response={
                "origin_iata": origin,
                "destination_iata": destination,
                "airline_code": airline_code,
                "airline_name": airline_name,
                "flight_number": flight_number,
                "cabin_class": cabin_class,
                "amadeus_order_id": amadeus_order_id,
                "stripe_payment_intent_id": data.payment_intent_id,
                "traveler_name": f"{data.traveler_first_name} {data.traveler_last_name}",
                "simulated": order.get("simulated", False),
                "note": "Booked via Amadeus test environment",
            },
        )

        # ── 8. Create Payment ORM ──
        payment = Payment(
            payment_id=payment_id,
            booking_id=booking_id,
            amount=total_price,
            currency=currency,
            payment_method=PaymentMethod.card,
            provider=PaymentProvider.stripe,
            stripe_payment_intent_id=data.payment_intent_id,
            transaction_reference=data.payment_intent_id,
            status=PaymentStatus.completed,
            raw_response={
                "stripe_status": "succeeded",
                "payment_intent_id": data.payment_intent_id,
            },
        )

        # ── 9. Create Receipt ORM ──
        receipt = Receipt(
            receipt_id=receipt_id,
            payment_id=payment_id,
            receipt_number=receipt_number,
            subtotal=total_price,
            tax=0.0,
            total=total_price,
            currency=currency,
        )

        # ── 10. Add all to session (don't commit — let router commit) ──
        self.db.add(booking)
        self.db.add(payment)
        self.db.add(receipt)

        logger.info(
            "[FlightService] Confirmed flight booking %s for trip %s "
            "(airline=%s, flight=%s, cost=%.2f %s, stripe=%s)",
            booking_id, data.trip_id, airline_code, flight_number,
            total_price, currency, data.payment_intent_id,
        )

        return booking

    # ── get_flight_booking ────────────────────────────────────────────────────

    async def get_flight_booking(self, booking_id: str) -> Booking | None:
        """Fetch a single flight booking by ID with payment + receipt eager-loaded.

        Returns ``None`` if not found or the booking is not a flight booking.
        """
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.payment).selectinload(Payment.receipt),
            )
            .where(
                Booking.booking_id == booking_id,
                Booking.booking_type == BookingType.flight,
            )
        )
        return result.scalar_one_or_none()

    # ── list_trip_flight_bookings ─────────────────────────────────────────────

    async def list_trip_flight_bookings(self, trip_id: str) -> list[Booking]:
        """List all flight bookings for a trip, newest first."""
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.payment).selectinload(Payment.receipt),
            )
            .where(
                Booking.trip_id == trip_id,
                Booking.booking_type == BookingType.flight,
            )
            .order_by(Booking.created_at.desc())
        )
        return list(result.scalars().all())

    # ── cancel_flight_booking ─────────────────────────────────────────────────

    async def cancel_flight_booking(self, booking_id: str, user_id: str) -> Booking:
        """Cancel a flight booking.

        Args:
            booking_id: The flight booking ID to cancel.
            user_id:    The user requesting cancellation (must match owner).

        Returns:
            The updated ``Booking`` ORM object (not yet committed).

        Raises:
            ValueError: If not found, user mismatch, or already cancelled.
        """
        booking = await self.get_flight_booking(booking_id)
        if not booking:
            raise ValueError(f"Flight booking {booking_id} not found")
        if booking.user_id != user_id:
            raise ValueError(f"Flight booking {booking_id} does not belong to this user")
        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Flight booking {booking_id} is already cancelled")

        booking.status = BookingStatus.cancelled
        booking.raw_response = {
            **(booking.raw_response or {}),
            "cancelled_at": datetime.utcnow().isoformat(),
        }

        logger.info("[FlightService] Cancelled flight booking %s", booking_id)
        return booking

    # ── internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_offer(
        offer: dict,
        idx: int,
        airline_names: dict[str, str],
    ) -> FlightOfferItem:
        """Parse a raw Amadeus offer dict into a ``FlightOfferItem``.

        Raises ``KeyError`` or ``IndexError`` if the offer structure is
        malformed.
        """
        airline_code = offer["validatingAirlineCodes"][0]
        itinerary = offer["itineraries"][0]
        segment = itinerary["segments"][0]
        flight_number = f"{segment['carrierCode']}{segment['number']}"

        departure_at = datetime.fromisoformat(
            segment["departure"]["at"].replace("Z", "+00:00")
        )
        arrival_at = datetime.fromisoformat(
            segment["arrival"]["at"].replace("Z", "+00:00")
        )

        cabin_class = (
            offer["travelerPricings"][0]
            ["fareDetailsBySegment"][0]
            ["cabin"]
        )

        total_price = float(offer["price"]["total"])
        currency = offer["price"]["currency"]
        price_per_adult = float(offer["price"]["base"])

        return FlightOfferItem(
            offer_index=idx,
            airline_code=airline_code,
            airline_name=airline_names.get(airline_code, airline_code),
            flight_number=flight_number,
            origin_iata=segment["departure"]["iataCode"],
            destination_iata=segment["arrival"]["iataCode"],
            departure_at=departure_at,
            arrival_at=arrival_at,
            cabin_class=cabin_class,
            total_price=total_price,
            currency=currency,
            price_per_adult=price_per_adult,
            raw_offer=offer,
        )
