"""Feedback schema."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.enums import FeedbackType


class FeedbackCreate(BaseModel):
    """Create schema for Feedback – aligns with model fields."""
    item_type:     str
    item_id:       str
    feedback_type: FeedbackType
    rating:        Optional[int]  = None
    comment:       Optional[str]  = None


class FeedbackResponse(BaseModel):
    """Response schema for Feedback – aligns with model fields."""
    feedback_id:   str
    user_id:       str
    profile_id:    Optional[str]
    item_type:     str
    item_id:       str
    feedback_type: FeedbackType
    rating:        Optional[int]
    comment:       Optional[str]
    submitted_at:  datetime

    class Config:
        from_attributes = True
