"""Itinerary, Day, ItineraryStop models."""

import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Text, Date, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ItineraryStatus, StopStatus, TravelMode, TimeOfDay


# ─── Itinerary ───────────────────────────────────────────────────────────────

class Itinerary(Base):
    __tablename__ = "itineraries"

    itinerary_id        = Column(String, primary_key=True)
    trip_id             = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number      = Column(Integer, default=1)
    description         = Column(Text, nullable=True)
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

    day_id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    itinerary_id    = Column(String, ForeignKey("itineraries.itinerary_id", ondelete="CASCADE"), nullable=False, index=True)
    day_number      = Column(Integer, nullable=False)
    date            = Column(Date, nullable=True)
    theme           = Column(String, nullable=True)
    description     = Column(Text, nullable=True)

    # Relationships
    itinerary = relationship("Itinerary", back_populates="days")
    stops     = relationship("ItineraryStop", back_populates="day", cascade="all, delete-orphan", order_by="ItineraryStop.order_in_day")


# ─── ItineraryStop ───────────────────────────────────────────────────────────

class ItineraryStop(Base):
    __tablename__ = "itinerary_stops"

    stop_id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    day_id                = Column(String, ForeignKey("days.day_id", ondelete="CASCADE"), nullable=False, index=True)
    place_id              = Column(String, ForeignKey("places.place_id"), nullable=True)
    place_snapshot        = Column(JSON, nullable=True)       # snapshot of Place data at creation time
    duration_minutes      = Column(Integer, nullable=True)
    order_in_day          = Column(Integer, default=0)
    time_of_day           = Column(SAEnum(TimeOfDay, name="time_of_day", values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    minutes_from_prev_stop = Column(Integer, nullable=True)
    travel_mode           = Column(SAEnum(TravelMode, name="travel_mode", values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    estimated_cost        = Column(Float, nullable=True)
    ai_notes              = Column(Text, nullable=True)
    status                = Column(
        SAEnum(StopStatus, name="stop_status"),
        default=StopStatus.planned,
        nullable=False,
    )
    created_at            = Column(DateTime, default=func.now())

    # Relationships
    day   = relationship("Day", back_populates="stops")
    place = relationship("Place")
