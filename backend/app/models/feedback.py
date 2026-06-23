"""Feedback model."""

from sqlalchemy import (
    Column, String, Integer, Text, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import FeedbackType


class Feedback(Base):
    __tablename__ = "feedback"

    feedback_id   = Column(String, primary_key=True)
    user_id       = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    trip_id       = Column(String, ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=True, index=True)
    feedback_type = Column(SAEnum(FeedbackType, name="feedback_type"), nullable=False)
    rating        = Column(Integer, nullable=True)            # 1-5 when feedback_type == rating
    comment       = Column(Text, nullable=True)
    submitted_at  = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User")
    trip = relationship("Trip", back_populates="feedbacks")
