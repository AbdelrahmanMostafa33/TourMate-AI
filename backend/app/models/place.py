"""Place, Hotel, Restaurant, Attraction, Location, OpeningHours models."""

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime, Date,
    ForeignKey, JSON, Map, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import TravelDimension


# ─── Place ───────────────────────────────────────────────────────────────────

class Place(Base):
    __tablename__ = "places"

    place_id          = Column(String, primary_key=True)
    name              = Column(String, nullable=False)
    description       = Column(Text, nullable=True)
    category          = Column(String, nullable=False)       # hotel / restaurant / attraction
    subcategory       = Column(String, nullable=True)
    subtype           = Column(String, nullable=True)
    rating            = Column(Float, nullable=True)
    review_count      = Column(Integer, default=0)
    popularity_score  = Column(Float, nullable=True)
    phone_number      = Column(String, nullable=True)
    website           = Column(String, nullable=True)
    maps_link         = Column(String, nullable=True)
    place_profile     = Column(JSON, nullable=True)          # {TravelDimension: Double}
    embedding         = Column(JSON, nullable=True)          # vector stored as JSON list
    photo_urls        = Column(JSON, nullable=True)          # List[str]
    primary_photo_url = Column(String, nullable=True)
    created_at        = Column(DateTime, default=func.now())

    # Relationships
    location       = relationship("Location",       back_populates="place", uselist=False, cascade="all, delete-orphan")
    opening_hours  = relationship("OpeningHours",   back_populates="place", uselist=False, cascade="all, delete-orphan")
    reviews        = relationship("Review",         back_populates="place", cascade="all, delete-orphan")
    saved_places   = relationship("SavedPlace",     back_populates="place")
    recommendations = relationship("Recommendation", back_populates="place")

    # Inheritance discriminator
    __mapper_args__ = {
        "polymorphic_on": "category",
        "polymorphic_identity": "place",
    }


# ─── Hotel (extends Place) ──────────────────────────────────────────────────

class Hotel(Place):
    __tablename__ = "hotels"

    place_id          = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    star_class        = Column(Integer, nullable=True)
    nightly_rate      = Column(Float, nullable=True)
    amenities         = Column(JSON, nullable=True)          # List[str]
    booking_platforms  = Column(JSON, nullable=True)         # List[str]

    __mapper_args__ = {"polymorphic_identity": "hotel"}


# ─── Restaurant (extends Place) ─────────────────────────────────────────────

class Restaurant(Place):
    __tablename__ = "restaurants"

    place_id          = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    cuisine_type      = Column(String, nullable=True)
    avg_cost_per_person = Column(Float, nullable=True)
    reservation_link  = Column(String, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "restaurant"}


# ─── Attraction (extends Place) ─────────────────────────────────────────────

class Attraction(Place):
    __tablename__ = "attractions"

    place_id          = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    attraction_type   = Column(String, nullable=True)
    tags              = Column(JSON, nullable=True)          # List[str]
    entry_fee         = Column(Float, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "attraction"}


# ─── Location ────────────────────────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"

    location_id = Column(String, primary_key=True)
    place_id    = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    address     = Column(String, nullable=True)
    city        = Column(String, nullable=True)
    state       = Column(String, nullable=True)
    country     = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    latitude    = Column(Float, nullable=False)
    longitude   = Column(Float, nullable=False)
    timezone    = Column(String, nullable=True)

    # Relationships
    place = relationship("Place", back_populates="location")


# ─── OpeningHours ────────────────────────────────────────────────────────────

class OpeningHours(Base):
    __tablename__ = "opening_hours"

    hours_id    = Column(String, primary_key=True)
    place_id    = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    monday      = Column(String, nullable=True)
    tuesday     = Column(String, nullable=True)
    wednesday   = Column(String, nullable=True)
    thursday    = Column(String, nullable=True)
    friday      = Column(String, nullable=True)
    saturday    = Column(String, nullable=True)
    sunday      = Column(String, nullable=True)
    special_days = Column(JSON, nullable=True)               # {date_str: hours_str}
    timezone    = Column(String, nullable=True)

    # Relationships
    place = relationship("Place", back_populates="opening_hours")
