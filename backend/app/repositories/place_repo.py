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
        star_class: Optional[int] = None,
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

        # Price level filter (include NULL — many places lack price_level)
        if min_price_level is not None:
            filters.append(
                or_(Place.price_level.is_(None), Place.price_level >= min_price_level)
            )
        if max_price_level is not None:
            filters.append(
                or_(Place.price_level.is_(None), Place.price_level <= max_price_level)
            )

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

        # Star class filter (requires HotelDetails join; include NULLs)
        # Avoid adding a second outerjoin if accommodation_type or interests
        # already added one.
        if star_class is not None:
            needs_hotel_join = not accommodation_type and not interests
            if needs_hotel_join:
                query = query.outerjoin(
                    HotelDetails,
                    Place.place_id == HotelDetails.place_id,
                )
            filters.append(
                or_(HotelDetails.star_class.is_(None), HotelDetails.star_class == star_class)
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

        # ── Exclude categories not in the Python enum (avoids LookupError) ──
        valid_categories = [c.value for c in PlaceCategory]
        filters.append(cast(Place.category, SAString).in_(valid_categories))

        # ── Apply filters to main query ────────────────────────────────────
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
        self, city: str, limit: int = 500
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
        # Exclude categories not in the Python enum (avoids LookupError)
        valid_categories = [c.value for c in PlaceCategory]
        query = query.where(cast(Place.category, SAString).in_(valid_categories))
        result = await self.session.execute(query)
        places = result.scalars().unique().all()
        return [self._place_to_dict(p) for p in places]

    async def get_places_by_city_diverse(
        self, city: str,
        per_subcategory: int = 20,
        per_cuisine: int = 10,
        per_accommodation: int = 10,
    ) -> List[dict]:
        """
        Get places for a city with SQL-level stratified sampling across ALL types.

        Instead of taking the top N places by popularity (which could all be
        from the same category), this queries the top K places from EACH:
        - Attraction subcategory (parks, museums, history, shopping, ...)
        - Restaurant cuisine type (Restaurant, Cafe, Street Food, ...)
        - Hotel accommodation type (hotel, hostel, resort, luxury)

        This guarantees diverse representation regardless of popularity scores.

        Args:
            city: Destination city name.
            per_subcategory: Top N places per attraction subcategory.
            per_cuisine: Top N restaurants per cuisine type.
            per_accommodation: Top N hotels per accommodation type.

        Returns:
            List of place dicts with balanced representation across all types.
        """
        city_key = city.lower().strip()
        all_places = []

        # ── 1. ATTRACTIONS: top K per subcategory ──────────────────────────
        subcat_query = (
            select(func.distinct(AttractionDetails.subcategory))
            .join(Place, Place.place_id == AttractionDetails.place_id)
            .where(func.lower(Place.city) == city_key)
            .where(AttractionDetails.subcategory.isnot(None))
            .where(AttractionDetails.subcategory != "")
        )
        subcat_result = await self.session.execute(subcat_query)
        subcategories = [row[0] for row in subcat_result.all()]

        for sub in subcategories:
            q = (
                select(Place)
                .options(
                    selectinload(Place.attraction_details),
                    selectinload(Place.restaurant_details),
                    selectinload(Place.hotel_details),
                )
                .join(AttractionDetails, Place.place_id == AttractionDetails.place_id)
                .where(func.lower(Place.city) == city_key)
                .where(AttractionDetails.subcategory == sub)
                .order_by(Place.popularity_score.desc().nullslast())
                .limit(per_subcategory)
            )
            result = await self.session.execute(q)
            all_places.extend(result.scalars().unique().all())

        # ── 2. RESTAURANTS: top K per cuisine type ────────────────────────
        cuisine_query = (
            select(func.distinct(RestaurantDetails.cuisine_type))
            .join(Place, Place.place_id == RestaurantDetails.place_id)
            .where(func.lower(Place.city) == city_key)
            .where(RestaurantDetails.cuisine_type.isnot(None))
            .where(RestaurantDetails.cuisine_type != "")
        )
        cuisine_result = await self.session.execute(cuisine_query)
        cuisine_types = [row[0] for row in cuisine_result.all()]

        for cuisine in cuisine_types:
            q = (
                select(Place)
                .options(
                    selectinload(Place.attraction_details),
                    selectinload(Place.restaurant_details),
                    selectinload(Place.hotel_details),
                )
                .join(RestaurantDetails, Place.place_id == RestaurantDetails.place_id)
                .where(func.lower(Place.city) == city_key)
                .where(RestaurantDetails.cuisine_type == cuisine)
                .order_by(Place.popularity_score.desc().nullslast())
                .limit(per_cuisine)
            )
            result = await self.session.execute(q)
            all_places.extend(result.scalars().unique().all())

        # ── 3. HOTELS: top K per accommodation type ────────────────────────
        # Cast enum to text for comparison
        acc_query = (
            select(func.distinct(HotelDetails.accommodation_type))
            .join(Place, Place.place_id == HotelDetails.place_id)
            .where(func.lower(Place.city) == city_key)
            .where(HotelDetails.accommodation_type.isnot(None))
        )
        acc_result = await self.session.execute(acc_query)
        acc_types = [row[0] for row in acc_result.all() if row[0]]

        for acc_type in acc_types:
            # acc_type might be an enum object — convert to string for comparison
            acc_val = acc_type.value if hasattr(acc_type, "value") else str(acc_type)
            q = (
                select(Place)
                .options(
                    selectinload(Place.attraction_details),
                    selectinload(Place.restaurant_details),
                    selectinload(Place.hotel_details),
                )
                .join(HotelDetails, Place.place_id == HotelDetails.place_id)
                .where(func.lower(Place.city) == city_key)
                .where(
                    func.lower(cast(HotelDetails.accommodation_type, SAString)) == acc_val.lower()
                )
                .order_by(Place.popularity_score.desc().nullslast())
                .limit(per_accommodation)
            )
            result = await self.session.execute(q)
            all_places.extend(result.scalars().unique().all())

        # Final sort: return places sorted by popularity_score descending
        # so the overall result is well-ordered even though we collected
        # top K per subcategory/cuisine/accommodation type.
        all_places.sort(key=lambda p: p.popularity_score or 0, reverse=True)
        return [self._place_to_dict(p) for p in all_places]

    def _place_to_dict(self, place: Place) -> dict:
        """
        Convert Place model to dict format expected by AI engine.
        Matches the format from places_tool.py's _normalize_place.
        """
        sub_category = ""
        # interest_tags removed
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
        # interest_tags removed

        # Build tags list from all detail sources for richer search
        all_tags: list[str] = []
        seen_tags: set[str] = set()

        def _add_tag(tag: str) -> None:
            lower = tag.lower()
            if lower not in seen_tags:
                all_tags.append(lower)
                seen_tags.add(lower)

        if cuisine_type:
            _add_tag(cuisine_type)
        if sub_category:
            _add_tag(sub_category)

        # Hotel amenities & accommodation type
        # NOTE: amenities are NOT added as individual tags — the amenities
        # field is already returned separately and `_add_tag(amenity)` just bloated
        # the prompt with 10+ redundant per-hotel tags like "pool", "gym", "free wifi".
        # The sub_category (accommodation_type) is sufficient as a hotel tag.
        amenities: list[str] = []
        accommodation_type = ""
        if hasattr(place, "hotel_details") and place.hotel_details:
            amenities = place.hotel_details.amenities or []
            accommodation_type = place.hotel_details.accommodation_type or ""
            if hasattr(accommodation_type, "value"):
                accommodation_type = accommodation_type.value

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
            # "interest_tags": all_tags,  # removed
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

    async def find_by_name_exact(
        self,
        name: str,
        city: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Optional[dict]:
        """
        Fast exact name match for place search.

        This is the first layer in hybrid search - attempts to find places
        by exact or fuzzy name match before falling back to vector search.

        Args:
            name: Place name to search for (supports partial matching)
            city: Optional city filter for disambiguation
            country: Optional country filter for disambiguation

        Returns:
            Single best matching place dict, or None if no match found.
        """
        if not name:
            return None

        query = (
            select(Place)
            .options(
                selectinload(Place.attraction_details),
                selectinload(Place.restaurant_details),
                selectinload(Place.hotel_details),
            )
            .where(Place.name.ilike(f"%{name}%"))
        )

        # Add city filter if provided
        if city:
            query = query.where(func.lower(Place.city) == city.lower())

        # Add country filter if provided
        if country:
            query = query.where(func.lower(Place.country) == country.lower())

        # Order by popularity to get the best match
        query = query.order_by(Place.popularity_score.desc().nullslast()).limit(1)

        # Exclude categories not in the Python enum (avoids LookupError)
        valid_categories = [c.value for c in PlaceCategory]
        query = query.where(cast(Place.category, SAString).in_(valid_categories))

        result = await self.session.execute(query)
        place = result.scalar_one_or_none()

        return self._place_to_dict(place) if place else None

    async def get_explore_filters(self, q: Optional[str] = None) -> dict:
        """
        Query the database for location suggestions and category options.
        Used by the explore/filters endpoint to populate the mobile
        app location picker and category tabs.

        Without `q`, locations/countries are returned EMPTY. The
        "Recent locations" section shown in the picker UI is populated
        client-side from the user's own local search history — this
        endpoint has no concept of per-user history (it's unauthenticated),
        so it must not fall back to globally popular locations here, as
        that would misrepresent "recent" with "most common in the DB".

        With `q`, returns locations whose city/country match the text
        (autocomplete-style substring search).

        Categories are always returned regardless of `q`.
        """
        q = q.strip() if q else None

        countries: list[dict] = []
        cities: list[dict] = []

        # ── When no query, return ALL cities for the explore dropdown ──
        if q:
            pattern = f"%{q}%"

            # ── Countries (top-level locations) ─────────────────────────
            country_q = (
                select(
                    Place.country,
                    func.count(Place.place_id).label("cnt"),
                )
                .where(Place.country.isnot(None))
                .where(Place.country != "")
                .where(Place.country.ilike(pattern))
                .group_by(Place.country)
                .order_by(func.count(Place.place_id).desc())
            )
            country_result = await self.session.execute(country_q)
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

            # ── Cities (grouped with country) ───────────────────────────
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
                .where(
                    or_(
                        Place.city.ilike(pattern),
                        Place.country.ilike(pattern),
                    )
                )
                .group_by(Place.city, Place.country)
                .order_by(func.count(Place.place_id).desc())
                .limit(20)
            )
            loc_result = await self.session.execute(loc_q)
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
        else:
            # ── No query: return ALL cities for the city dropdown filter ──
            # The Flutter explore screen calls this endpoint to populate its
            # city picker. Without a query we return every distinct city
            # (with country) sorted by place count so the dropdown is usable.
            all_cities_q = (
                select(
                    Place.city,
                    Place.country,
                    func.count(Place.place_id).label("cnt"),
                )
                .where(Place.city.isnot(None))
                .where(Place.city != "")
                .where(Place.country.isnot(None))
                .where(Place.country != "")
                .group_by(Place.city, Place.country)
                .order_by(func.count(Place.place_id).desc())
                .limit(50)
            )
            all_cities_result = await self.session.execute(all_cities_q)
            for row in all_cities_result.all():
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

        # Merge: countries first, then cities.
        # Safety cap: limit countries so a pathological short query can never
        # silently crowd out every city suggestion.
        locations = countries[:5] + cities

        # ── Categories with counts (always returned, independent of q) ──
        # Cast to text to avoid LookupError for DB values not in the Python enum.
        cat_q = (
            select(cast(Place.category, SAString), func.count(Place.place_id).label("cnt"))
            .group_by(cast(Place.category, SAString))
            .order_by(func.count(Place.place_id).desc())
        )
        cat_result = await self.session.execute(cat_q)
        categories = []
        for row in cat_result.all():
            cat_val = (row[0] or "").strip().lower()
            if cat_val:
                categories.append({"key": cat_val, "display": cat_val.title(), "count": row[1]})

        return {
            "locations": locations,
            "countries": [{"key": c["key"], "display": c["display"], "count": c["count"]} for c in countries]
        }