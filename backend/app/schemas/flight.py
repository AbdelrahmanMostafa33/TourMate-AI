"""
Flight booking Pydantic schemas.

Defines request/response shapes for the Amadeus flight booking simulation
feature.  Flight bookings reuse the existing ``Booking`` table with
``booking_type=flight`` and ``provider=amadeus``, so the response schema
unpacks flight-specific fields from the ``raw_response`` JSON column.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.booking import Booking
from app.models.enums import BookingStatus
from app.schemas.booking import PaymentResponse


# ─── City / Airport Autocomplete ──────────────────────────────────────────────

class CitySearchResult(BaseModel):
    """A single city or airport returned from the Amadeus autocomplete API."""

    iata_code: str
    city_name: str
    airport_name: str | None = None
    country_name: str
    sub_type: str  # "AIRPORT" or "CITY"


# ─── Search ───────────────────────────────────────────────────────────────────

class FlightSearchRequest(BaseModel):
    """Search parameters for flight offers via Amadeus.

    ``origin`` and ``destination`` accept **either**:
    - A 3-letter IATA code (``\"CAI\"``)
    - A city name (``\"cairo\"``)  – the server will auto-resolve it to an IATA code
    """

    origin: str
    destination: str
    departure_date: date
    adults: int = 1
    max_results: int = 5

    @field_validator("origin", "destination")
    @classmethod
    def uppercase_iata(cls, v: str) -> str:
        """Normalise IATA codes to uppercase."""
        return v.strip().upper()


class SmartFlightSearchRequest(BaseModel):
    """Flight search that intelligently resolves city names to IATA codes.

    Unlike ``FlightSearchRequest`` which expects raw IATA codes only (and
    preserves the city-name-as-IATA for server-side resolution), this schema
    makes the resolution explicit: frontends send city names and get back
    the resolved result alongside the flight offers.
    """

    origin_city: str
    destination_city: str
    departure_date: date
    adults: int = 1
    max_results: int = 5


class SmartFlightSearchResponse(BaseModel):
    """Response from the smart-search endpoint.

    Includes the resolved IATA codes so frontends can display which airports
    were matched, plus the flight offers themselves.
    """

    origin: CitySearchResult
    destination: CitySearchResult
    offers: list[FlightOfferItem]


class FlightOfferItem(BaseModel):
    """A single parsed flight offer returned from a search."""

    offer_index: int
    airline_code: str
    airline_name: str
    flight_number: str
    origin_iata: str
    destination_iata: str
    departure_at: datetime
    arrival_at: datetime
    cabin_class: str
    total_price: float
    currency: str
    price_per_adult: float
    raw_offer: dict

    class Config:
        from_attributes = True


# ─── Saved Offers ────────────────────────────────────────────────────────────

class SaveFlightOfferRequest(BaseModel):
    """Save a selected flight offer for later booking."""

    trip_id: str
    offer_index: int
    raw_offer: dict


class SavedFlightOfferResponse(BaseModel):
    """Response after saving a flight offer."""

    offer_id: str
    trip_id: str
    offer_index: int
    origin_iata: str | None = None
    destination_iata: str | None = None
    airline_code: str | None = None
    flight_number: str | None = None
    total_price: float | None = None
    currency: str | None = None
    departure_at: datetime | None = None
    arrival_at: datetime | None = None


# ─── Trip Context ─────────────────────────────────────────────────────────────

class TripFlightContext(BaseModel):
    """Pre-filled flight search suggestions derived from an existing trip.

    Frontends can use this to auto-populate the flight search form
    when a user has an existing trip with a known destination and dates.

    The ``home_city`` (and its IATA) come from the user's profile —
    set during registration or in profile settings.  The destination
    fields come from the trip itself.
    """

    trip_id: str
    trip_name: str | None = None

    # ── From user profile (home city) ──
    home_city: str | None = None
    home_city_iata: str | None = None

    # ── From trip (destination) ──
    destination_city: str
    destination_iata: str | None = None
    suggested_departure_date: str | None = None
    suggested_return_date: str | None = None
    suggested_adults: int = 1


# ─── Booking ──────────────────────────────────────────────────────────────────

class FlightBookRequest(BaseModel):
    """Request payload to book a flight (create a Booking row + Amadeus order)."""

    trip_id: str
    raw_offer: dict
    traveler_first_name: str
    traveler_last_name: str
    traveler_date_of_birth: date
    traveler_gender: str  # "MALE" or "FEMALE"
    traveler_email: str
    traveler_phone: str

    @field_validator("traveler_gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("MALE", "FEMALE"):
            raise ValueError("traveler_gender must be 'MALE' or 'FEMALE'")
        return upper


class FlightBookFromOfferRequest(BaseModel):
    """Book a flight from a previously saved offer — no raw_offer needed.

    Instead of passing the full ``raw_offer`` dict (which can be very large),
    the frontend references the ``offer_id`` returned by
    ``POST /flights/offer`` and only sends the traveler details.
    """

    trip_id: str
    traveler_first_name: str
    traveler_last_name: str
    traveler_date_of_birth: date
    traveler_gender: str  # "MALE" or "FEMALE"
    traveler_email: str
    traveler_phone: str

    @field_validator("traveler_gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        upper = v.strip().upper()
        if upper not in ("MALE", "FEMALE"):
            raise ValueError("traveler_gender must be 'MALE' or 'FEMALE'")
        return upper


class FlightBookingResponse(BaseModel):
    """Response shape for a flight booking, unpacking fields from raw_response."""

    booking_id: str
    trip_id: str
    user_id: str
    status: BookingStatus
    total_cost: float | None = None
    currency: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    confirmation_number: str | None = None
    created_at: datetime | None = None

    # Flight-specific fields (unpacked from raw_response)
    origin_iata: str | None = None
    destination_iata: str | None = None
    airline_name: str | None = None
    flight_number: str | None = None
    cabin_class: str | None = None
    amadeus_order_id: str | None = None

    payment: Optional[PaymentResponse] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_booking(cls, booking: Booking) -> "FlightBookingResponse":
        """Build a response from a Booking ORM object, extracting flight fields."""
        raw = booking.raw_response or {}
        return cls(
            booking_id=booking.booking_id,
            trip_id=booking.trip_id,
            user_id=booking.user_id,
            status=booking.status,
            total_cost=booking.total_cost,
            currency=booking.currency,
            start_datetime=booking.start_datetime,
            end_datetime=booking.end_datetime,
            confirmation_number=booking.confirmation_number,
            created_at=booking.created_at,
            origin_iata=raw.get("origin_iata"),
            destination_iata=raw.get("destination_iata"),
            airline_name=raw.get("airline_name"),
            flight_number=raw.get("flight_number"),
            cabin_class=raw.get("cabin_class"),
            amadeus_order_id=raw.get("amadeus_order_id"),
            payment=PaymentResponse.model_validate(booking.payment)
            if booking.payment else None,
        )
