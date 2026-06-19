"""Places routes — search endpoints for AI Engine integration."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.place_search import (
    PlaceSearchRequest,
    PlaceSearchResponse,
)
from app.services.places_service import PlaceSearchService

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# POST /places/search
# Main search endpoint for Retrieval Agent
# ═════════════════════════════════════════════════════════════════════════════


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
    - Categories (attraction, restaurant, hotel)
    - Rating (min)
    - Price level (min/max)
    - Interests/tags
    - Location (lat/lng) with distance filter
    """
    service = PlaceSearchService(db)

    result = await service.search_places(
        city=request.city,
        country=request.country,
        categories=request.categories,
        min_rating=request.min_rating,
        min_price_level=request.min_price_level,
        max_price_level=request.max_price_level,
        interests=request.interests,
        lat=request.lat,
        lng=request.lng,
        max_distance_km=request.max_distance_km,
        limit=request.limit,
        offset=request.offset,
        sort_by=request.sort_by,
        sort_desc=request.sort_desc,
    )

    return PlaceSearchResponse(**result)


# ═════════════════════════════════════════════════════════════════════════════
# GET /places/city/{city}
# Simple city retrieval (backward compatible)
# ═════════════════════════════════════════════════════════════════════════════


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
