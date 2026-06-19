from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    """Create schema for User registration – aligns with model fields."""
    full_name:    str
    phone_number: Optional[str] = None


class UserResponse(BaseModel):
    """Response schema for User – aligns with ERD model fields."""
    user_id:           str
    full_name:         Optional[str] = None
    email:             str
    phone_number:      Optional[str] = None
    registration_date: Optional[datetime] = None
    home_city:         Optional[str] = None
    traveler_persona:  Optional[str] = None
    updated_at:        Optional[datetime] = None

    class Config:
        from_attributes = True