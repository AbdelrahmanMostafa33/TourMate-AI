# app/models/user.py

from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    user_id           = Column(String, primary_key=True)
    email             = Column(String, unique=True, nullable=False)
    full_name         = Column(String, nullable=True)
    phone_number      = Column(String, nullable=True)
    registration_date = Column(DateTime, default=func.now())
    home_city         = Column(String, nullable=True)
    traveler_persona  = Column(String, nullable=True)
    updated_at        = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    trips            = relationship("Trip",            back_populates="user", cascade="all, delete-orphan")
    conversations    = relationship("Conversation",    back_populates="user", cascade="all, delete-orphan")
    reviews          = relationship("Review",          back_populates="user")
    saved_places     = relationship("SavedPlace",      back_populates="user", cascade="all, delete-orphan")
    review_likes     = relationship("ReviewLike",      back_populates="user", cascade="all, delete-orphan")

