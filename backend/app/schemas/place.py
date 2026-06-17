"""Place, Hotel, Restaurant, Attraction, Location, OpeningHours schemas."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


# ─── Location ────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    """Create schema for Location – aligns with model fields."""
    address:     Optional[str]  = None
    city:        Optional[str]  = None
    state:       Optional[str]  = None
    country:     Optional[str]  = None
    postal_code: Optional[str]  = None
    latitude:    float
    longitude:   float
    timezone:    Optional[str]  = None


class LocationResponse(BaseModel):
    """Response schema for Location – aligns with model fields."""
    location_id: str
    place_id:    str
    address:     Optional[str]  = None
    city:        Optional[str]  = None
    state:       Optional[str]  = None
    country:     Optional[str]  = None
    postal_code: Optional[str]  = None
    latitude:    float
    longitude:   float
    timezone:    Optional[str]  = None

    class Config:
        from_attributes = True


# ─── OpeningHours ────────────────────────────────────────────────────────────

class OpeningHoursCreate(BaseModel):
    """Create schema for OpeningHours – aligns with model fields."""
    monday:       Optional[str] = None
    tuesday:      Optional[str] = None
    wednesday:    Optional[str] = None
    thursday:     Optional[str] = None
    friday:       Optional[str] = None
    saturday:     Optional[str] = None
    sunday:       Optional[str] = None
    special_days: Optional[Dict[str, str]] = None   # {date_str: hours_str}
    timezone:     Optional[str] = None


class OpeningHoursResponse(BaseModel):
    """Response schema for OpeningHours – aligns with model fields."""
    hours_id:     str
    place_id:     str
    monday:       Optional[str] = None
    tuesday:      Optional[str] = None
    wednesday:    Optional[str] = None
    thursday:     Optional[str] = None
    friday:       Optional[str] = None
    saturday:     Optional[str] = None
    sunday:       Optional[str] = None
    special_days: Optional[Dict[str, str]] = None
    timezone:     Optional[str] = None

    class Config:
        from_attributes = True


# ─── Place (base) ────────────────────────────────────────────────────────────

class PlaceCreate(BaseModel):
    """Create schema for Place – aligns with model fields."""
    name:              str
    description:       Optional[str]   = None
    category:          str
    subcategory:       Optional[str]   = None
    subtype:           Optional[str]   = None
    rating:            Optional[float] = None
    review_count:      int             = 0
    popularity_score:  Optional[float] = None
    phone_number:      Optional[str]   = None
    website:           Optional[str]   = None
    maps_link:         Optional[str]   = None
    place_profile:     Optional[Dict[str, float]] = None   # {TravelDimension: Double}
    photo_urls:        Optional[List[str]] = None
    primary_photo_url: Optional[str]   = None
    location:          Optional[LocationCreate]    = None
    opening_hours:     Optional[OpeningHoursCreate] = None


class PlaceResponse(BaseModel):
    """Response schema for Place – aligns with model fields."""
    place_id:          str
    name:              str
    description:       Optional[str]   = None
    category:          str
    subcategory:       Optional[str]   = None
    subtype:           Optional[str]   = None
    rating:            Optional[float] = None
    review_count:      int
    popularity_score:  Optional[float] = None
    phone_number:      Optional[str]   = None
    website:           Optional[str]   = None
    maps_link:         Optional[str]   = None
    place_profile:     Optional[Dict[str, float]] = None
    photo_urls:        Optional[List[str]] = None
    primary_photo_url: Optional[str]   = None
    created_at:        Optional[datetime] = None
    location:          Optional[LocationResponse]    = None
    opening_hours:     Optional[OpeningHoursResponse] = None

    class Config:
        from_attributes = True


# ─── Hotel (extends Place) ───────────────────────────────────────────────────

class HotelCreate(BaseModel):
    """Create schema for Hotel – extends Place fields."""
    name:              str
    description:       Optional[str]   = None
    category:          str             = "hotel"
    rating:            Optional[float] = None
    review_count:      int             = 0
    popularity_score:  Optional[float] = None
    phone_number:      Optional[str]   = None
    website:           Optional[str]   = None
    maps_link:         Optional[str]   = None
    photo_urls:        Optional[List[str]] = None
    primary_photo_url: Optional[str]   = None
    location:          Optional[LocationCreate]    = None
    opening_hours:     Optional[OpeningHoursCreate] = None
    # Hotel-specific
    star_class:        Optional[int]          = None
    nightly_rate:      Optional[float]        = None
    amenities:         Optional[List[str]]    = None
    booking_platforms: Optional[List[str]]    = None


class HotelResponse(PlaceResponse):
    """Response schema for Hotel – extends Place with hotel-specific fields."""
    star_class:        Optional[int]          = None
    nightly_rate:      Optional[float]        = None
    amenities:         Optional[List[str]]    = None
    booking_platforms: Optional[List[str]]    = None


# ─── Restaurant (extends Place) ──────────────────────────────────────────────

class RestaurantCreate(BaseModel):
    """Create schema for Restaurant – extends Place fields."""
    name:              str
    description:       Optional[str]   = None
    category:          str             = "restaurant"
    rating:            Optional[float] = None
    review_count:      int             = 0
    popularity_score:  Optional[float] = None
    phone_number:      Optional[str]   = None
    website:           Optional[str]   = None
    maps_link:         Optional[str]   = None
    photo_urls:        Optional[List[str]] = None
    primary_photo_url: Optional[str]   = None
    location:          Optional[LocationCreate]    = None
    opening_hours:     Optional[OpeningHoursCreate] = None
    # Restaurant-specific
    cuisine_type:        Optional[str]   = None
    avg_cost_per_person: Optional[float] = None
    reservation_link:    Optional[str]   = None


class RestaurantResponse(PlaceResponse):
    """Response schema for Restaurant – extends Place with restaurant-specific fields."""
    cuisine_type:        Optional[str]   = None
    avg_cost_per_person: Optional[float] = None
    reservation_link:    Optional[str]   = None


# ─── Attraction (extends Place) ──────────────────────────────────────────────

class AttractionCreate(BaseModel):
    """Create schema for Attraction – extends Place fields."""
    name:              str
    description:       Optional[str]   = None
    category:          str             = "attraction"
    rating:            Optional[float] = None
    review_count:      int             = 0
    popularity_score:  Optional[float] = None
    phone_number:      Optional[str]   = None
    website:           Optional[str]   = None
    maps_link:         Optional[str]   = None
    photo_urls:        Optional[List[str]] = None
    primary_photo_url: Optional[str]   = None
    location:          Optional[LocationCreate]    = None
    opening_hours:     Optional[OpeningHoursCreate] = None
    # Attraction-specific
    attraction_type: Optional[str]       = None
    tags:            Optional[List[str]] = None
    entry_fee:       Optional[float]     = None


class AttractionResponse(PlaceResponse):
    """Response schema for Attraction – extends Place with attraction-specific fields."""
    attraction_type: Optional[str]       = None
    tags:            Optional[List[str]] = None
    entry_fee:       Optional[float]     = None
