"""Recommendation model."""

from sqlalchemy import Column, String, Float, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    recommendation_id = Column(String, primary_key=True)
    user_id           = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    place_id          = Column(String, ForeignKey("places.place_id"), nullable=False, index=True)
    score             = Column(Float, nullable=False)           # 0.0 – 1.0 match score
    reason            = Column(Text, nullable=True)             # AI-generated reason
    generated_at      = Column(DateTime, default=func.now())
    expires_at        = Column(DateTime, nullable=True)
    was_clicked       = Column(Boolean, default=False)
    was_booked        = Column(Boolean, default=False)

    # Relationships
    user  = relationship("User", back_populates="recommendations")
    place = relationship("Place", back_populates="recommendations")
