"""Booking, Reservation, Payment, Receipt schemas."""

from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time, datetime

from app.models.enums import (
    BookingType, BookingStatus, ReservationStatus,
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
    amount:         float
    payment_method: PaymentMethod
    transaction_id: Optional[str] = None
    card_last_four: Optional[str] = None
    card_type:      Optional[str] = None


class PaymentResponse(BaseModel):
    """Response schema for Payment – aligns with model fields."""
    payment_id:     str
    booking_id:     str
    amount:         float
    payment_method: PaymentMethod
    transaction_id: Optional[str]
    status:         PaymentStatus
    payment_date:   datetime
    card_last_four: Optional[str]
    card_type:      Optional[str]
    receipt:        Optional[ReceiptResponse] = None

    class Config:
        from_attributes = True


# ─── Reservation ─────────────────────────────────────────────────────────────

class ReservationCreate(BaseModel):
    """Create schema for Reservation – aligns with model fields."""
    place_id:          Optional[str] = None
    reservation_date:  Optional[date] = None
    reservation_time:  Optional[time] = None
    number_of_people:  int = 1
    confirmation_code: Optional[str] = None
    special_requests:  Optional[str] = None


class ReservationResponse(BaseModel):
    """Response schema for Reservation – aligns with model fields."""
    reservation_id:    str
    place_id:          Optional[str]
    booking_id:        str
    reservation_date:  Optional[date]
    reservation_time:  Optional[time]
    number_of_people:  int
    status:            ReservationStatus
    confirmation_code: Optional[str]
    special_requests:  Optional[str]

    class Config:
        from_attributes = True


# ─── Booking ─────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    """Create schema for Booking – aligns with model fields."""
    booking_type:          BookingType
    confirmation_number:   Optional[str] = None
    total:                 Optional[float] = None
    cancellation_deadline: Optional[datetime] = None
    reservations:          Optional[List[ReservationCreate]] = []


class BookingResponse(BaseModel):
    """Response schema for Booking – aligns with model fields."""
    booking_id:            str
    user_id:               str
    booking_type:          BookingType
    status:                BookingStatus
    confirmation_number:   Optional[str]
    total:                 Optional[float]
    booking_date:          datetime
    cancellation_deadline: Optional[datetime]
    reservations:          List[ReservationResponse] = []
    payment:               Optional[PaymentResponse] = None

    class Config:
        from_attributes = True


class BookingStatusUpdate(BaseModel):
    """Update schema for Booking status."""
    status: BookingStatus
