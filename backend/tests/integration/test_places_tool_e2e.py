# tests/integration/test_places_tool_e2e.py

"""
End-to-end integration test for the places_tool DB path.

Verifies that get_places_for_city works against a real database:
  - Seeds Place + detail rows into an in-memory SQLite database
  - Calls get_places_for_city() (which queries via PlaceRepository)
  - Asserts the returned dicts contain expected places, categories, and tags

This catches wiring bugs that unit tests with mocks cannot detect
(e.g. wrong column names, broken joins, missing selectinload).
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.database import Base
from ai_engine.tools.places_tool import get_places_for_city


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _seed_places_sync(conn) -> None:
    """Insert sample places via a raw connection (used by run_sync)."""
    from sqlalchemy import text

    # Hotels
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('h1', 'Marriott Mena House', 'hotel', 29.9758, 31.1334, 4.6, 80, 500, 'Cairo', 'Egypt', 'Al Ahram Rd')"))
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('h2', 'Budget Cairo Inn', 'hotel', 30.05, 31.24, 3.8, 50, 200, 'Cairo', 'Egypt', '123 Main St')"))
    conn.execute(text("INSERT INTO hotel_details (place_id, star_class, nightly_rate, amenities, accommodation_type) VALUES ('h1', 5, 200.0, '[\"wifi\", \"pool\", \"spa\"]', 'luxury')"))
    conn.execute(text("INSERT INTO hotel_details (place_id, star_class, nightly_rate, amenities, accommodation_type) VALUES ('h2', 2, 40.0, '[\"wifi\"]', 'hostel')"))

    # Attractions
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('a1', 'Egyptian Museum', 'attractions', 30.0478, 31.2336, 4.7, 95, 2000, 'Cairo', 'Egypt', 'Tahrir Square')"))
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('a2', 'Khan El Khalili', 'attractions', 30.0476, 31.2611, 4.5, 85, 1500, 'Cairo', 'Egypt', 'El Muezz St')"))
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('a3', 'Pyramids of Giza', 'attractions', 29.9792, 31.1342, 4.8, 100, 5000, 'Cairo', 'Egypt', 'Al Haram')"))
    conn.execute(text("INSERT INTO attraction_details (place_id, subcategory, entry_fee) VALUES ('a1', 'museum', 50.0)"))
    conn.execute(text("INSERT INTO attraction_details (place_id, subcategory) VALUES ('a2', 'market')"))
    conn.execute(text("INSERT INTO attraction_details (place_id, subcategory) VALUES ('a3', 'historic monument')"))

    # Restaurants
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('r1', 'Abu Shukri', 'restaurant', 30.0464, 31.2325, 4.5, 75, 600, 'Cairo', 'Egypt', 'Near Al-Azhar')"))
    conn.execute(text("INSERT INTO restaurant_details (place_id, cuisine_type, avg_cost_per_person) VALUES ('r1', 'local cuisine', 15.0)"))

    # Alexandria
    conn.execute(text("INSERT INTO places (place_id, name, category, lat, lng, rating, popularity_score, review_count, city, country, address) VALUES ('ax1', 'Bibliotheca Alexandrina', 'attractions', 31.2089, 29.9092, 4.6, 88, 1800, 'Alexandria', 'Egypt', 'Al Corniche')"))
    conn.execute(text("INSERT INTO attraction_details (place_id, subcategory) VALUES ('ax1', 'museum')"))



@pytest.fixture()
def seeded_db():
    """Create an in-memory async SQLite DB seeded with sample places.

    Yields a helper ``query(city, interests=None)`` that patches
    ``async_session`` and calls ``get_places_for_city`` against the
    real seeded database.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Seed data via the async engine (run DDL + inserts in a sync callback)
    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_seed_places_sync)

    import asyncio
    asyncio.run(_setup())

    async def query(city: str):
        """Run get_places_for_city against the seeded DB."""
        async_session_factory = MagicMock()
        async_session_factory.return_value.__aenter__ = AsyncMock(
            return_value=AsyncSession(engine),
        )
        async_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("ai_engine.tools.places_tool.async_session", async_session_factory):
            return await get_places_for_city(city)

    yield query

    async def _teardown():
        await engine.dispose()
    asyncio.run(_teardown())


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestGetPlacesForCityE2E:
    """End-to-end tests using a real in-memory SQLite database."""

    async def test_returns_all_cairo_places(self, seeded_db):
        """Querying 'Cairo' should return all Cairo places sorted by popularity."""
        places = await seeded_db("Cairo")
        assert len(places) == 6  # 2 hotels + 3 attractions + 1 restaurant
        names = {p["name"] for p in places}
        assert "Egyptian Museum" in names
        assert "Khan El Khalili" in names
        assert "Abu Shukri" in names

    async def test_alexandria_places_not_in_cairo_results(self, seeded_db):
        """Places from Alexandria should not appear in Cairo results."""
        places = await seeded_db("Cairo")
        names = {p["name"] for p in places}
        assert "Bibliotheca Alexandrina" not in names

    async def test_unknown_city_returns_empty(self, seeded_db):
        """A city with no places should return an empty list."""
        places = await seeded_db("Tokyo")
        assert places == []

    async def test_places_have_required_keys(self, seeded_db):
        """Every returned place dict should have the keys the pipeline expects."""
        places = await seeded_db("Cairo")
        required_keys = {"id", "name", "category", "lat", "lon", "rating", "popularity_score"}
        for place in places:
            missing = required_keys - set(place.keys())
            assert not missing, f"Place '{place.get('name')}' missing keys: {missing}"

    async def test_place_categories_match_db_values(self, seeded_db):
        """Category values should come directly from the database."""
        places = await seeded_db("Cairo")
        categories = {p["category"] for p in places}
        assert "hotel" in categories
        assert "attractions" in categories
        assert "restaurant" in categories



    async def test_hotel_amenities_and_details_populated(self, seeded_db):
        """Hotel details (amenities, accommodation_type) should be in the result.
        Amenities are NOT duplicated as individual interest_tags."""
        places = await seeded_db("Cairo")
        marriott = next(p for p in places if p["name"] == "Marriott Mena House")
        assert marriott["accommodation_type"] == "luxury"
        # Amenities are stored in the amenities field, not as individual interest_tags
        assert "wifi" in marriott.get("amenities", [])
        assert "pool" in marriott.get("amenities", [])
        assert "spa" in marriott.get("amenities", [])
        assert "pool" not in marriott.get("interest_tags", [])
        assert "spa" not in marriott.get("interest_tags", [])

    async def test_restaurant_cuisine_populated(self, seeded_db):
        """Restaurant cuisine_type should appear in interest_tags."""
        places = await seeded_db("Cairo")
        abu_shukri = next(p for p in places if p["name"] == "Abu Shukri")
        assert abu_shukri["cuisine_type"] == "local cuisine"
        assert "local cuisine" in abu_shukri.get("interest_tags", [])

    async def test_attraction_subcategory_in_tags(self, seeded_db):
        """Attraction subcategory should appear in interest_tags."""
        places = await seeded_db("Cairo")
        museum = next(p for p in places if p["name"] == "Egyptian Museum")
        assert "museum" in museum.get("interest_tags", [])

    async def test_sorted_by_popularity_descending(self, seeded_db):
        """Places should be returned sorted by popularity_score descending."""
        places = await seeded_db("Cairo")
        scores = [p["popularity_score"] for p in places]
        assert scores == sorted(scores, reverse=True)
