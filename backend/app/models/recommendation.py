"""Recommendation model."""

from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import RecommendationType, RecommendationStatus


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id   = Column(String, primary_key=True)
    trip_id             = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    place_id            = Column(String, ForeignKey("places.place_id"), nullable=False, index=True)
    score               = Column(Float, nullable=False)           # 0.0 – 1.0 match score
    reason              = Column(Text, nullable=True)             # AI-generated reason
    recommendation_type = Column(
        SAEnum(RecommendationType, name="recommendation_type"),
        nullable=True,
    )
    status              = Column(
        SAEnum(RecommendationStatus, name="recommendation_status"),
        default=RecommendationStatus.pending,
        nullable=False,
    )
    created_at          = Column(DateTime, default=func.now())

    # Relationships
    trip  = relationship("Trip", back_populates="recommendations")
    place = relationship("Place", back_populates="recommendations")
