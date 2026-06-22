"""Review schema."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    """Create schema for Review – aligns with model fields."""
    place_id:  str
    rating:    int = Field(ge=1, le=5)
    comment:   Optional[str] = None


class ReviewUpdate(BaseModel):
    """Update schema for Review – all fields optional."""
    rating:   Optional[int] = Field(default=None, ge=1, le=5)
    comment:  Optional[str] = None


class ReviewResponse(BaseModel):
    """Response schema for Review – aligns with model fields."""
    review_id:    str
    user_id:      str
    place_id:     str
    rating:       int
    comment:      Optional[str]  = None
    review_date:  datetime
    likes_count:  int

    class Config:
        from_attributes = True


class ReviewSummary(BaseModel):
    """Summary schema for Review."""
    review_id:   str
    user_id:     str
    rating:      int
    comment:     Optional[str]  = None
    review_date: datetime

    class Config:
        from_attributes = True
