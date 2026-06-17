"""SavedPlace model."""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SavedPlace(Base):
    __tablename__ = "saved_places"

    saved_place_id = Column(String, primary_key=True)
    user_id        = Column(String, ForeignKey("users.user_id"), nullable=False, index=True)
    place_id       = Column(String, ForeignKey("places.place_id"), nullable=False, index=True)
    saved_at       = Column(DateTime, default=func.now())
    note           = Column(Text, nullable=True)

    # Relationships
    user  = relationship("User", back_populates="saved_places")
    place = relationship("Place", back_populates="saved_places")
