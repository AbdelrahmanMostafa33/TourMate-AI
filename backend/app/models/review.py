"""Review model."""

from sqlalchemy import (
    Column, String, Integer, Text, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Review(Base):
    __tablename__ = "reviews"

    review_id     = Column(String, primary_key=True)
    user_id       = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    place_id      = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False, index=True)
    rating        = Column(Integer, nullable=False)          # 1-5
    comment       = Column(Text, nullable=True)
    review_date   = Column(DateTime, default=func.now())
    likes_count   = Column(Integer, default=0)

    # Relationships
    place = relationship("Place", back_populates="reviews")
    user  = relationship("User", back_populates="reviews")
    likes = relationship("ReviewLike", back_populates="review", cascade="all, delete-orphan")


class ReviewLike(Base):
    """Tracks which user liked which review."""
    __tablename__ = "review_likes"

    user_id     = Column(String, ForeignKey("users.user_id"), nullable=False, primary_key=True)
    review_id   = Column(String, ForeignKey("reviews.review_id", ondelete="CASCADE"), nullable=False, primary_key=True)

    # Relationships
    user   = relationship("User",   back_populates="review_likes")
    review = relationship("Review", back_populates="likes")
