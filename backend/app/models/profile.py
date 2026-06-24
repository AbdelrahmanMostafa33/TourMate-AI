# app/models/profile.py

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, JSON, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import BudgetLevel, TravelStyle, TripPace


class TripProfile(Base):
    """AI-generated profile per trip, as specified in the ERD."""
    __tablename__ = "trip_profiles"

    profile_id           = Column(String, primary_key=True)
    trip_id              = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Preference columns (stored as PostgreSQL ENUM for DB-level type safety.
    #     values_callable ensures the enum .value (lowercase) is stored in the DB,
    #     matching what the Python service layer sends.) ---
    budget_level         = Column(SAEnum(BudgetLevel, name="budget_level", values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    travel_style         = Column(SAEnum(TravelStyle, name="travel_style", values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    pace                 = Column(SAEnum(TripPace, name="trip_pace", values_callable=lambda obj: [e.value for e in obj]), nullable=True)

    # --- Preference Lists ---
    interests            = Column(JSON, nullable=True)     # List[str]
    food_preferences     = Column(JSON, nullable=True)     # List[str]
    accommodation_preferences = Column(JSON, nullable=True)  # List[str]

    # --- Timestamps ---
    generated_at         = Column(DateTime, default=func.now())
    updated_at           = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="trip_profiles")
