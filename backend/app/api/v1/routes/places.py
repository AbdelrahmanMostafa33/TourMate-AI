"""Places routes — search endpoints for AI Engine integration + user exploration."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.place import Place, HotelDetails, RestaurantDetails, AttractionDetails
from app.repositories.place_repo import PlaceRepository
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
    country: Optional[str] = Query(
        None,
        description=(
            "Filter by country (e.g. Egypt, UAE). "
            "Defaults to Egypt only when neither city nor country is provided "
            "(the untouched initial state). If you pass city alone, the search "
            "spans that city across all countries — pass country too if you "
            "want it scoped to one."
        ),
    ),
    category: Optional[str] = Query(
        None,
        description="Filter by category: attractions, restaurant, hotel. Defaults to all categories when not provided.",
    ),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    Explore places by city, country, and category.

    Queries the database for places matching the given filters.
    Data is expected to be seeded from the curated JSON files in data/.

    Note: city/country here are independent free-text filters — they are
    NOT required to originate from a /places/explore/filters suggestion.
    The filters endpoint is purely an autocomplete UX aid; a user typing
    a value directly and submitting it must work identically to tapping
    a suggestion, as long as the value matches what's in the DB.

    **No auth required** — public browsing endpoint.

    **Defaults:**
    - country: defaults to Egypt ONLY when both city and country are omitted
      (the untouched initial state). Pass city alone to search that city
      across every country in the DB — e.g. a "Cairo" autocomplete pick
      that matched multiple countries.
    - category: defaults to None (all categories).
      Pass attraction, restaurant, or hotel to filter.

    Whatever you DO pass for city/country is always respected as-is —
    there is no flag that erases an explicitly provided value.

    **Examples:**
    - GET /places/explore (Egypt, all categories)
    - GET /places/explore?category=restaurant (Egypt restaurants)
    - GET /places/explore?city=cairo&category=restaurant (Cairo restaurants, any country)
    - GET /places/explore?city=cairo&country=egypt&category=restaurant (Cairo, Egypt restaurants only)
    - GET /places/explore?country=Egypt (all Egypt, all categories)
    """
    # ── country default: only for the untouched initial state ─────────────
    # If the caller passed a city without a country (e.g. an autocomplete
    # suggestion for "Cairo" that doesn't pin a single country, or a value
    # the user typed by hand), do NOT silently scope it to Egypt — search
    # that city across every country in the DB instead.
    if city is None and country is None:
        country = "Egypt"

    # ── category filter: null means no filter (all categories) ──
    categories = None
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

    # Normalize country (strip whitespace)
    if country:
        country = country.strip()

    # Normalize city (strip whitespace) — without this, a value like
    # "Cairo " (trailing space from a client) silently matches zero rows.
    if city:
        city = city.strip()

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
# Main search endpoint for Place Retriever (DB-backed)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/search", response_model=PlaceSearchResponse)
async def search_places(
    request: PlaceSearchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search places with structured filters.

    Used by the AI Engine's Place Retriever to fetch places
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
# POST /places/search/semantic
# Semantic search using embeddings
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/search/semantic")
async def semantic_search_places(
    request: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search using text embeddings and cosine similarity.

    Takes a natural language query, embeds it, and returns places
    ranked by semantic similarity to the query.

    **Request body:**
    - query: Natural language search query (e.g. "romantic dinner with sea view")
    - city: Optional city filter
    - category: Optional category filter
    - limit: Max results (default 20)

    **Returns:**
    - places: List of places with similarity scores
    - total: Total matching places
    - query: The original query
    """
    from ai_engine.services.embedding_service import (
        embed_query, cosine_similarity, build_query_text
    )
    from app.models.place import Place
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select, and_, func, cast, String as SAString
    import numpy as np

    query_text = request.get("query", "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="Query is required")

    city_filter = request.get("city")
    category_filter = request.get("category")
    limit = request.get("limit", 20)

    # Format query for embedding
    formatted_query = f"task: search result | query: {query_text}"
    query_vector = embed_query(formatted_query)

    if query_vector is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding service unavailable. Please try again."
        )

    # Load all places with embeddings (optionally filtered by city/category)
    filters = [
        Place.embedding.isnot(None),
    ]

    if city_filter:
        filters.append(func.lower(Place.city) == city_filter.lower().strip())

    if category_filter:
        cat_lower = category_filter.lower().strip()
        cat_map = {
            "attraction": "attraction", "attractions": "attraction",
            "restaurant": "restaurant", "restaurants": "restaurant",
            "hotel": "hotel", "hotels": "hotel",
        }
        if cat_lower in cat_map:
            filters.append(
                func.lower(cast(Place.category, SAString)) == cat_map[cat_lower]
            )

    stmt = (
        select(Place)
        .options(
            selectinload(Place.attraction_details),
            selectinload(Place.restaurant_details),
            selectinload(Place.hotel_details),
        )
        .where(and_(*filters))
    )

    result = await db.execute(stmt)
    places = result.scalars().unique().all()

    # Compute similarity scores
    repo = PlaceRepository(db)
    scored_places = []
    for place in places:
        if place.embedding is not None:
            try:
                place_vector = list(place.embedding) if not isinstance(place.embedding, list) else place.embedding
                score = cosine_similarity(query_vector, place_vector)
                place_dict = repo._place_to_dict(place)
                place_dict["similarity_score"] = round(score, 4)
                scored_places.append(place_dict)
            except Exception:
                continue

    # Sort by similarity score descending
    scored_places.sort(key=lambda p: p.get("similarity_score", 0), reverse=True)

    # Apply limit
    total = len(scored_places)
    scored_places = scored_places[:limit]

    return {
        "places": scored_places,
        "total": total,
        "query": query_text,
    }


@router.get("/{place_id}")
async def get_place_detail(
    place_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full details for a single place by its ID.

    Returns the complete place record with all category-specific
    details (hotel_details, restaurant_details, attraction_details),
    photos, address, coordinates, and pricing info.

    Used by the mobile app's PlaceDetailScreen.

    **No auth required** — public browsing endpoint.

    **Errors:**
    - 404: Place not found
    """
    result = await db.execute(
        select(Place)
        .options(
            selectinload(Place.attraction_details),
            selectinload(Place.restaurant_details),
            selectinload(Place.hotel_details),
        )
        .where(Place.place_id == place_id)
    )
    place = result.scalar_one_or_none()

    if not place:
        raise HTTPException(status_code=404, detail="Place not found")

    repo = PlaceRepository(db)
    return repo._place_to_dict(place)


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