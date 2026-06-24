"""Booking, Payment, Receipt schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.enums import (
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
)


# ─── Receipt ─────────────────────────────────────────────────────────────────

class ReceiptCreate(BaseModel):
    """Create schema for Receipt – aligns with model fields."""
    receipt_number: str
    subtotal:       float
    tax:            Optional[float] = None
    total:          float


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
    trip_id:             str
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


class BookingStatusUpdate(BaseModel):
    """Update schema for Booking status."""
    status: BookingStatus


# ─── Trip Package Booking ────────────────────────────────────────────────────

class PackageBookingItem(BaseModel):
    """A single booking created as part of a trip package."""
    booking_id:          str
    place_name:          str
    booking_type:        BookingType
    category:            str
    total_cost:          Optional[float] = None
    currency:            Optional[str] = None
    status:              BookingStatus
    confirmation_number: str


class TripPackageBookingResponse(BaseModel):
    """Response for booking an entire trip as a package."""
    trip_id:      str
    trip_name:    Optional[str] = None
    destination:  str
    total_cost:   float
    currency:     str
    bookings:     list[PackageBookingItem]
    stop_count:   int
    booking_count: int


# ─── Trip Package Payment ─────────────────────────────────────────────────

class PackagePaymentItem(BaseModel):
    """A single paid booking as part of a trip package payment."""
    booking_id:          str
    amount:              float
    currency:            str
    receipt_number:      str
    status:              BookingStatus = BookingStatus.confirmed


class PackagePaymentSkipItem(BaseModel):
    """A booking that was skipped during bulk payment."""
    booking_id:          str
    reason:              str


class BulkPaymentRequest(BaseModel):
    """Request for paying all pending bookings in a trip at once.

    The ``amount`` per booking is taken from each booking's ``total_cost``,
    so only ``payment_method`` and optional ``currency`` are needed here.
    """
    payment_method:     PaymentMethod
    currency:           Optional[str] = None


class TripPackagePaymentResponse(BaseModel):
    """Response for paying all pending bookings in a trip."""
    trip_id:           str
    total_charged:     float
    currency:          str
    paid_count:        int
    skipped_count:     int
    paid_bookings:     list[PackagePaymentItem]
    skipped_bookings:  list[PackagePaymentSkipItem]
