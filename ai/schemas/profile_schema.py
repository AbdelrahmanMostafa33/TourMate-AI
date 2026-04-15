# ai/schemas/profile_schema.py

from pydantic import BaseModel
from typing import Optional, List


class BehavioralProfileSchema(BaseModel):
    """
    Pydantic schema that validates the profile payload received from the backend.

    This mirrors the BehavioralProfile TypedDict in graph/state.py but uses
    Pydantic for automatic validation, default handling, and serialization.
    """

    user_id: str

    # Demographics
    age: Optional[int] = None
    sex: Optional[str] = None
    travel_companion: Optional[str] = None
    location: Optional[str] = None

    # Slider preferences (0–100)
    adventure_relaxing: Optional[int] = None
    nature_culture: Optional[int] = None
    popular_local: Optional[int] = None
    budget_level: Optional[int] = None
    early_night: Optional[int] = None
    independent_social: Optional[int] = None

    # Multi-select fields
    accommodation_styles: List[str] = []
    dining_preferences: List[str] = []
    interests: List[str] = []
    traveler_types: List[str] = []

    # AI-generated persona
    persona_name: Optional[str] = None
    persona_bio: Optional[str] = None
    suggested_questions: Optional[List[str]] = None

    # Completion flag
    quiz_completed: bool = False