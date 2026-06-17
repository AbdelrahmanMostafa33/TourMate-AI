"""Recommendation schema."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RecommendationCreate(BaseModel):
    """Create schema for Recommendation – aligns with model fields."""
    place_id:    str
    score:       float
    reason:      Optional[str]     = None
    expires_at:  Optional[datetime] = None


class RecommendationResponse(BaseModel):
    """Response schema for Recommendation – aligns with model fields."""
    recommendation_id: str
    user_id:           str
    place_id:          str
    score:             float
    reason:            Optional[str]     = None
    generated_at:      datetime
    expires_at:        Optional[datetime] = None
    was_clicked:       bool
    was_booked:        bool

    class Config:
        from_attributes = True
