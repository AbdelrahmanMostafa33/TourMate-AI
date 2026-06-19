"""Place, HotelDetails, RestaurantDetails, AttractionDetails schemas."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime


# ─── Place (base) ────────────────────────────────────────────────────────────

class PlaceCreate(BaseModel):
    """Create schema for Place – aligns with model fields."""
    name:              str
    description:       Optional[str]   = None
    category:          str
    rating:            Optional[float] = None
    review_count:      int             = 0
    popularity_score:  Optional[float] = None
    phone:             Optional[str]   = None
    website:           Optional[str]   = None
    price_level:       Optional[int]   = None
    maps_link:         Optional[str]   = None
    address:           Optional[str]   = None
    city:              Optional[str]   = None
    country:           Optional[str]   = None
    lat:               Optional[float] = None
    lng:               Optional[float] = None
    timezone:          Optional[str]   = None
    opening_hours:     Optional[Dict[str, str]] = None
    photo_urls:        Optional[List[str]] = None


class PlaceResponse(BaseModel):
    """Response schema for Place – aligns with model fields."""
    place_id:          str
    name:              str
    description:       Optional[str]   = None
    category:          str
    rating:            Optional[float] = None
    review_count:      int
    popularity_score:  Optional[float] = None
    phone:             Optional[str]   = None
    website:           Optional[str]   = None
    price_level:       Optional[int]   = None
    maps_link:         Optional[str]   = None
    address:           Optional[str]   = None
    city:              Optional[str]   = None
    country:           Optional[str]   = None
    lat:               Optional[float] = None
    lng:               Optional[float] = None
    timezone:          Optional[str]   = None
    opening_hours:     Optional[Dict[str, str]] = None
    photo_urls:        Optional[List[str]] = None

    class Config:
        from_attributes = True


# ─── HotelDetails ────────────────────────────────────────────────────────────

class HotelDetailsCreate(BaseModel):
    """Create schema for HotelDetails."""
    star_class:        Optional[int]          = None
    nightly_rate:      Optional[float]        = None
    amenities:         Optional[List[str]]    = None
    booking_platforms: Optional[List[str]]    = None


class HotelDetailsResponse(BaseModel):
    """Response schema for HotelDetails."""
    place_id:          str
    star_class:        Optional[int]          = None
    nightly_rate:      Optional[float]        = None
    amenities:         Optional[List[str]]    = None
    booking_platforms: Optional[List[str]]    = None

    class Config:
        from_attributes = True


# ─── RestaurantDetails ──────────────────────────────────────────────────────

class RestaurantDetailsCreate(BaseModel):
    """Create schema for RestaurantDetails."""
    cuisine_type:        Optional[str]                = None
    avg_cost_per_person: Optional[float]              = None
    opening_hours:       Optional[Dict[str, str]]     = None  # Map<DayOfWeek, String>


class RestaurantDetailsResponse(BaseModel):
    """Response schema for RestaurantDetails."""
    place_id:            str
    cuisine_type:        Optional[str]                = None
    avg_cost_per_person: Optional[float]              = None
    opening_hours:       Optional[Dict[str, str]]     = None

    class Config:
        from_attributes = True


# ─── AttractionDetails ──────────────────────────────────────────────────────

class AttractionDetailsCreate(BaseModel):
    """Create schema for AttractionDetails."""
    subcategory:   Optional[str]            = None
    tags:          Optional[List[str]]      = None
    entry_fee:     Optional[float]          = None
    opening_hours: Optional[Dict[str, str]] = None  # Map<DayOfWeek, String>


class AttractionDetailsResponse(BaseModel):
    """Response schema for AttractionDetails."""
    place_id:      str
    subcategory:   Optional[str]            = None
    tags:          Optional[List[str]]      = None
    entry_fee:     Optional[float]          = None
    opening_hours: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True
