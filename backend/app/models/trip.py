"""Trip model - matches the class diagram."""

from sqlalchemy import (
    Column, String, Integer, Date, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import TripStatus


# --- Trip ---

class Trip(Base):
    __tablename__ = "trips"

    trip_id              = Column(String, primary_key=True)
    user_id              = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    trip_name            = Column(String, nullable=True)
    destination          = Column(String, nullable=False)
    start_date           = Column(Date, nullable=True)
    end_date             = Column(Date, nullable=True)
    number_of_travelers  = Column(Integer, default=1)
    conversation_id      = Column(String, ForeignKey("conversations.conversation_id"), nullable=True, index=True)
    status               = Column(
        SAEnum(TripStatus, name="trip_status"),
        default=TripStatus.planning,
        nullable=False,
    )
    created_at           = Column(DateTime, default=func.now())
    updated_at           = Column(DateTime, default=func.now(), onupdate=func.now())
    approved_at          = Column(DateTime, nullable=True)

    # Relationships
    user            = relationship("User",            back_populates="trips")
    itineraries     = relationship("Itinerary",       back_populates="trip", cascade="all, delete-orphan")
    conversation    = relationship("Conversation",    back_populates="trips", uselist=False)
    trip_profiles   = relationship("TripProfile",     back_populates="trip", cascade="all, delete-orphan")
    images          = relationship("Image",           back_populates="trip", cascade="all, delete-orphan")
    bookings        = relationship("Booking",         back_populates="trip", cascade="all, delete-orphan")
    feedbacks       = relationship("Feedback",        back_populates="trip", cascade="all, delete-orphan")
