"""Place search service for AI Engine integration."""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.place_repo import PlaceRepository


class PlaceSearchService:
    """
    Service layer for place search operations.
    Handles business logic between API routes and repository.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PlaceRepository(db)

    async def search_places(
        self,
        city: Optional[str] = None,
        country: Optional[str] = None,
        categories: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        min_price_level: Optional[int] = None,
        max_price_level: Optional[int] = None,
        interests: Optional[List[str]] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        accommodation_type: Optional[str] = None,
        max_distance_km: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "popularity_score",
        sort_desc: bool = True,
    ) -> dict:
        """
        Search places with filters and return in AI engine format.

        Returns dict with:
            - places: List of place dicts
            - total: Total matching count
            - filters_applied: Dict of applied filters
        """
        places, total = await self.repo.search_places(
            city=city,
            country=country,
            categories=categories,
            min_rating=min_rating,
            min_price_level=min_price_level,
            max_price_level=max_price_level,
            interests=interests,
            lat=lat,
            lng=lng,
            accommodation_type=accommodation_type,
            max_distance_km=max_distance_km,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )

        filters_applied = {}
        if city:
            filters_applied["city"] = city
        if country:
            filters_applied["country"] = country
        if categories:
            filters_applied["categories"] = categories
        if min_rating is not None:
            filters_applied["min_rating"] = min_rating
        if interests:
            filters_applied["interests"] = interests

        return {
            "places": places,
            "total": total,
            "filters_applied": filters_applied,
        }

    async def get_places_for_city(
        self, city: str, interests: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Simple city-based retrieval (backward compatible).
        Used by AI engine's places_tool replacement.
        """
        places = await self.repo.get_places_by_city(city)

        if interests:
            interests_set = set(interests)
            places = [
                p for p in places
                if p["category"] in interests_set
            ]
            # Safety fallback
            if not places:
                places = await self.repo.get_places_by_city(city)

        return places

    async def get_explore_filters(self, q: Optional[str] = None) -> dict:
        """
        Get location suggestions and category options from the database.
        Used by the explore/filters endpoint to populate the mobile app
        location picker and category tabs.
        """
        return await self.repo.get_explore_filters(q=q)
