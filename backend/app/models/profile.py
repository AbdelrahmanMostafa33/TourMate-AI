# app/models/profile.py

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON, Boolean, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import (
    PaceStyle, SpendingStyle, ExperienceLean,
    DayRhythm, AttractionPreference, SocialStyle,
)


class BehavioralProfile(Base):
    __tablename__ = "behavioral_profiles"

    profile_id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id               = Column(String, ForeignKey("users.user_id"), nullable=False, unique=True, index=True)

    # --- Enum-based dimension styles ---
    pace_style            = Column(String, nullable=True)            # PaceStyle
    spending_style        = Column(String, nullable=True)            # SpendingStyle
    experience_lean       = Column(String, nullable=True)            # ExperienceLean
    day_rhythm            = Column(String, nullable=True)            # DayRhythm
    attraction_preference = Column(String, nullable=True)            # AttractionPreference
    social_style          = Column(String, nullable=True)            # SocialStyle

    # --- Lists ---
    interests                 = Column(JSON, nullable=True)           # List[InterestTag]
    dining_preferences        = Column(JSON, nullable=True)           # List[DiningType]
    accommodation_preferences = Column(JSON, nullable=True)           # List[AccommodationType]
    custom_interests          = Column(JSON, nullable=True)           # List[str] from "Add your own"

    # --- AI-Generated Persona ---
    persona_title    = Column(String, nullable=True)                 # e.g. "Adventurous Independent Nightowl"
    persona_summary  = Column(Text, nullable=True)                   # AI-generated blurb

    # --- Quiz status ---
    quiz_completed   = Column(Boolean, default=False)
    completed_at     = Column(DateTime, nullable=True)
    updated_at       = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user      = relationship("User",       back_populates="profile")
