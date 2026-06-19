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
