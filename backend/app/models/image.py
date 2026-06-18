"""Image and ImageFeature models."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, JSON,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ProcessingStatus


# ─── Image ───────────────────────────────────────────────────────────────────

class Image(Base):
    __tablename__ = "images"

    image_id          = Column(String, primary_key=True)
    trip_id           = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id           = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    file_name         = Column(String, nullable=False)
    file_url          = Column(String, nullable=True)
    uploaded_at       = Column(DateTime, default=func.now())
    analysis_status   = Column(
        SAEnum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.pending,
        nullable=False,
    )

    # Relationships
    trip     = relationship("Trip", back_populates="images")
    user     = relationship("User", back_populates="images")
    features = relationship("ImageFeature", back_populates="image", cascade="all, delete-orphan")


# ─── ImageFeature ────────────────────────────────────────────────────────────

class ImageFeature(Base):
    __tablename__ = "image_features"

    feature_id   = Column(String, primary_key=True)
    image_id     = Column(String, ForeignKey("images.image_id", ondelete="CASCADE"), nullable=False, index=True)
    feature_type = Column(String, nullable=False)              # e.g. "landmark", "food", "style"
    feature_name = Column(String, nullable=True)
    confidence   = Column(Float, nullable=True)                # 0.0 – 1.0
    value        = Column(String, nullable=True)               # extracted value
    metadata     = Column(JSON, nullable=True)                 # extra info

    # Relationships
    image = relationship("Image", back_populates="features")
