"""Places routes — search endpoints for AI Engine integration + user exploration."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.place_search import (
    PlaceSearchRequest,
    PlaceSearchResponse,
    ExplorePlacesResponse,
    VALID_CATEGORIES,
    VALID_ACCOMMODATION_TYPES,
)
from app.services.places_service import PlaceSearchService

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /places/explore/filters
# Returns available cities, countries, and categories from the DB
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/explore/filters")
async def get_explore_filters(
    q: Optional[str] = Query(None, description="Search text for location autocomplete (e.g. 'Cai' → 'Cairo, Egypt')"),
    limit: int = Query(20, ge=1, le=50, description="Max location suggestions to return"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get location suggestions and category options for the explore endpoint.

    Populates the mobile app's location picker and category tabs.
    Returns locations with type info (country vs city) for the picker UI.

    When q is provided, returns matching locations for autocomplete.
    Without q, returns popular locations sorted by place count.

    **No auth required** — public browsing endpoint.

    **Response format:**
    - locations: List of location objects with key, city, country, display,
      subtitle, type (country/city), and count
    - countries: Simplified country list for quick access
    - categories: Category tabs with counts

    **Examples:**
    - GET /places/explore/filters → all locations + categories
    - GET /places/explore/filters?q=cai → suggestions matching 'Cai'
    - GET /places/explore/filters?q=egypt → locations in Egypt
    """
    service = PlaceSearchService(db)
    result = await service.get_explore_filters(q=q)
    # Apply limit to locations
    if "locations" in result:
        result["locations"] = result["locations"][:limit]
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GET /places/explore
# User-facing exploration — queries the database
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/explore", response_model=ExplorePlacesResponse)
async def explore_places(
    city: Optional[str] = Query(None, description="Filter by city name (e.g. Cairo, Dubai)"),
    country: Optional[str] = Query("Egypt", description="Filter by country (e.g. Egypt, UAE). Defaults to Egypt."),
    category: Optional[str] = Query("hotel", description="Filter by category: attractions, restaurant, hotel. Defaults to hotel."),
    no_defaults: Optional[bool] = Query(None, description="If true, ignore country/category defaults and return all places."),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    Explore places by city, country, and category.

    Queries the database for places matching the given filters.
    Data is expected to be seeded from the curated JSON files in data/.

    **No auth required** — public browsing endpoint.

    **Defaults:** country=Egypt, category=hotel (matches mobile app initial state).

    **Examples:**
    - GET /places/explore (returns hotels in Egypt, sorted by popularity)
    - GET /places/explore?category=attractions
    - GET /places/explore?city=cairo&category=restaurant
    - GET /places/explore?country=egypt&category=attractions
    """
    # ── Handle no_defaults: clear both country and category ───────
    categories = None
    if no_defaults:
        country = None
        categories = None
    else:
        # Normalize category for DB query
        if category:
            cat_lower = category.lower().strip()
            cat_map = {
                "attraction": "attraction", "attractions": "attraction",
                "restaurant": "restaurant", "restaurants": "restaurant",
                "hotel": "hotel", "hotels": "hotel",
            }
            if cat_lower not in cat_map:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid category: '{category}'. "
                        f"Valid options are: attractions, restaurant, hotel"
                    ),
                )
            categories = [cat_map[cat_lower]]

        # Normalize country (strip whitespace, default to Egypt)
        if country:
            country = country.strip()

    service = PlaceSearchService(db)

    result = await service.search_places(
        city=city,
        country=country,
        categories=categories,
        limit=limit,
        offset=offset,
        sort_by="popularity_score",
        sort_desc=True,
    )

    return ExplorePlacesResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /places/search
# Main search endpoint for Retrieval Agent (DB-backed)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/search", response_model=PlaceSearchResponse)
async def search_places(
    request: PlaceSearchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search places with structured filters.

    Used by the AI Engine's Retrieval Agent to fetch places
    from the database instead of local JSON files.

    **Filters supported:**
    - City (required)
    - Categories: attraction, restaurant, hotel
    - Accommodation type (hotels only): hotel, hostel, resort, luxury
    - Rating (min)
    - Price level (min/max)
    - Interests/tags
    - Location (lat/lng) with distance filter

    **Returns:**
    - places: List of place dicts in AI engine format
    - total: Total matching places in database
    - filters_applied: Summary of applied filters

    **Errors:**
    - 400: Invalid category or accommodation_type values
    """
    # Validate categories (return 400, not 422)
    if request.categories:
        invalid = [c for c in request.categories if c not in VALID_CATEGORIES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid category values: {invalid}. "
                    f"Valid options are: {sorted(VALID_CATEGORIES)}"
                ),
            )

    # ── Validate accommodation_type (return 400) ──────────────────────
    if request.accommodation_type and request.accommodation_type not in VALID_ACCOMMODATION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid accommodation_type: {request.accommodation_type}. "
                f"Valid options are: {sorted(VALID_ACCOMMODATION_TYPES)}"
            ),
        )

    service = PlaceSearchService(db)

    result = await service.search_places(
        city=request.city,
        country=request.country,
        categories=request.categories,
        min_rating=request.min_rating,
        min_price_level=request.min_price_level,
        max_price_level=request.max_price_level,
        interests=request.interests,
        accommodation_type=request.accommodation_type,
        lat=request.lat,
        lng=request.lng,
        max_distance_km=request.max_distance_km,
        limit=request.limit,
        offset=request.offset,
        sort_by=request.sort_by,
        sort_desc=request.sort_desc,
    )

    return PlaceSearchResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /places/city/{city}
# Simple city retrieval (backward compatible)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/city/{city}")
async def get_places_by_city(
    city: str,
    interests: Optional[List[str]] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all places for a city.
    Simple endpoint for basic city-based retrieval.
    """
    service = PlaceSearchService(db)
    places = await service.get_places_for_city(city, interests)
    return {"city": city, "places": places, "count": len(places)}
