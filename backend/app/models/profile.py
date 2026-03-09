from sqlalchemy import Column, String, Integer, JSON, DateTime, Boolean,ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id          = Column(String, ForeignKey("users.user_id"), primary_key=True)

    age              = Column(Integer)
    sex              = Column(String)
    travel_companion = Column(String)
    location         = Column(String)

    # Sliders
    adventure_relaxing  = Column(Integer)
    nature_culture      = Column(Integer)
    popular_local       = Column(Integer)
    budget_level        = Column(Integer)
    early_night         = Column(Integer)
    independent_social  = Column(Integer)

    # Multi-select
    accommodation_styles = Column(JSON)
    dining_preferences   = Column(JSON)
    interests            = Column(JSON)
    traveler_types       = Column(JSON)

    # Persona
    persona_name        = Column(String, nullable=True)
    persona_bio         = Column(String, nullable=True)
    suggested_questions = Column(JSON, nullable=True)

    # Flag
    quiz_completed = Column(Boolean, default=False)
    created_at     = Column(DateTime, server_default=func.now())
    updated_at     = Column(DateTime, onupdate=func.now())