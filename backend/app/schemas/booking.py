"""Booking, Payment, Receipt schemas."""

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date, datetime

from app.models.enums import (
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
)


class ReceiptResponse(BaseModel):
    """Response schema for Receipt – aligns with model fields."""
    receipt_id:     str
    payment_id:     str
    receipt_number: str
    issue_date:     datetime
    subtotal:       float
    tax:            Optional[float] = None
    total:          float
    currency:       Optional[str] = None

    class Config:
        from_attributes = True


# ─── Payment ─────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    """Create schema for Payment – aligns with model fields."""
    amount:                float
    currency:              Optional[str] = None
    payment_method:        PaymentMethod
    provider:              Optional[PaymentProvider] = None
    stripe_payment_intent_id: Optional[str] = None
    transaction_reference: Optional[str] = None


class PaymentResponse(BaseModel):
    """Response schema for Payment – aligns with model fields."""
    payment_id:            str
    booking_id:            str
    amount:                float
    currency:              Optional[str] = None
    payment_method:        PaymentMethod
    provider:              Optional[PaymentProvider] = None
    stripe_payment_intent_id: Optional[str] = None
    status:                PaymentStatus
    transaction_reference: Optional[str]
    raw_response:          Optional[dict] = None
    paid_at:               datetime
    created_at:            datetime
    updated_at:            Optional[datetime] = None
    receipt:               Optional[ReceiptResponse] = None

    class Config:
        from_attributes = True


# ─── Booking ─────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    """Create schema for Booking – aligns with model fields."""
    trip_id:             Optional[str]     = None  # Optional since it's passed to create_booking() as a param
    booking_type:        BookingType
    place_id:            Optional[str]     = None
    provider:            Optional[BookingProvider] = None
    provider_reference:  Optional[str]     = None
    confirmation_number: Optional[str]     = None
    start_datetime:      Optional[datetime] = None
    end_datetime:        Optional[datetime] = None
    total_cost:          Optional[float]   = None
    currency:            Optional[str]     = None


class BookingResponse(BaseModel):
    """Response schema for Booking – aligns with model fields."""
    booking_id:          str
    trip_id:             str
    user_id:             str
    place_id:            Optional[str]
    booking_type:        BookingType
    provider:            Optional[BookingProvider] = None
    provider_reference:  Optional[str] = None
    confirmation_number: Optional[str]
    booking_date:        datetime
    start_datetime:      Optional[datetime]
    end_datetime:        Optional[datetime]
    total_cost:          Optional[float]
    currency:            Optional[str] = None
    status:              BookingStatus
    raw_response:        Optional[dict] = None
    created_at:          datetime
    updated_at:          Optional[datetime] = None
    payment:             Optional[PaymentResponse] = None

    class Config:
        from_attributes = True


# ─── Confirm After Payment (client-side verification) ────────────────────

class ConfirmAfterPaymentRequest(BaseModel):
    """Request for confirming a booking after the Payment Sheet succeeds.

    The Flutter app sends this after the Stripe Payment Sheet completes
    successfully.  The backend verifies the PaymentIntent status with Stripe
    directly (not trusting the client) and confirms the booking immediately.
    """
    stripe_payment_intent_id: str


# ─── Combined (flight + hotel) booking ───────────────────────────────────

class CombinedBookInitiateRequest(BaseModel):
    """Initiate a combined flight + hotel payment.

    Prices the flight via Amadeus, creates a pending hotel booking, and
    generates a single Stripe PaymentIntent for the combined total.

    Supports three modes:
    - **Both** (flight + hotel): set ``raw_offer`` + ``hotel_place_id``
    - **Flight only**: set ``raw_offer``, leave ``hotel_place_id`` null
    - **Hotel only**: set ``hotel_place_id``, leave ``raw_offer`` null
    """
    trip_id:              str
    raw_offer:            Optional[dict]   = None
    hotel_place_id:       Optional[str]    = None
    hotel_total_cost:     Optional[float]  = None
    hotel_currency:       Optional[str]    = None
    hotel_start_datetime: Optional[datetime] = None
    hotel_end_datetime:   Optional[datetime] = None


class CombinedBookInitiateResponse(BaseModel):
    """Response from combined initiate — single Stripe PaymentIntent.

    Flight fields are null when only a hotel is booked (and vice versa).
    """
    client_secret:          str
    payment_intent_id:      str
    combined_amount:        float
    currency:               str
    # Flight fields (null when hotel-only)
    flight_airline_name:    Optional[str] = None
    flight_number:          Optional[str] = None
    flight_origin_iata:     Optional[str] = None
    flight_destination_iata: Optional[str] = None
    flight_departure_at:    Optional[datetime] = None
    flight_arrival_at:      Optional[datetime] = None
    flight_cabin_class:     Optional[str] = None
    flight_amount:          Optional[float] = None
    # Hotel fields (null when flight-only)
    hotel_booking_id:       Optional[str] = None
    hotel_amount:           Optional[float] = None
    # Flutter stores this and sends it back on confirm (null when hotel-only)
    priced_offer:           Optional[dict] = None


class CombinedBookConfirmRequest(BaseModel):
    """Confirm after Stripe succeeds — supports flight-only, hotel-only, or both.

    ``priced_offer`` + traveler fields are required for flight booking, but
    ``hotel_booking_id`` is optional (null when flight-only).
    Conversely, ``priced_offer`` can be null when hotel-only.
    """
    payment_intent_id:     str
    priced_offer:          Optional[dict]   = None
    trip_id:               str
    hotel_booking_id:      Optional[str]    = None
    traveler_first_name:   Optional[str]    = None
    traveler_last_name:    Optional[str]    = None
    traveler_date_of_birth: Optional[date]  = None
    traveler_gender:       Optional[str]    = None
    traveler_email:        Optional[str]    = None
    traveler_phone:        Optional[str]    = None

    @field_validator("traveler_gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v is None:
            return v
        upper = v.strip().upper()
        if upper not in ("MALE", "FEMALE"):
            raise ValueError("traveler_gender must be 'MALE' or 'FEMALE'")
        return upper



