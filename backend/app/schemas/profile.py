# app/schemas/profile.py

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from app.models.enums import BudgetLevel, TravelStyle, TripPace


class TripProfileCreate(BaseModel):
    """Request schema for creating/updating a trip profile – aligns with ERD trip_profiles."""
    budget_level: Optional[BudgetLevel] = None
    travel_style: Optional[TravelStyle] = None
    pace: Optional[TripPace] = None
    interests: List[str] = []
    food_preferences: List[str] = []
    accommodation_preferences: List[str] = []


class TripProfileResponse(BaseModel):
    """Response schema for trip profile – aligns with TripProfile model fields."""
    profile_id: str
    trip_id: str
    budget_level: Optional[BudgetLevel] = None
    travel_style: Optional[TravelStyle] = None
    pace: Optional[TripPace] = None
    interests: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None
    accommodation_preferences: Optional[List[str]] = None
    generated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    """Response schema for user profile data (user + trip profile combined)."""
    # ── User Info ──
    user_id: str
    full_name: Optional[str] = None
    email: str
    phone_number: Optional[str] = None
    home_city: Optional[str] = None
    registration_date: Optional[datetime] = None
    traveler_persona: Optional[str] = None

    # ── Trip Profile (if exists for current trip) ──
    trip_profile: Optional[TripProfileResponse] = None

    class Config:
        from_attributes = True