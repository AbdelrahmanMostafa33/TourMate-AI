"""Booking, Payment, Receipt models."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, JSON,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import (
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
)


# ─── Booking ─────────────────────────────────────────────────────────────────

class Booking(Base):
    __tablename__ = "bookings"

    booking_id          = Column(String, primary_key=True)
    trip_id             = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id             = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    place_id            = Column(String, ForeignKey("places.place_id"), nullable=True)
    booking_type        = Column(SAEnum(BookingType, name="booking_type"), nullable=False)
    provider            = Column(SAEnum(BookingProvider, name="booking_provider"), nullable=True)
    provider_reference  = Column(String, nullable=True)
    confirmation_number = Column(String, nullable=True)
    booking_date        = Column(DateTime, default=func.now())
    start_datetime      = Column(DateTime, nullable=True)
    end_datetime        = Column(DateTime, nullable=True)
    total_cost          = Column(Float, nullable=True)
    currency            = Column(String(3), nullable=True)
    status              = Column(
        SAEnum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
    )
    raw_response        = Column(JSON, nullable=True)
    created_at          = Column(DateTime, default=func.now())
    updated_at          = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trip    = relationship("Trip",    back_populates="bookings")
    user    = relationship("User")
    payment = relationship("Payment", back_populates="booking", uselist=False, cascade="all, delete-orphan")


# ─── Payment ─────────────────────────────────────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    payment_id            = Column(String, primary_key=True)
    booking_id            = Column(String, ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    amount                = Column(Float, nullable=False)
    currency              = Column(String(3), nullable=True)
    payment_method        = Column(SAEnum(PaymentMethod, name="payment_method"), nullable=False)
    provider              = Column(SAEnum(PaymentProvider, name="payment_provider"), nullable=True)
    stripe_payment_intent_id = Column(String, nullable=True)
    transaction_reference = Column(String, nullable=True)
    status                = Column(
        SAEnum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
    )
    raw_response          = Column(JSON, nullable=True)
    paid_at               = Column(DateTime, default=func.now())
    created_at            = Column(DateTime, default=func.now())
    updated_at            = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    booking = relationship("Booking", back_populates="payment")
    receipt = relationship("Receipt", back_populates="payment", uselist=False, cascade="all, delete-orphan")


# ─── Receipt ─────────────────────────────────────────────────────────────────

class Receipt(Base):
    __tablename__ = "receipts"

    receipt_id     = Column(String, primary_key=True)
    payment_id     = Column(String, ForeignKey("payments.payment_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    receipt_number = Column(String, nullable=False)
    issue_date     = Column(DateTime, default=func.now())
    subtotal       = Column(Float, nullable=False)
    tax            = Column(Float, nullable=True)
    total          = Column(Float, nullable=False)
    currency       = Column(String(3), nullable=True)

    # Relationships
    payment = relationship("Payment", back_populates="receipt")
