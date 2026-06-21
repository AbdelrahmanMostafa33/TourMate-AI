# tests/integration/test_explore_fixes.py

"""
Integration tests for the explore endpoint fixes (Issues A, B, C).

Issue A: Country-type suggestions must have city=None, not the country name.
Issue B: city and country must both be .strip()-normalized in explore_places.
Issue C: A safety cap limits countries in the merged list so cities aren't
         crowded out by a pathological short query.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


# ═════════════════════════════════════════════════════════════════════════════
# Issue A — Country-type suggestions must have city=None
# ═════════════════════════════════════════════════════════════════════════════


class TestCountryTypeCityIsNull:
    """When type='country', the city field must be None, not the country name."""

    @pytest.mark.asyncio
    async def test_country_type_has_city_none(self):
        """GET /explore/filters?q=egypt — country results must have city=None."""
        from app.repositories.place_repo import PlaceRepository

        mock_session = AsyncMock()
        country_row = MagicMock()
        country_row.__getitem__ = lambda self, idx: ["Egypt", 50][idx]

        city_row = MagicMock()
        city_row.__getitem__ = lambda self, idx: ["Cairo", "Egypt", 20][idx]

        country_result = MagicMock()
        country_result.all.return_value = [country_row]

        city_result = MagicMock()
        city_result.all.return_value = [city_row]

        cat_result = MagicMock()
        cat_result.all.return_value = []

        # Execution order in get_explore_filters: country → city → category
        mock_session.execute = AsyncMock(
            side_effect=[country_result, city_result, cat_result]
        )

        repo = PlaceRepository(mock_session)
        result = await repo.get_explore_filters(q="egypt")

        country_locations = [
            loc for loc in result["locations"] if loc["type"] == "country"
        ]
        assert len(country_locations) > 0, "Expected at least one country-type result"

        for loc in country_locations:
            assert loc["city"] is None, (
                f"Country-type location '{loc['display']}' has city={loc['city']!r}, "
                f"expected None"
            )
            assert loc["country"] is not None, "country field should still be set"

    @pytest.mark.asyncio
    async def test_city_type_still_has_city_value(self):
        """City-type suggestions must still have a non-None city field."""
        from app.repositories.place_repo import PlaceRepository

        mock_session = AsyncMock()
        country_result = MagicMock()
        country_result.all.return_value = []

        city_row = MagicMock()
        city_row.__getitem__ = lambda self, idx: ["Cairo", "Egypt", 20][idx]
        city_result = MagicMock()
        city_result.all.return_value = [city_row]

        cat_result = MagicMock()
        cat_result.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[country_result, city_result, cat_result]
        )

        repo = PlaceRepository(mock_session)
        result = await repo.get_explore_filters(q="cairo")

        city_locations = [
            loc for loc in result["locations"] if loc["type"] == "city"
        ]
        assert len(city_locations) > 0
        for loc in city_locations:
            assert loc["city"] is not None, "City-type location should have city set"
            assert loc["city"] != "", "City-type location should have non-empty city"


# ═════════════════════════════════════════════════════════════════════════════
# Issue B — city must be .strip()-normalized like country
# ═════════════════════════════════════════════════════════════════════════════


class TestCityStripNormalization:
    """city must be stripped of whitespace just like country."""

    @pytest.mark.asyncio
    async def test_explore_places_strips_city_whitespace(self):
        """explore_places route must .strip() city before passing to service."""
        from fastapi.testclient import TestClient
        from app.main import app

        mock_service = AsyncMock()
        mock_service.search_places.return_value = {
            "places": [],
            "total": 0,
            "filters_applied": {},
        }

        with patch(
            "app.api.v1.routes.places.PlaceSearchService", return_value=mock_service
        ):
            client = TestClient(app)
            client.get(
                "/api/v1/places/explore",
                params={"city": "  Cairo  ", "country": "Egypt", "category": "hotel"},
            )

            call_kwargs = mock_service.search_places.call_args
            assert call_kwargs.kwargs["city"] == "Cairo", (
                f"Expected stripped city 'Cairo', got {call_kwargs.kwargs['city']!r}"
            )

    @pytest.mark.asyncio
    async def test_explore_places_strips_country_whitespace(self):
        """explore_places route must also .strip() country."""
        from fastapi.testclient import TestClient
        from app.main import app

        mock_service = AsyncMock()
        mock_service.search_places.return_value = {
            "places": [],
            "total": 0,
            "filters_applied": {},
        }

        with patch(
            "app.api.v1.routes.places.PlaceSearchService", return_value=mock_service
        ):
            client = TestClient(app)
            client.get(
                "/api/v1/places/explore",
                params={
                    "city": "Cairo",
                    "country": "  Egypt  ",
                    "category": "hotel",
                },
            )

            call_kwargs = mock_service.search_places.call_args
            assert call_kwargs.kwargs["country"] == "Egypt", (
                f"Expected stripped country 'Egypt', got {call_kwargs.kwargs['country']!r}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# Issue C — Safety cap prevents countries from crowding out cities
# ═════════════════════════════════════════════════════════════════════════════


class TestCountrySafetyCap:
    """A safety cap ensures the merged list always contains some cities."""

    @pytest.mark.asyncio
    async def test_many_countries_dont_crowd_out_cities(self):
        """Even with many matching countries, cities should still appear."""
        from app.repositories.place_repo import PlaceRepository

        mock_session = AsyncMock()

        # Simulate 20 countries matching the query
        country_rows = []
        for i in range(20):
            row = MagicMock()
            row.__getitem__ = lambda self, idx, i=i: [f"Country_{i}", 100 - i][idx]
            country_rows.append(row)

        country_result = MagicMock()
        country_result.all.return_value = country_rows

        # Only 2 cities match
        city_row1 = MagicMock()
        city_row1.__getitem__ = lambda self, idx: ["Cairo", "Egypt", 15][idx]
        city_row2 = MagicMock()
        city_row2.__getitem__ = lambda self, idx: ["Giza", "Egypt", 10][idx]

        city_result = MagicMock()
        city_result.all.return_value = [city_row1, city_row2]

        cat_result = MagicMock()
        cat_result.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[country_result, city_result, cat_result]
        )

        repo = PlaceRepository(mock_session)
        result = await repo.get_explore_filters(q="c")

        locations = result["locations"]

        country_count = sum(1 for loc in locations if loc["type"] == "country")
        city_count = sum(1 for loc in locations if loc["type"] == "city")

        assert country_count <= 5, (
            f"Expected at most 5 countries due to safety cap, got {country_count}"
        )
        assert city_count > 0, (
            f"Expected some cities in the merged list, got {city_count}"
        )
        assert len(locations) == country_count + city_count

    @pytest.mark.asyncio
    async def test_few_countries_not_capped(self):
        """When fewer than 5 countries match, all should be returned."""
        from app.repositories.place_repo import PlaceRepository

        mock_session = AsyncMock()

        # Only 2 countries
        country_rows = []
        for i in range(2):
            row = MagicMock()
            row.__getitem__ = lambda self, idx, i=i: [f"Country_{i}", 50 - i][idx]
            country_rows.append(row)

        country_result = MagicMock()
        country_result.all.return_value = country_rows

        city_row = MagicMock()
        city_row.__getitem__ = lambda self, idx: ["Cairo", "Egypt", 20][idx]
        city_result = MagicMock()
        city_result.all.return_value = [city_row]

        cat_result = MagicMock()
        cat_result.all.return_value = []

        mock_session.execute = AsyncMock(
            side_effect=[country_result, city_result, cat_result]
        )

        repo = PlaceRepository(mock_session)
        result = await repo.get_explore_filters(q="co")

        country_count = sum(
            1 for loc in result["locations"] if loc["type"] == "country"
        )
        assert country_count == 2, "All 2 countries should be returned (under cap)"


# ═════════════════════════════════════════════════════════════════════════════
# Combined: Country-type suggestion forwarded to /explore returns results
# ═════════════════════════════════════════════════════════════════════════════


class TestCountrySuggestionForwarding:
    """
    When a user selects a country-type suggestion, the frontend forwards
    city=None+country=X to /explore. With city=None, the query must match
    ALL places in that country, not zero.
    """

    @pytest.mark.asyncio
    async def test_country_pick_with_none_city_matches_all(self):
        """
        Simulate: suggestion has city=None, country='Egypt'.
        The search_places query with city=None, country='Egypt' should
        match places (not return zero due to city='Egypt' mismatch).
        """
        from app.repositories.place_repo import PlaceRepository

        mock_session = AsyncMock()

        # Mock search_places to return results when city=None, country='Egypt'
        place_mock = MagicMock()
        place_mock.place_id = "p001"
        place_mock.name = "Pyramids"
        place_mock.category = "attractions"
        place_mock.description = "Ancient wonder"
        place_mock.lat = 29.9792
        place_mock.lng = 31.1342
        place_mock.rating = 4.8
        place_mock.review_count = 94000
        place_mock.popularity_score = 95.0
        place_mock.price_level = 3
        place_mock.address = "Giza, Egypt"
        place_mock.city = "Giza"
        place_mock.country = "Egypt"
        place_mock.phone = None
        place_mock.website = None
        place_mock.maps_link = None
        place_mock.opening_hours = {}
        place_mock.photo_urls = []
        place_mock.embedding = None
        place_mock.attraction_details = MagicMock(
            subcategory="historic", entry_fee=10.0
        )
        place_mock.restaurant_details = None
        place_mock.hotel_details = None

        # Execution order in search_places: count_query FIRST, then main query
        count_mock = MagicMock()
        count_mock.scalar.return_value = 1
        result_mock = MagicMock()
        result_mock.scalars.return_value.unique.return_value.all.return_value = [
            place_mock
        ]

        mock_session.execute = AsyncMock(side_effect=[count_mock, result_mock])

        repo = PlaceRepository(mock_session)
        places, total = await repo.search_places(
            city=None,  # This is what happens when suggestion type='country'
            country="Egypt",
            categories=["attraction"],
            limit=50,
            offset=0,
        )

        assert total > 0, "Country-level pick with city=None should match places"
        assert len(places) > 0
        assert places[0]["country"] == "Egypt"


# ═════════════════════════════════════════════════════════════════════════════
# Default behavior — /explore returns 200 with sensible defaults
# ═════════════════════════════════════════════════════════════════════════════


class TestExploreDefaults:
    """GET /places/explore with no params should return 200 with Egypt hotels."""

    @pytest.mark.asyncio
    async def test_explore_no_params_returns_200(self):
        """GET /places/explore (no params) → 200, hotels in Egypt."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app

        mock_service = AsyncMock()
        mock_service.search_places.return_value = {
            "places": [
                {
                    "id": "h001",
                    "name": "Test Hotel",
                    "category": "hotel",
                    "lat": 30.0,
                    "lon": 31.0,
                    "rating": 4.5,
                    "city": "Cairo",
                    "country": "Egypt",
                }
            ],
            "total": 1,
            "filters_applied": {"country": "Egypt"},
        }

        with patch(
            "app.api.v1.routes.places.PlaceSearchService", return_value=mock_service
        ):
            client = TestClient(app)
            response = client.get("/api/v1/places/explore")

            assert response.status_code == 200
            data = response.json()
            assert "places" in data
            assert data["total"] >= 0

            # Verify the service was called with Egypt defaults
            call_kwargs = mock_service.search_places.call_args.kwargs
            assert call_kwargs.get("country") == "Egypt"
            assert call_kwargs.get("categories") == ["hotel"]

    @pytest.mark.asyncio
    async def test_explore_cairo_restaurants_returns_200(self):
        """GET /places/explore?city=cairo&country=egypt&category=restaurant → 200."""
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app

        mock_service = AsyncMock()
        mock_service.search_places.return_value = {
            "places": [
                {
                    "id": "r001",
                    "name": "Test Restaurant",
                    "category": "restaurant",
                    "lat": 30.0,
                    "lon": 31.0,
                    "rating": 4.2,
                    "city": "Cairo",
                    "country": "Egypt",
                }
            ],
            "total": 1,
            "filters_applied": {"city": "cairo", "country": "egypt"},
        }

        with patch(
            "app.api.v1.routes.places.PlaceSearchService", return_value=mock_service
        ):
            client = TestClient(app)
            response = client.get(
                "/api/v1/places/explore",
                params={
                    "city": "cairo",
                    "country": "egypt",
                    "category": "restaurant",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "places" in data

            # Verify service was called with the correct filters
            call_kwargs = mock_service.search_places.call_args.kwargs
            assert call_kwargs.get("city") == "cairo"
            assert call_kwargs.get("country") == "egypt"
            assert call_kwargs.get("categories") == ["restaurant"]
