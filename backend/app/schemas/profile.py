# app/schemas/profile.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.models.enums import (
    PaceStyle, SpendingStyle, ExperienceLean,
    DayRhythm, AttractionPreference, SocialStyle,
)


class QuizSubmitRequest(BaseModel):
    """Request schema for quiz submission – aligns with BehavioralProfile model fields."""
    pace_style:            PaceStyle
    spending_style:        SpendingStyle
    experience_lean:       ExperienceLean
    day_rhythm:            DayRhythm
    attraction_preference: AttractionPreference
    social_style:          SocialStyle

    interests:                 List[str] = []
    dining_preferences:        List[str] = []
    accommodation_preferences: List[str] = []
    custom_interests:          List[str] = []


class PersonaResponse(BaseModel):
    """Response schema for persona data – aligns with BehavioralProfile model fields."""
    persona_title:   str
    persona_summary: str
    interests:       List[str]
    quiz_completed:  bool

    class Config:
        from_attributes = True


class FullProfileResponse(BaseModel):
    """Full user profile response – aligns with User + BehavioralProfile models."""
    # ── User Info (from User model) ──
    user_id: str
    full_name: Optional[str] = None
    email: str
    phone_number: Optional[str] = None
    home_city: Optional[str] = None
    registration_date: Optional[datetime] = None

    # ── Quiz Status ──
    quiz_completed: bool = False

    # ── Persona (only if quiz completed) ──
    persona_title: Optional[str] = None
    persona_summary: Optional[str] = None

    # ── Behavioral Styles ──
    pace_style: Optional[PaceStyle] = None
    spending_style: Optional[SpendingStyle] = None
    experience_lean: Optional[ExperienceLean] = None
    day_rhythm: Optional[DayRhythm] = None
    attraction_preference: Optional[AttractionPreference] = None
    social_style: Optional[SocialStyle] = None

    # ── Lists ──
    interests: Optional[List[str]] = None
    dining_preferences: Optional[List[str]] = None
    accommodation_preferences: Optional[List[str]] = None
    custom_interests: Optional[List[str]] = None

    # ── Timestamps ──
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True