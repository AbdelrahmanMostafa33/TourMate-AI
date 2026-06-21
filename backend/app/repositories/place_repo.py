"""Place repository with complex search queries for AI Engine integration."""

from typing import List, Optional, Tuple
from sqlalchemy import select, and_, or_, func, cast, String as SAString
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

        # City filter (case-insensitive, optional)
        if city:
            filters.append(func.lower(Place.city) == city.lower())

        # Country filter
        if country:
            filters.append(func.lower(Place.country) == country.lower())

        # Category filter (case-insensitive string comparison)
        # NOTE: Place.category is a PostgreSQL enum column (place_category type).
        # func.lower() has no overload for enum types in Postgres, so we must
        # cast to text first — same pattern used below for accommodation_type.
        if categories:
            valid = {c.value for c in PlaceCategory}
            cat_values = [c.lower().strip() for c in categories if c.lower().strip() in valid]
            if cat_values:
                filters.append(
                    func.lower(cast(Place.category, SAString)).in_(cat_values)
                )

        # Rating filter
        if min_rating is not None:
            filters.append(Place.rating >= min_rating)

        # Price level filter
        if min_price_level is not None:
            filters.append(Place.price_level >= min_price_level)
        if max_price_level is not None:
            filters.append(Place.price_level <= max_price_level)

        # Accommodation type filter (requires HotelDetails join)
        # Cast enum to text for safe comparison with asyncpg
        if accommodation_type:
            query = query.outerjoin(
                HotelDetails,
                Place.place_id == HotelDetails.place_id,
            )
            filters.append(
                func.lower(cast(HotelDetails.accommodation_type, SAString)) == accommodation_type.lower()
            )

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
                    # 1. Attraction subcategory (fuzzy)
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

        entry_fee = None
        avg_cost_per_person = None

        if hasattr(place, "attraction_details") and place.attraction_details:
            sub_category = place.attraction_details.subcategory or ""
            entry_fee = place.attraction_details.entry_fee
        elif hasattr(place, "restaurant_details") and place.restaurant_details:
            cuisine_type = place.restaurant_details.cuisine_type or ""
            sub_category = cuisine_type
            avg_cost_per_person = place.restaurant_details.avg_cost_per_person
        elif hasattr(place, "hotel_details") and place.hotel_details:
            sub_category = (place.hotel_details.accommodation_type or "hotel").lower()

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

        # Hotel amenities & accommodation type
        amenities: list[str] = []
        accommodation_type = ""
        if hasattr(place, "hotel_details") and place.hotel_details:
            amenities = place.hotel_details.amenities or []
            accommodation_type = place.hotel_details.accommodation_type or ""
            if hasattr(accommodation_type, "value"):
                accommodation_type = accommodation_type.value
            for amenity in amenities:
                _add_tag(amenity)

        # Hotel-specific pricing
        nightly_rate = None
        star_class = None
        if hasattr(place, "hotel_details") and place.hotel_details:
            nightly_rate = getattr(place.hotel_details, "nightly_rate", None)
            star_class = getattr(place.hotel_details, "star_class", None)

        # Category enum -> plain string value for the AI engine response
        category_value = place.category
        if hasattr(category_value, "value"):
            category_value = category_value.value

        return {
            "id": place.place_id,
            "name": place.name,
            "category": category_value or "",
            "sub_category": sub_category,
            "lat": place.lat or 0,
            "lon": place.lng or 0,
            "description": place.description or "",
            "rating": place.rating or 0,
            "review_count": place.review_count or 0,
            "popularity_score": place.popularity_score or 0,
            "interest_tags": all_tags,
            "cuisine_type": cuisine_type,
            "amenities": amenities,
            "accommodation_type": accommodation_type,
            "address": place.address or "",
            "hours": place.opening_hours or {},
            "city": place.city or "",
            "country": place.country or "",
            "price_level": place.price_level,
            "entry_fee": entry_fee,
            "avg_cost_per_person": avg_cost_per_person,
            "nightly_rate": nightly_rate,
            "star_class": star_class,
            "photos": (place.photo_urls or [])[:1],
            "maps_link": place.maps_link,
        }

    async def get_explore_filters(self, q: Optional[str] = None) -> dict:
        """
        Query the database for location suggestions and category options.
        Used by the explore/filters endpoint to populate the mobile
        app location picker and category tabs.

        Returns locations with type info (country vs city) for the
        location picker's "Recent locations" display.
        """
        # ── Countries (top-level locations) ────────────────────────────
        country_q = (
            select(
                Place.country,
                func.count(Place.place_id).label("cnt"),
            )
            .where(Place.country.isnot(None))
            .where(Place.country != "")
            .group_by(Place.country)
            .order_by(func.count(Place.place_id).desc())
        )
        if q:
            pattern = f"%{q.strip()}%"
            country_q = country_q.where(Place.country.ilike(pattern))

        country_result = await self.session.execute(country_q)
        countries = []
        for row in country_result.all():
            country_name = (row[0] or "").strip()
            countries.append({
                "key": country_name.lower(),
                "city": None,
                "country": country_name,
                "display": country_name,
                "subtitle": "Country",
                "type": "country",
                "count": row[1],
            })

        # ── Cities (grouped with country) ──────────────────────────────
        loc_q = (
            select(
                Place.city,
                Place.country,
                func.count(Place.place_id).label("cnt"),
            )
            .where(Place.city.isnot(None))
            .where(Place.city != "")
            .where(Place.country.isnot(None))
            .where(Place.country != "")
        )

        if q:
            pattern = f"%{q.strip()}%"
            loc_q = loc_q.where(
                or_(
                    Place.city.ilike(pattern),
                    Place.country.ilike(pattern),
                )
            )

        loc_q = loc_q.group_by(Place.city, Place.country)
        loc_q = loc_q.order_by(func.count(Place.place_id).desc())
        loc_q = loc_q.limit(20)

        loc_result = await self.session.execute(loc_q)
        cities = []
        for row in loc_result.all():
            city_name = (row[0] or "").strip()
            country_name = (row[1] or "").strip()
            cities.append({
                "key": city_name.lower(),
                "city": city_name,
                "country": country_name,
                "display": f"{city_name}, {country_name}",
                "subtitle": f"{city_name}, {country_name}",
                "type": "city",
                "count": row[2],
            })

        # Merge: countries first, then cities (for "Recent locations")
        #Safety cap: limit countries so a pathological short query can never
        # silently crowd out every city suggestion.
        locations = countries[:5] + cities

        # ── Categories with counts ────────────────────────────────────
        cat_q = (
            select(Place.category, func.count(Place.place_id).label("cnt"))
            .group_by(Place.category)
            .order_by(func.count(Place.place_id).desc())
        )
        cat_result = await self.session.execute(cat_q)
        categories = []
        for row in cat_result.all():
            val = row[0]
            cat_val = val.value if hasattr(val, "value") else str(val) if val else ""
            categories.append({"key": cat_val, "display": cat_val.title(), "count": row[1]})

        return {
            "locations": locations,
            "countries": [{"key": c["key"], "display": c["display"], "count": c["count"]} for c in countries],
            "categories": categories,
        }
        
        