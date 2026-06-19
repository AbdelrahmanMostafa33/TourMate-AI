# app/models/profile.py

from sqlalchemy import (
    Column, String, Float, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TripProfile(Base):
    """AI-generated profile per trip, as specified in the ERD."""
    __tablename__ = "trip_profiles"

    profile_id           = Column(String, primary_key=True)
    trip_id              = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)

    # --- Preference ENUMs ---
    budget_level         = Column(String, nullable=True)   # BudgetLevel
    travel_style         = Column(String, nullable=True)   # TravelStyle
    pace                 = Column(String, nullable=True)   # TripPace

    # --- Preference Lists ---
    interests            = Column(JSON, nullable=True)     # List[str]
    food_preferences     = Column(JSON, nullable=True)     # List[str]
    accommodation_preferences = Column(JSON, nullable=True)  # List[str]

    # --- AI-generated Scoring Fields (0.0 - 1.0) ---
    luxury_score         = Column(Float, nullable=True)
    culture_score        = Column(Float, nullable=True)
    adventure_score      = Column(Float, nullable=True)
    shopping_score       = Column(Float, nullable=True)
    family_score         = Column(Float, nullable=True)
    confidence           = Column(Float, nullable=True)

    # --- Timestamps ---
    generated_at         = Column(DateTime, default=func.now())
    updated_at           = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trip = relationship("Trip", back_populates="trip_profiles")
