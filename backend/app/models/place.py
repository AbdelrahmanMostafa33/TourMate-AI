"""Place, HotelDetails, RestaurantDetails, AttractionDetails models.

Inlined Location and OpeningHours into Place and detail classes per class diagram.
"""

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PlaceCategory, AccommodationType



# ─── Place ───────────────────────────────────────────────────────────────────

class Place(Base):
    __tablename__ = "places"

    place_id          = Column(String, primary_key=True)
    name              = Column(String, nullable=False)
    description       = Column(Text, nullable=True)
    category          = Column(
        SAEnum(PlaceCategory, name="place_category"),
        nullable=False,
    )
    rating            = Column(Float, nullable=True)
    review_count      = Column(Integer, default=0)
    popularity_score  = Column(Float, nullable=True)
    phone             = Column(String, nullable=True)
    website           = Column(String, nullable=True)
    price_level       = Column(Integer, nullable=True)
    maps_link         = Column(String, nullable=True)
    address           = Column(String, nullable=True)
    city              = Column(String, nullable=True)
    country           = Column(String, nullable=True)
    lat               = Column(Float, nullable=True)
    lng               = Column(Float, nullable=True)
    timezone          = Column(String, nullable=True)
    opening_hours     = Column(JSON, nullable=True)          # Map<DayOfWeek, String>
    photo_urls        = Column(JSON, nullable=True)          # List[str]
    embedding         = Column(JSON, nullable=True)          # vector stored as JSON list (will migrate to pgvector vector(768) later)

    # Relationships
    reviews          = relationship("Review",         back_populates="place", cascade="all, delete-orphan")
    saved_places     = relationship("SavedPlace",     back_populates="place", cascade="all, delete-orphan")
    hotel_details    = relationship("HotelDetails",    back_populates="place", uselist=False, cascade="all, delete-orphan")
    restaurant_details = relationship("RestaurantDetails", back_populates="place", uselist=False, cascade="all, delete-orphan")
    attraction_details = relationship("AttractionDetails", back_populates="place", uselist=False, cascade="all, delete-orphan")




# ─── HotelDetails (composition 0..1 from Place) ─────────────────────────────

class HotelDetails(Base):
    __tablename__ = "hotel_details"

    place_id          = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    star_class        = Column(Integer, nullable=True)
    nightly_rate      = Column(Float, nullable=True)
    amenities          = Column(JSON, nullable=True)          # List[str]
    booking_platforms   = Column(JSON, nullable=True)         # List[str]
    accommodation_type = Column(
        SAEnum(AccommodationType, name="accommodation_type"),
        nullable=True,
    )

    # Relationships
    place = relationship("Place", back_populates="hotel_details")


# ─── RestaurantDetails (composition 0..1 from Place) ────────────────────────

class RestaurantDetails(Base):
    __tablename__ = "restaurant_details"

    place_id            = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    cuisine_type        = Column(String, nullable=True)
    avg_cost_per_person = Column(Float, nullable=True)

    # Relationships
    place = relationship("Place", back_populates="restaurant_details")


# ─── AttractionDetails (composition 0..1 from Place) ────────────────────────

class AttractionDetails(Base):
    __tablename__ = "attraction_details"

    place_id      = Column(String, ForeignKey("places.place_id", ondelete="CASCADE"), primary_key=True)
    subcategory   = Column(String, nullable=True)
    entry_fee     = Column(Float, nullable=True)

    # Relationships
    place = relationship("Place", back_populates="attraction_details")