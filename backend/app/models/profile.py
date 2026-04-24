# app/models/profile.py

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, ForeignKey, JSON, Boolean 
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    profile_id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(String, ForeignKey("users.user_id"), nullable=False, unique=True, index=True)

    # ── Basic Info ───────────────────────────────────────────────────────
    age                 = Column(Integer, nullable=True)
    sex                 = Column(String, nullable=True)
    travel_companion    = Column(String, nullable=True)
    location            = Column(String, nullable=True)

    # ── Sliders (0–100) ─────────────────────────────────────────────────
    adventure_relaxing  = Column(Integer, nullable=True)
    nature_culture      = Column(Integer, nullable=True)
    popular_local       = Column(Integer, nullable=True)
    budget_level        = Column(Integer, nullable=True)
    early_night         = Column(Integer, nullable=True)
    independent_social  = Column(Integer, nullable=True)

    # ── Multi-select (JSON arrays) ───────────────────────────────────────
    accommodation_styles = Column(JSON, nullable=True)    # ["hotel", "hostel", "airbnb"]
    dining_preferences   = Column(JSON, nullable=True)    # ["street_food", "fine_dining"]
    interests            = Column(JSON, nullable=True)    # ["history", "food", "beaches"]
    traveler_types       = Column(JSON, nullable=True)    # ["solo", "backpacker"]

    # ── AI-Generated Persona ─────────────────────────────────────────────
    persona_name         = Column(String, nullable=True)
    persona_bio          = Column(Text, nullable=True)
    suggested_questions  = Column(JSON, nullable=True)    # ["What's the best...", ...]

    created_at           = Column(DateTime, default=func.now())
    updated_at           = Column(DateTime, default=func.now(), onupdate=func.now())
    
    quiz_completed = Column(Boolean, default=False, nullable=False)