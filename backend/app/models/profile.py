# app/models/profile.py

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TravelerProfile(Base):
    __tablename__ = "traveler_profiles"

    profile_id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(String, ForeignKey("users.user_id"), nullable=False, unique=True, index=True)

    # --- Dimension Scores (keyed by TravelDimension enum) ---
    # Stored as JSON: {"ADVENTURE": 0.8, "CULTURE": 0.6, ...}
    dimension_scores    = Column(JSON, nullable=True)

    # --- Interests & Dietary ---
    interests           = Column(JSON, nullable=True)           # List[str]
    dietary_restrictions = Column(JSON, nullable=True)          # List[str]

    # --- Legacy quiz fields (kept for backwards-compat) ---
    age                 = Column(Integer, nullable=True)
    sex                 = Column(String, nullable=True)
    travel_companion    = Column(String, nullable=True)
    location            = Column(String, nullable=True)

    # --- Sliders (0-100) - kept for existing quiz UI ---
    adventure_relaxing  = Column(Integer, nullable=True)
    nature_culture      = Column(Integer, nullable=True)
    popular_local       = Column(Integer, nullable=True)
    budget_level        = Column(Integer, nullable=True)
    early_night         = Column(Integer, nullable=True)
    independent_social  = Column(Integer, nullable=True)

    # --- Multi-select ---
    accommodation_styles = Column(JSON, nullable=True)
    dining_preferences   = Column(JSON, nullable=True)
    traveler_types       = Column(JSON, nullable=True)

    # --- AI-Generated Persona ---
    persona_name         = Column(String, nullable=True)
    persona_bio          = Column(Text, nullable=True)
    suggested_questions  = Column(JSON, nullable=True)

    created_at           = Column(DateTime, default=func.now())
    last_updated         = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user      = relationship("User",       back_populates="profile")
    feedbacks = relationship("Feedback",   back_populates="profile")
