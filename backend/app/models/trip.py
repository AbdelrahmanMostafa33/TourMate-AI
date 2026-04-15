from sqlalchemy import (
    Column, String, Integer, Float, Numeric,
    Date, DateTime, Time, Text, Enum, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
 
from app.core.database import Base
# ─── Enums ────────────────────────────────────────────────────────────────────
 
class TripStatus(str, enum.Enum):
    planning   = "planning"
    active     = "active"
    completed  = "completed"
 
class ActivityType(str, enum.Enum):
    attraction = "attraction"
    hotel      = "hotel"
    restaurant = "restaurant"
    transport  = "transport"
 
# ─── Trip ─────────────────────────────────────────────────────────────────────
 
class Trip(Base):
    __tablename__ = "trips"
 
    trip_id             = Column(String, primary_key=True)
    user_id             = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    destination_city    = Column(String, nullable=False)
    destination_country = Column(String, nullable=False)
    start_date          = Column(Date, nullable=False)
    end_date            = Column(Date, nullable=False)
    duration_days       = Column(Integer, default=1)
    status              = Column(Enum(TripStatus), default=TripStatus.planning, nullable=False)
    budget_total        = Column(Numeric(10, 2), nullable=True)
    traveler_count      = Column(Integer, default=1)
    input_mode          = Column(Enum(InputMode), default=InputMode.ai_chat)
    created_at          = Column(DateTime, default=func.now())
 
    # Relationships
    days          = relationship("TripDay",      back_populates="trip", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="trip", cascade="all, delete-orphan")
 
 
# ─── TripDay ──────────────────────────────────────────────────────────────────
 
class TripDay(Base):
    __tablename__ = "trip_days"
 
    day_id     = Column(Integer, primary_key=True, autoincrement=True)
    trip_id    = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    day_number = Column(Integer, nullable=False)
    date       = Column(Date, nullable=True)
 
    # Relationships
    trip       = relationship("Trip",         back_populates="days")
    activities = relationship("TripActivity", back_populates="day", cascade="all, delete-orphan")
 
 
# ─── TripActivity ─────────────────────────────────────────────────────────────
 
class TripActivity(Base):
    __tablename__ = "trip_activities"
 
    activity_id    = Column(Integer, primary_key=True, autoincrement=True)
    day_id         = Column(Integer, ForeignKey("trip_days.day_id", ondelete="CASCADE"), nullable=False, index=True)
    name           = Column(String, nullable=False)
    type           = Column(Enum(ActivityType), nullable=False)
    time           = Column(Time,  nullable=True)
    duration_hours = Column(Float, nullable=True)
    notes          = Column(Text,  nullable=True)
    created_at     = Column(DateTime, default=func.now())
 
    # Relationships
    day = relationship("TripDay", back_populates="activities")