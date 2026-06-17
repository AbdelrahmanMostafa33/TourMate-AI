"""Review model."""

from sqlalchemy import (
    Column, String, Integer, Text, Date, DateTime, Boolean,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ReviewSource


class Review(Base):
    __tablename__ = "reviews"

    review_id     = Column(String, primary_key=True)
    place_id      = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id       = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    rating        = Column(Integer, nullable=False)          # 1-5
    source        = Column(SAEnum(ReviewSource, name="review_source"), nullable=False, default=ReviewSource.user)
    title         = Column(String, nullable=True)
    comment       = Column(Text, nullable=True)
    visit_date    = Column(Date, nullable=True)
    review_date   = Column(DateTime, default=func.now())
    helpful_count = Column(Integer, default=0)
    is_verified   = Column(Boolean, default=False)

    # Relationships
    place = relationship("Place", back_populates="reviews")
    user  = relationship("User", back_populates="reviews")
