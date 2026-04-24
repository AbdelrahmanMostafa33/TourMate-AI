# app/schemas/profile.py

from pydantic import BaseModel, Field
from typing import List, Optional

class QuizSubmitRequest(BaseModel):
    age: int
    sex: str
    travel_companion: str
    location: str

    adventure_relaxing: int = Field(ge=0, le=100)
    nature_culture: int     = Field(ge=0, le=100)
    popular_local: int      = Field(ge=0, le=100)
    budget_level: int       = Field(ge=0, le=100)
    early_night: int        = Field(ge=0, le=100)
    independent_social: int = Field(ge=0, le=100)

    accommodation_styles: List[str]
    dining_preferences: List[str]
    interests: List[str]
    traveler_types: List[str]

class PersonaResponse(BaseModel):
    persona_name: str
    persona_bio: str
    interests: List[str]
    suggested_questions: List[str]
    quiz_completed: bool

    class Config:
        from_attributes = True


# ✅ NEW: Full user profile response
class FullProfileResponse(BaseModel):
    # ── User Info ──
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool

    # ── Quiz Status ──
    quiz_completed: bool

    # ── Persona (only if quiz completed) ──
    persona_name: Optional[str] = None
    persona_bio: Optional[str] = None
    suggested_questions: Optional[List[str]] = None

    # ── Basic Info ──
    age: Optional[int] = None
    sex: Optional[str] = None
    travel_companion: Optional[str] = None
    location: Optional[str] = None

    # ── Sliders ──
    adventure_relaxing: Optional[int] = None
    nature_culture: Optional[int] = None
    popular_local: Optional[int] = None
    budget_level: Optional[int] = None
    early_night: Optional[int] = None
    independent_social: Optional[int] = None

    # ── Multi-select ──
    accommodation_styles: Optional[List[str]] = None
    dining_preferences: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    traveler_types: Optional[List[str]] = None

    class Config:
        from_attributes = True