"""Place Search schemas for AI Engine integration + user exploration."""

from pydantic import BaseModel, Field
from typing import Optional, List

from app.models.enums import PlaceCategory, AccommodationType

# Valid category values for validation (used by route handler for 400 response)
VALID_CATEGORIES = {e.value for e in PlaceCategory}
VALID_ACCOMMODATION_TYPES = {e.value for e in AccommodationType}


class PlaceSearchRequest(BaseModel):
    """
    Request schema for structured place search.
    Used by the Retrieval Agent to query places from the database.
    """
    city: str = Field(..., description="Destination city name")
    country: Optional[str] = Field(None, description="Country filter")

    # Category filters
    categories: Optional[List[str]] = Field(
        None, description="Filter by categories: attraction, restaurant, hotel"
    )

    # Accommodation type filter (hotels only)
    accommodation_type: Optional[str] = Field(
        None, description=f"Filter hotels by type: {sorted(VALID_ACCOMMODATION_TYPES)}"
    )

    # Rating filters
    min_rating: Optional[float] = Field(
        None, ge=0, le=5, description="Minimum rating threshold"
    )

    # Price filters
    min_price_level: Optional[int] = Field(
        None, ge=1, le=4, description="Minimum price level"
    )
    max_price_level: Optional[int] = Field(
        None, ge=1, le=4, description="Maximum price level"
    )

    # Interest/Tag filters
    interests: Optional[List[str]] = Field(
        None, description="User interests for tag matching (e.g. history, food)"
    )

    # Location filters
    lat: Optional[float] = Field(None, description="Center latitude for distance filter")
    lng: Optional[float] = Field(None, description="Center longitude for distance filter")
    max_distance_km: Optional[float] = Field(
        None, ge=0, description="Max distance from center in km"
    )

    # Pagination
    limit: int = Field(50, ge=1, le=200, description="Max results to return")
    offset: int = Field(0, ge=0, description="Results offset for pagination")

    # Sorting
    sort_by: Optional[str] = Field(
        "popularity_score", description="Field to sort by: popularity_score, rating, name"
    )
    sort_desc: bool = Field(True, description="Sort descending (highest first)")


class PlaceSearchResponse(BaseModel):
    """
    Response schema for place search (DB-backed).
    Returns places in the format expected by AI engine agents.

    Each place dict includes:
    - id, name, category, sub_category
    - lat, lon (coordinates)
    - rating, popularity_score, review_count
    - interest_tags (merged from all detail sources)
    - cuisine_type (restaurants only)
    - amenities, accommodation_type (hotels only)
    """
    places: List[dict] = Field(..., description="Filtered places in AI engine format")
    total: int = Field(..., description="Total matching places in database")
    filters_applied: dict = Field(..., description="Summary of applied filters")

    class Config:
        json_schema_extra = {
            "example": {
                "places": [
                    {
                        "id": "place_001",
                        "name": "Egyptian Museum",
                        "category": "attractions",
                        "sub_category": "museum",
                        "lat": 30.0478,
                        "lon": 31.2336,
                        "rating": 4.5,
                        "popularity_score": 85.0,
                        "interest_tags": ["history", "culture"],
                    },
                    {
                        "id": "place_002",
                        "name": "Four Seasons Hotel Cairo",
                        "category": "hotel",
                        "sub_category": "luxury",
                        "lat": 30.0531,
                        "lon": 31.2254,
                        "rating": 4.8,
                        "popularity_score": 92.0,
                        "interest_tags": ["luxury"],
                        "amenities": ["spa", "pool", "gym"],
                        "accommodation_type": "luxury",
                    }
                ],
                "total": 2,
                "filters_applied": {
                    "city": "cairo",
                    "categories": ["attraction", "hotel"],
                    "accommodation_type": None,
                    "min_rating": None,
                    "interests": None,
                },
            }
        }


class ExplorePlacesResponse(BaseModel):
    """
    Response schema for user-facing place exploration.
    Loads from curated JSON data files (treated as DB until seeded).
    """
    places: List[dict] = Field(..., description="Matching places")
    total: int = Field(..., description="Total matching places across all data files")
    filters_applied: dict = Field(..., description="Summary of applied filters")

    class Config:
        json_schema_extra = {
            "example": {
                "places": [
                    {
                        "id": "lo-747C0ECE",
                        "name": "Giza Necropolis",
                        "category": "attractions",
                        "sub_category": "Historic Sites",
                        "lat": 29.9772,
                        "lon": 31.1324,
                        "rating": 4.6,
                        "review_count": 25400,
                        "popularity_score": 94.4,
                        "city": "Cairo",
                        "country": "Egypt",
                        "address": "Al Ahram, Nazlet El-Semman, Giza",
                        "nightly_rate": None,
                        "star_class": None,
                        "photos": ["https://example.com/giza.jpg"],
                    }
                ],
                "total": 1,
                "filters_applied": {"city": "cairo", "categories": ["attraction"]},
            }
        }
