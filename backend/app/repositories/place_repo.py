"""Place repository with complex search queries for AI Engine integration."""

from typing import List, Optional, Tuple
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.place import Place, AttractionDetails, RestaurantDetails, HotelDetails
from app.models.enums import PlaceCategory
from app.repositories.base_repo import BaseRepository

# ── Allowlist of valid sort fields (prevents attribute injection) ───────────
VALID_SORT_FIELDS = {"popularity_score", "rating", "name", "review_count", "price_level"}


class PlaceRepository(BaseRepository):
    """Repository for Place CRUD and complex search operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def search_places(
        self,
        city: str,
        country: Optional[str] = None,
        categories: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        min_price_level: Optional[int] = None,
        max_price_level: Optional[int] = None,
        interests: Optional[List[str]] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        max_distance_km: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "popularity_score",
        sort_desc: bool = True,
    ) -> Tuple[List[dict], int]:
        """
        Search places with multiple filters.

        Returns:
            Tuple of (places as dicts, total_count)
        """
        # ── Build base queries ──────────────────────────────────────────────
        query = select(Place)
        # count_query is rebuilt after joins are determined (see below)

        filters = []

        # City filter (case-insensitive)
        filters.append(func.lower(Place.city) == city.lower())

        # Country filter
        if country:
            filters.append(func.lower(Place.country) == country.lower())

        # Category filter (convert strings to enum values)
        if categories:
            enum_categories = []
            for cat in categories:
                if isinstance(cat, str):
                    try:
                        enum_categories.append(PlaceCategory(cat))
                    except ValueError:
                        continue  # skip invalid categories
                else:
                    enum_categories.append(cat)
            if enum_categories:
                filters.append(Place.category.in_(enum_categories))

        # Rating filter
        if min_rating is not None:
            filters.append(Place.rating >= min_rating)

        # Price level filter
        if min_price_level is not None:
            filters.append(Place.price_level >= min_price_level)
        if max_price_level is not None:
            filters.append(Place.price_level <= max_price_level)

        # Interest/Tag filter (broad search across multiple sources)
        if interests:
            # Join detail tables for interest matching
            query = query.outerjoin(
                AttractionDetails,
                Place.place_id == AttractionDetails.place_id,
            ).outerjoin(
                RestaurantDetails,
                Place.place_id == RestaurantDetails.place_id,
            ).outerjoin(
                HotelDetails,
                Place.place_id == HotelDetails.place_id,
            )

            # Build interest conditions across multiple sources
            interest_conditions = []
            for interest in interests:
                escaped = f"%{interest}%"
                interest_conditions.extend([
                    # 1. Attraction tags (JSON contains)
                    AttractionDetails.tags.op("@>")(f'["{interest}"]'),
                    # 2. Attraction subcategory (fuzzy)
                    AttractionDetails.subcategory.ilike(escaped),
                    # 3. Restaurant cuisine type (COALESCE for nullable)
                    func.coalesce(RestaurantDetails.cuisine_type, "").ilike(escaped),
                    # 4. Hotel amenities (JSON contains)
                    HotelDetails.amenities.op("@>")(f'["{interest}"]'),
                    # 5. Place name (fuzzy)
                    Place.name.ilike(escaped),
                    # 6. Place description (COALESCE for nullable)
                    func.coalesce(Place.description, "").ilike(escaped),
                ])
            filters.append(or_(*interest_conditions))

        # ── Apply filters to main query ────────────────────────────────────
        if filters:
            query = query.where(and_(*filters))

        # ── Get total count (rebuilt with same joins + DISTINCT) ────────────
        count_query = select(func.count(func.distinct(Place.place_id)))
        # Re-apply the same outerjoins if interests are present
        if interests:
            count_query = count_query.outerjoin(
                AttractionDetails, Place.place_id == AttractionDetails.place_id,
            ).outerjoin(
                RestaurantDetails, Place.place_id == RestaurantDetails.place_id,
            ).outerjoin(
                HotelDetails, Place.place_id == HotelDetails.place_id,
            )
        if filters:
            count_query = count_query.where(and_(*filters))
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # ── Eager-load relationships (after all filters/joins) ──────────────
        query = query.options(
            selectinload(Place.attraction_details),
            selectinload(Place.restaurant_details),
            selectinload(Place.hotel_details),
        )

        # ── Sorting (with allowlist validation) ──────────────────────────────
        if sort_by not in VALID_SORT_FIELDS:
            sort_by = "popularity_score"
        sort_column = getattr(Place, sort_by)
        if sort_desc:
            query = query.order_by(sort_column.desc().nullslast())
        else:
            query = query.order_by(sort_column.asc().nullsfirst())

        # ── Pagination ──────────────────────────────────────────────────────
        query = query.offset(offset).limit(limit)

        # Execute query
        result = await self.session.execute(query)
        places = result.scalars().unique().all()

        # Convert to dicts
        places_dict = [self._place_to_dict(p) for p in places]

        return places_dict, total

    async def get_places_by_city(
        self, city: str, limit: int = 100
    ) -> List[dict]:
        """Get all places for a city, sorted by popularity."""
        query = (
            select(Place)
            .options(
                selectinload(Place.attraction_details),
                selectinload(Place.restaurant_details),
                selectinload(Place.hotel_details),
            )
            .where(func.lower(Place.city) == city.lower())
            .order_by(Place.popularity_score.desc().nullslast())
            .limit(limit)
        )
        result = await self.session.execute(query)
        places = result.scalars().unique().all()
        return [self._place_to_dict(p) for p in places]

    def _place_to_dict(self, place: Place) -> dict:
        """
        Convert Place model to dict format expected by AI engine.
        Matches the format from places_tool.py's _normalize_place.
        """
        sub_category = ""
        interest_tags: list[str] = []
        cuisine_type = ""

        if hasattr(place, "attraction_details") and place.attraction_details:
            sub_category = place.attraction_details.subcategory or ""
            interest_tags = place.attraction_details.tags or []
        elif hasattr(place, "restaurant_details") and place.restaurant_details:
            cuisine_type = place.restaurant_details.cuisine_type or ""
            sub_category = cuisine_type
        elif hasattr(place, "hotel_details") and place.hotel_details:
            sub_category = "hotel"

        # Derive tags from sub_category if empty
        if not interest_tags and sub_category:
            interest_tags = [sub_category.lower()]

        # Build tags list from all detail sources for richer search
        all_tags: list[str] = []
        seen_tags: set[str] = set()

        def _add_tag(tag: str) -> None:
            lower = tag.lower()
            if lower not in seen_tags:
                all_tags.append(lower)
                seen_tags.add(lower)

        for t in interest_tags:
            _add_tag(t)
        if cuisine_type:
            _add_tag(cuisine_type)
        if sub_category:
            _add_tag(sub_category)

        # Hotel amenities
        amenities: list[str] = []
        if hasattr(place, "hotel_details") and place.hotel_details:
            amenities = place.hotel_details.amenities or []
            for amenity in amenities:
                _add_tag(amenity)

        return {
            "id": place.place_id,
            "name": place.name,
            "category": place.category.value if place.category else "",
            "sub_category": sub_category,
            "lat": place.lat or 0,
            "lon": place.lng or 0,  # Map lng → lon for AI engine compatibility
            "description": place.description or "",
            "rating": place.rating or 0,
            "review_count": place.review_count or 0,
            "popularity_score": place.popularity_score or 0,
            "interest_tags": all_tags,
            "cuisine_type": cuisine_type,
            "amenities": amenities,
            "address": place.address or "",
            "hours": place.opening_hours or {},
            "photos": (place.photo_urls or [])[:1],
            "maps_link": place.maps_link,
        }
