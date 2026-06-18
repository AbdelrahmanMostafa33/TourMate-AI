"""Recommendation schema."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.enums import RecommendationType, RecommendationStatus


class RecommendationCreate(BaseModel):
    """Create schema for Recommendation – aligns with model fields."""
    place_id:            str
    score:               float
    reason:              Optional[str]              = None
    recommendation_type: Optional[RecommendationType] = None
    status:              Optional[RecommendationStatus] = RecommendationStatus.pending


class RecommendationResponse(BaseModel):
    """Response schema for Recommendation – aligns with model fields."""
    recommendation_id:   str
    trip_id:             str
    place_id:            str
    score:               float
    reason:              Optional[str]              = None
    recommendation_type: Optional[RecommendationType] = None
    status:              RecommendationStatus
    created_at:          datetime

    class Config:
        from_attributes = True
