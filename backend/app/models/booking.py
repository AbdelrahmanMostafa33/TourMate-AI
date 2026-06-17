"""Booking, Reservation, Payment, Receipt models."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, Time, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import (
    BookingType, BookingStatus, ReservationStatus,
    PaymentMethod, PaymentStatus,
)


# ─── Booking ─────────────────────────────────────────────────────────────────

class Booking(Base):
    __tablename__ = "bookings"

    booking_id            = Column(String, primary_key=True)
    user_id               = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    booking_type          = Column(SAEnum(BookingType, name="booking_type"), nullable=False)
    status                = Column(
        SAEnum(BookingStatus, name="booking_status"),
        default=BookingStatus.pending,
        nullable=False,
    )
    confirmation_number   = Column(String, nullable=True)
    total                 = Column(Float, nullable=True)
    booking_date          = Column(DateTime, default=func.now())
    cancellation_deadline = Column(DateTime, nullable=True)

    # Relationships
    user         = relationship("User", back_populates="bookings")
    reservations = relationship("Reservation", back_populates="booking", cascade="all, delete-orphan")
    payment      = relationship("Payment", back_populates="booking", uselist=False, cascade="all, delete-orphan")


# ─── Reservation ─────────────────────────────────────────────────────────────

class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id    = Column(String, primary_key=True)
    place_id          = Column(String, ForeignKey("places.place_id"), nullable=True)
    booking_id        = Column(String, ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, index=True)
    reservation_date  = Column(Date, nullable=True)
    reservation_time  = Column(Time, nullable=True)
    number_of_people  = Column(Integer, default=1)
    status            = Column(
        SAEnum(ReservationStatus, name="reservation_status"),
        default=ReservationStatus.pending,
        nullable=False,
    )
    confirmation_code = Column(String, nullable=True)
    special_requests  = Column(Text, nullable=True)

    # Relationships
    booking = relationship("Booking", back_populates="reservations")
    place   = relationship("Place")


# ─── Payment ─────────────────────────────────────────────────────────────────

class Payment(Base):
    __tablename__ = "payments"

    payment_id      = Column(String, primary_key=True)
    booking_id      = Column(String, ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    amount          = Column(Float, nullable=False)
    payment_method  = Column(SAEnum(PaymentMethod, name="payment_method"), nullable=False)
    transaction_id  = Column(String, nullable=True)
    status          = Column(
        SAEnum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
    )
    payment_date    = Column(DateTime, default=func.now())
    card_last_four  = Column(String, nullable=True)
    card_type       = Column(String, nullable=True)

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

    # Relationships
    payment = relationship("Payment", back_populates="receipt")
