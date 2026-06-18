"""Booking, Payment, Receipt schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.enums import (
    BookingType, BookingStatus,
    PaymentMethod, PaymentStatus,
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

    class Config:
        from_attributes = True


# ─── Payment ─────────────────────────────────────────────────────────────────

class PaymentCreate(BaseModel):
    """Create schema for Payment – aligns with model fields."""
    amount:                float
    payment_method:        PaymentMethod
    transaction_reference: Optional[str] = None


class PaymentResponse(BaseModel):
    """Response schema for Payment – aligns with model fields."""
    payment_id:            str
    booking_id:            str
    amount:                float
    payment_method:        PaymentMethod
    status:                PaymentStatus
    transaction_reference: Optional[str]
    paid_at:               datetime
    created_at:            datetime
    receipt:               Optional[ReceiptResponse] = None

    class Config:
        from_attributes = True


# ─── Booking ─────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    """Create schema for Booking – aligns with model fields."""
    booking_type:        BookingType
    place_id:            Optional[str]     = None
    confirmation_number: Optional[str]     = None
    start_datetime:      Optional[datetime] = None
    end_datetime:        Optional[datetime] = None
    total_cost:          Optional[float]   = None


class BookingResponse(BaseModel):
    """Response schema for Booking – aligns with model fields."""
    booking_id:          str
    trip_id:             str
    place_id:            Optional[str]
    booking_type:        BookingType
    confirmation_number: Optional[str]
    booking_date:        datetime
    start_datetime:      Optional[datetime]
    end_datetime:        Optional[datetime]
    total_cost:          Optional[float]
    status:              BookingStatus
    created_at:          datetime
    payment:             Optional[PaymentResponse] = None

    class Config:
        from_attributes = True


class BookingStatusUpdate(BaseModel):
    """Update schema for Booking status."""
    status: BookingStatus
