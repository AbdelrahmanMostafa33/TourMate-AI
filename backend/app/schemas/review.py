"""Review schema."""

from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

from app.models.enums import ReviewSource


class ReviewCreate(BaseModel):
    """Create schema for Review – aligns with model fields."""
    place_id:    str
    rating:      int
    source:      ReviewSource = ReviewSource.user
    title:       Optional[str] = None
    comment:     Optional[str] = None
    visit_date:  Optional[date] = None


class ReviewResponse(BaseModel):
    """Response schema for Review – aligns with model fields."""
    review_id:     str
    place_id:      str
    user_id:       str
    rating:        int
    source:        ReviewSource
    title:         Optional[str]   = None
    comment:       Optional[str]   = None
    visit_date:    Optional[date]  = None
    review_date:   datetime
    helpful_count: int
    is_verified:   bool

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    """Summary schema for Review."""
    review_id:   str
    user_id:     str
    rating:      int
    source:      ReviewSource
    title:       Optional[str]  = None
    comment:     Optional[str]  = None
    review_date: datetime

    class Config:
        from_attributes = True
