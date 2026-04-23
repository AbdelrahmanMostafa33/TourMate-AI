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