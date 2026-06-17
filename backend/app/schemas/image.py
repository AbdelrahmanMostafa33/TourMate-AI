"""UploadedImage and ImageFeature schemas."""

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


# ─── UploadedImage ───────────────────────────────────────────────────────────

class UploadedImageCreate(BaseModel):
    """Create schema for UploadedImage – aligns with model fields."""
    file_name:          str
    file_path:          str
    file_size:          Optional[int]  = None
    mime_type:          Optional[str]  = None
    features:           Optional[List[ImageFeatureCreate]] = []


class UploadedImageResponse(BaseModel):
    """Response schema for UploadedImage – aligns with model fields."""
    image_id:           str
    trip_id:            str
    user_id:            str
    file_name:          str
    file_path:          str
    file_size:          Optional[int]
    mime_type:          Optional[str]
    upload_date:        datetime
    processing_status:  ProcessingStatus
    features:           List[ImageFeatureResponse] = []

    class Config:
        from_attributes = True
