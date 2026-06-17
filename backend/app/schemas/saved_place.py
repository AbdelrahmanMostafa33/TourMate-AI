"""SavedPlace schema."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SavedPlaceCreate(BaseModel):
    """Create schema for SavedPlace – aligns with model fields."""
    place_id: str
    note:     Optional[str] = None


class SavedPlaceResponse(BaseModel):
    """Response schema for SavedPlace – aligns with model fields."""
    saved_place_id: str
    user_id:        str
    place_id:       str
    saved_at:       datetime
    note:           Optional[str] = None

    class Config:
        from_attributes = True
