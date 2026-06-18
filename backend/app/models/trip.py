"""Trip model - matches the class diagram."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, DateTime,
    ForeignKey, JSON, Enum as SAEnum
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
    budget               = Column(Float, nullable=True)
    preferences          = Column(JSON, nullable=True)  # List[str]
    status               = Column(
        SAEnum(TripStatus, name="trip_status"),
        default=TripStatus.planning,
        nullable=False,
    )
    created_at           = Column(DateTime, default=func.now())

    # Relationships
    user            = relationship("User",            back_populates="trips")
    itineraries     = relationship("Itinerary",       back_populates="trip", cascade="all, delete-orphan")
    conversations   = relationship("Conversation",    back_populates="trip", cascade="all, delete-orphan")
    images          = relationship("Image",           back_populates="trip", cascade="all, delete-orphan")
    bookings        = relationship("Booking",         back_populates="trip", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation",  back_populates="trip", cascade="all, delete-orphan")
    feedbacks       = relationship("Feedback",        back_populates="trip", cascade="all, delete-orphan")
