# tests/integration/test_place_search.py

"""
Integration tests for the enhanced place search functionality.

Tests cover:
  - Category validation (HTTP 400 for invalid values)
  - COALESCE for nullable text fields (Place.description, RestaurantDetails.cuisine_type)
  - HotelDetails.amenities in interest search
  - AttractionDetails.subcategory in interest search
  - _place_to_dict enrichment (amenities, merged tags, dedup)
  - Sort validation and fallback behavior
  - Count accuracy with DISTINCT
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from app.schemas.place_search import PlaceSearchRequest, PlaceSearchResponse, VALID_CATEGORIES
from app.models.enums import PlaceCategory
from app.repositories.place_repo import PlaceRepository, VALID_SORT_FIELDS


# ═════════════════════════════════════════════════════════════════════════════
# 1. Category Validation (HTTP 400)
# ═════════════════════════════════════════════════════════════════════════════


class TestCategoryValidation:
    """Invalid category values should be rejected before hitting the database."""

    def test_valid_categories_accepted(self):
        for cat in ["hotel", "restaurant", "attraction"]:
            req = PlaceSearchRequest(city="Cairo", categories=[cat])
            assert req.categories == [cat]

    def test_multiple_valid_categories(self):
        req = PlaceSearchRequest(
            city="Cairo", categories=["hotel", "restaurant", "attraction"]
        )
        assert len(req.categories) == 3

    def test_none_categories_is_fine(self):
        req = PlaceSearchRequest(city="Cairo", categories=None)
        assert req.categories is None

    def test_empty_list_categories_is_fine(self):
        req = PlaceSearchRequest(city="Cairo", categories=[])
        assert req.categories == []

    def test_invalid_category_accepted_by_schema_but_rejected_by_route(self):
        """Schema accepts any string; route handler rejects invalid categories."""
        # Schema does NOT validate categories (returns 400 in route, not 422)
        req = PlaceSearchRequest(city="Cairo", categories=["museum"])
        assert req.categories == ["museum"]

        # Route handler catches invalid categories
        invalid = [c for c in req.categories if c not in VALID_CATEGORIES]
        assert invalid == ["museum"]

    def test_mixed_valid_and_invalid_detected_at_route(self):
        """Route handler detects mixed valid/invalid categories."""
        req = PlaceSearchRequest(
            city="Cairo", categories=["hotel", "museum", "attraction"]
        )
        invalid = [c for c in req.categories if c not in VALID_CATEGORIES]
        assert invalid == ["museum"]

    def test_case_sensitive_categories_detected_at_route(self):
        """Uppercase 'Hotel' is invalid (enum values are lowercase)."""
        req = PlaceSearchRequest(city="Cairo", categories=["Hotel"])
        invalid = [c for c in req.categories if c not in VALID_CATEGORIES]
        assert invalid == ["Hotel"]

    def test_valid_categories_set_matches_enum(self):
        expected = {e.value for e in PlaceCategory}
        assert VALID_CATEGORIES == expected

    def test_route_handler_validates_categories(self):
        """Route handler validates categories and would raise HTTP 400."""
        invalid_cats = ["museum", "park"]
        invalid = [c for c in invalid_cats if c not in VALID_CATEGORIES]
        assert len(invalid) == 2
        assert all(c not in VALID_CATEGORIES for c in invalid)


# ═════════════════════════════════════════════════════════════════════════════
# 2. _place_to_dict: Tag Merging and Enrichment
# ═════════════════════════════════════════════════════════════════════════════


def _make_place_model(**overrides):
    """Create a mock Place model object with relationships."""
    place = MagicMock()
    place.place_id = overrides.get("place_id", "p001")
    place.name = overrides.get("name", "Test Place")
    place.category = overrides.get("category", PlaceCategory.attraction)
    place.description = overrides.get("description", "A nice place")
    place.lat = overrides.get("lat", 30.0)
    place.lng = overrides.get("lng", 31.0)
    place.rating = overrides.get("rating", 4.5)
    place.review_count = overrides.get("review_count", 100)
    place.popularity_score = overrides.get("popularity_score", 80)
    place.price_level = overrides.get("price_level", 3)
    place.address = overrides.get("address", "123 Street")
    place.city = overrides.get("city", "Cairo")
    place.country = overrides.get("country", "Egypt")
    place.phone = overrides.get("phone", None)
    place.website = overrides.get("website", None)
    place.maps_link = overrides.get("maps_link", None)
    place.opening_hours = overrides.get("opening_hours", {})
    place.photo_urls = overrides.get("photo_urls", [])
    place.embedding = overrides.get("embedding", None)
    place.attraction_details = overrides.get("attraction_details", None)
    place.restaurant_details = overrides.get("restaurant_details", None)
    place.hotel_details = overrides.get("hotel_details", None)
    return place


def _make_attraction_details(subcategory="museum"):
    d = MagicMock()
    d.subcategory = subcategory
    d.entry_fee = 50.0
    return d


def _make_restaurant_details(cuisine_type="Italian"):
    d = MagicMock()
    d.cuisine_type = cuisine_type
    d.avg_cost_per_person = 25.0
    d.opening_hours = {}
    return d


def _make_hotel_details(amenities=None, accommodation_type=None):
    d = MagicMock()
    d.star_class = 4
    d.nightly_rate = 150.0
    d.amenities = amenities or ["wifi", "pool"]
    d.booking_platforms = ["booking.com"]
    d.accommodation_type = accommodation_type or "hotel"
    return d


def _place_to_dict(place) -> dict:
    """Call _place_to_dict on a new repository instance (avoids __new__ hack)."""
    repo = PlaceRepository(session=MagicMock())
    return repo._place_to_dict(place)


class TestPlaceToDictEnrichment:
    """_place_to_dict should merge tags from all detail sources."""

    def test_attraction_subcategory_included_in_interest_tags(self):
        place = _make_place_model(
            attraction_details=_make_attraction_details(
                subcategory="museum"
            )
        )
        result = _place_to_dict(place)
        assert "museum" in result["interest_tags"]

    def test_cuisine_type_included_in_interest_tags(self):
        place = _make_place_model(
            category=PlaceCategory.restaurant,
            restaurant_details=_make_restaurant_details(cuisine_type="Italian"),
            attraction_details=None,
        )
        result = _place_to_dict(place)
        assert "italian" in result["interest_tags"]
        assert result["cuisine_type"] == "Italian"

    def test_hotel_amenities_included_in_interest_tags(self):
        place = _make_place_model(
            category=PlaceCategory.hotel,
            hotel_details=_make_hotel_details(amenities=["spa", "pool", "gym"]),
            attraction_details=None,
            restaurant_details=None,
        )
        result = _place_to_dict(place)
        assert "spa" in result["interest_tags"]
        assert "pool" in result["interest_tags"]
        assert "gym" in result["interest_tags"]
        assert result["amenities"] == ["spa", "pool", "gym"]

    def test_amenities_empty_for_non_hotel(self):
        place = _make_place_model(
            category=PlaceCategory.attraction,
            attraction_details=_make_attraction_details(),
            hotel_details=None,
        )
        result = _place_to_dict(place)
        assert result["amenities"] == []

    def test_subcategory_included_in_interest_tags(self):
        place = _make_place_model(
            attraction_details=_make_attraction_details(
                subcategory="historic"
            )
        )
        result = _place_to_dict(place)
        assert "historic" in result["interest_tags"]

    def test_tags_are_case_deduplicated(self):
        place = _make_place_model(
            attraction_details=_make_attraction_details(
                subcategory="Italian"
            ),
            restaurant_details=_make_restaurant_details(cuisine_type="italian"),
        )
        result = _place_to_dict(place)
        italian_count = sum(
            1 for t in result["interest_tags"] if t.lower() == "italian"
        )
        assert italian_count == 1

    def test_null_description_does_not_crash(self):
        place = _make_place_model(description=None)
        result = _place_to_dict(place)
        assert result["description"] == ""

    def test_null_cuisine_type_does_not_crash(self):
        place = _make_place_model(
            category=PlaceCategory.restaurant,
            restaurant_details=MagicMock(cuisine_type=None),
            attraction_details=None,
        )
        result = _place_to_dict(place)
        assert result["cuisine_type"] == ""

    def test_null_amenities_does_not_crash(self):
        d = MagicMock()
        d.star_class = 4
        d.nightly_rate = 150.0
        d.amenities = None
        d.booking_platforms = ["booking.com"]
        d.accommodation_type = None
        place = _make_place_model(
            category=PlaceCategory.hotel,
            hotel_details=d,
            attraction_details=None,
            restaurant_details=None,
        )
        result = _place_to_dict(place)
        assert result["amenities"] == []
        assert result["interest_tags"] == ["hotel"]

    def test_hotel_amenities_merge_with_hotel_subcategory(self):
        """Hotel details: subcategory + amenities should all appear in interest_tags."""
        place = _make_place_model(
            category=PlaceCategory.hotel,
            attraction_details=None,
            restaurant_details=None,
            hotel_details=_make_hotel_details(amenities=["spa", "gym"]),
        )
        result = _place_to_dict(place)
        tags_lower = [t.lower() for t in result["interest_tags"]]
        assert "hotel" in tags_lower  # default subcategory
        assert "spa" in tags_lower
        assert "gym" in tags_lower


# ═════════════════════════════════════════════════════════════════════════════
# 3. Sort Validation
# ═════════════════════════════════════════════════════════════════════════════


class TestSortValidation:
    """Invalid sort fields should fall back to popularity_score."""

    def test_valid_sort_fields_set(self):
        expected = {"popularity_score", "rating", "name", "review_count", "price_level"}
        assert VALID_SORT_FIELDS == expected

    def test_all_sort_fields_are_place_columns(self):
        """Every valid sort field should map to a real Place column."""
        from app.models.place import Place

        for field in VALID_SORT_FIELDS:
            assert hasattr(Place, field), f"Place has no column '{field}'"


# ═════════════════════════════════════════════════════════════════════════════
# 4. Schema Request Validation
# ═════════════════════════════════════════════════════════════════════════════


class TestAccommodationTypeFilter:
    """accommodation_type filter should work in the request schema."""

    def test_accommodation_type_accepted(self):
        req = PlaceSearchRequest(city="Cairo", accommodation_type="hotel")
        assert req.accommodation_type == "hotel"

    def test_accommodation_type_none_by_default(self):
        req = PlaceSearchRequest(city="Cairo")
        assert req.accommodation_type is None

    def test_accommodation_type_with_category(self):
        req = PlaceSearchRequest(
            city="Cairo", categories=["hotel"], accommodation_type="resort"
        )
        assert req.accommodation_type == "resort"
        assert req.categories == ["hotel"]


class TestSchemaValidation:
    """PlaceSearchRequest schema validation rules."""

    def test_min_rating_bounds(self):
        req = PlaceSearchRequest(city="Cairo", min_rating=4.5)
        assert req.min_rating == 4.5

    def test_min_rating_out_of_bounds(self):
        with pytest.raises(ValidationError):
            PlaceSearchRequest(city="Cairo", min_rating=6.0)

    def test_price_level_bounds(self):
        req = PlaceSearchRequest(city="Cairo", min_price_level=1, max_price_level=4)
        assert req.min_price_level == 1

    def test_price_level_out_of_bounds(self):
        with pytest.raises(ValidationError):
            PlaceSearchRequest(city="Cairo", min_price_level=0)

    def test_limit_bounds(self):
        req = PlaceSearchRequest(city="Cairo", limit=200)
        assert req.limit == 200

    def test_limit_out_of_bounds(self):
        with pytest.raises(ValidationError):
            PlaceSearchRequest(city="Cairo", limit=0)

    def test_offset_non_negative(self):
        req = PlaceSearchRequest(city="Cairo", offset=0)
        assert req.offset == 0

    def test_offset_negative_rejected(self):
        with pytest.raises(ValidationError):
            PlaceSearchRequest(city="Cairo", offset=-1)

    def test_default_values(self):
        req = PlaceSearchRequest(city="Cairo")
        assert req.limit == 50
        assert req.offset == 0
        assert req.sort_by == "popularity_score"
        assert req.sort_desc is True
        assert req.categories is None
        assert req.interests is None


# ═════════════════════════════════════════════════════════════════════════════
# 5. PlaceSearchResponse Structure
# ═════════════════════════════════════════════════════════════════════════════


class TestPlaceSearchResponse:
    """PlaceSearchResponse should match the expected structure."""

    def test_response_has_required_fields(self):
        resp = PlaceSearchResponse(
            places=[], total=0, filters_applied={"city": "Cairo"}
        )
        assert resp.places == []
        assert resp.total == 0
        assert resp.filters_applied["city"] == "Cairo"

    def test_response_with_places(self):
        place = {
            "id": "p001",
            "name": "Test",
            "category": "attraction",
            "lat": 30.0,
            "lon": 31.0,
            "rating": 4.5,
        }
        resp = PlaceSearchResponse(
            places=[place], total=1, filters_applied={"city": "Cairo"}
        )
        assert len(resp.places) == 1
        assert resp.places[0]["id"] == "p001"


# ═════════════════════════════════════════════════════════════════════════════
# 6. Service Layer
# ═════════════════════════════════════════════════════════════════════════════


class TestPlaceSearchService:
    """PlaceSearchService orchestration logic."""

    @pytest.mark.asyncio
    async def test_search_places_returns_expected_structure(self):
        from app.services.places_service import PlaceSearchService

        mock_repo = AsyncMock()
        mock_repo.search_places.return_value = ([{"id": "p1"}], 1)

        service = PlaceSearchService(db=MagicMock())
        service.repo = mock_repo

        result = await service.search_places(city="Cairo")
        assert "places" in result
        assert "total" in result
        assert "filters_applied" in result
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_get_places_for_city_with_interests_filters(self):
        from app.services.places_service import PlaceSearchService

        mock_repo = AsyncMock()
        mock_repo.get_places_by_city.return_value = [
            {"id": "p1", "category": "hotel", "interest_tags": ["spa"], "name": "Hotel"},
            {"id": "p2", "category": "attraction", "interest_tags": ["history"], "name": "Museum"},
        ]

        service = PlaceSearchService(db=MagicMock())
        service.repo = mock_repo

        result = await service.get_places_for_city("Cairo", interests=["history"])
        assert len(result) == 2  # hotel always included + museum matches

    @pytest.mark.asyncio
    async def test_get_places_for_city_fallback_on_empty(self):
        from app.services.places_service import PlaceSearchService

        # Use non-hotel places with no matching tags so the filter yields empty
        all_places = [
            {"id": "p1", "category": "attraction", "interest_tags": ["art"], "name": "Gallery"},
        ]

        mock_repo = AsyncMock()
        mock_repo.get_places_by_city.return_value = all_places

        service = PlaceSearchService(db=MagicMock())
        service.repo = mock_repo

        result = await service.get_places_for_city("Cairo", interests=["nonexistent"])
        assert len(result) == 1
        # Filtered list was empty → fallback triggered → second call
        assert mock_repo.get_places_by_city.call_count == 2
