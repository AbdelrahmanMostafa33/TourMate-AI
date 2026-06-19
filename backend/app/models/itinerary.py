"""Itinerary, Day, ItineraryStop models."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, Time, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ItineraryStatus, StopStatus, TravelMode, StopClassification, TimeOfDay


# ─── Itinerary ───────────────────────────────────────────────────────────────

class Itinerary(Base):
    __tablename__ = "itineraries"

    itinerary_id        = Column(String, primary_key=True)
    trip_id             = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number      = Column(Integer, default=1)
    title               = Column(String, nullable=True)
    description         = Column(Text, nullable=True)
    total_estimated_cost = Column(Float, nullable=True)
    status              = Column(
        SAEnum(ItineraryStatus, name="itinerary_status"),
        default=ItineraryStatus.draft,
        nullable=False,
    )
    created_at          = Column(DateTime, default=func.now())
    updated_at          = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="itineraries")
    days = relationship("Day", back_populates="itinerary", cascade="all, delete-orphan", order_by="Day.day_number")


# ─── Day ─────────────────────────────────────────────────────────────────────

class Day(Base):
    __tablename__ = "days"

    day_id          = Column(Integer, primary_key=True, autoincrement=True)
    itinerary_id    = Column(String, ForeignKey("itineraries.itinerary_id", ondelete="CASCADE"), nullable=False, index=True)
    day_number      = Column(Integer, nullable=False)
    date            = Column(Date, nullable=True)
    theme           = Column(String, nullable=True)
    description     = Column(Text, nullable=True)
    estimated_cost  = Column(Float, nullable=True)

    # Relationships
    itinerary = relationship("Itinerary", back_populates="days")
    stops     = relationship("ItineraryStop", back_populates="day", cascade="all, delete-orphan", order_by="ItineraryStop.order_in_day")


# ─── ItineraryStop ───────────────────────────────────────────────────────────

class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"

    stop_id               = Column(Integer, primary_key=True, autoincrement=True)
    day_id                = Column(Integer, ForeignKey("days.day_id", ondelete="CASCADE"), nullable=False, index=True)
    place_id              = Column(String, ForeignKey("places.place_id"), nullable=True)
    place_snapshot        = Column(JSON, nullable=True)       # snapshot of Place data at creation time
    scheduled_time        = Column(Time, nullable=True)
    duration_minutes      = Column(Integer, nullable=True)
    order_in_day          = Column(Integer, default=0)
    classification        = Column(SAEnum(StopClassification, name="stop_classification"), nullable=True)
    importance_score      = Column(Integer, nullable=True)
    time_of_day           = Column(SAEnum(TimeOfDay, name="time_of_day"), nullable=True)
    minutes_from_prev_stop = Column(Integer, nullable=True)
    travel_mode           = Column(SAEnum(TravelMode, name="travel_mode"), nullable=True)
    estimated_cost        = Column(Float, nullable=True)
    ai_notes              = Column(Text, nullable=True)
    user_notes            = Column(Text, nullable=True)
    status                = Column(
        SAEnum(StopStatus, name="stop_status"),
        default=StopStatus.planned,
        nullable=False,
    )
    created_at            = Column(DateTime, default=func.now())

    # Relationships
    day   = relationship("Day", back_populates="stops")
    place = relationship("Place")
