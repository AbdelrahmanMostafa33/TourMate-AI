"""Image and ImageFeature schemas."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

from app.models.enums import ProcessingStatus


# ─── ImageFeature ────────────────────────────────────────────────────────────

class ImageFeatureCreate(BaseModel):
    """Create schema for ImageFeature – aligns with model fields."""
    feature_type: str
    feature_name: Optional[str]   = None
    confidence:   Optional[float] = None
    value:        Optional[str]   = None
    metadata:     Optional[Dict]  = None


class ImageFeatureResponse(BaseModel):
    """Response schema for ImageFeature – aligns with model fields."""
    feature_id:   str
    image_id:     str
    feature_type: str
    feature_name: Optional[str]   = None
    confidence:   Optional[float] = None
    value:        Optional[str]   = None
    metadata:     Optional[Dict]  = None

    class Config:
        from_attributes = True


# ─── Image ───────────────────────────────────────────────────────────────────

class ImageCreate(BaseModel):
    """Create schema for Image – aligns with model fields."""
    file_name:    str
    file_url:     Optional[str]   = None
    features:     Optional[List[ImageFeatureCreate]] = []


class ImageResponse(BaseModel):
    """Response schema for Image – aligns with model fields."""
    image_id:         str
    trip_id:          str
    user_id:          str
    file_name:        str
    file_url:         Optional[str]
    uploaded_at:      datetime
    analysis_status:  ProcessingStatus
    features:         List[ImageFeatureResponse] = []

    class Config:
        from_attributes = True
