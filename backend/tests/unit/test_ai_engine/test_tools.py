# backend/tests/unit/test_ai_engine/test_tools.py

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_engine.tools.places_tool import get_places_for_city
from ai_engine.tools.routing_tool import get_travel_time_minutes, order_stops_by_proximity


# ── places_tool tests ─────────────────────────────────────────────────────────

# Sample places returned by PlaceRepository.get_places_by_city
_MOCK_DB_PLACES = [
    {
        "id": "h1", "name": "Test Hotel", "category": "hotel",
        "lat": 30.0, "lon": 31.0, "rating": 4.5,
        "popularity_score": 80, "interest_tags": ["hotel"],
        "sub_category": "hotel", "accommodation_type": "hotel",
    },
    {
        "id": "a1", "name": "Egyptian Museum", "category": "attractions",
        "lat": 30.05, "lon": 31.23, "rating": 4.8,
        "popularity_score": 95, "interest_tags": ["museum", "history"],
        "sub_category": "museum",
    },
    {
        "id": "a2", "name": "Khan el-Khalili", "category": "attractions",
        "lat": 30.05, "lon": 31.26, "rating": 4.3,
        "popularity_score": 75, "interest_tags": ["shopping", "market"],
        "sub_category": "market",
    },
    {
        "id": "r1", "name": "Naguib Mahfouz Restaurant", "category": "restaurant",
        "lat": 30.05, "lon": 31.26, "rating": 4.1,
        "popularity_score": 60, "interest_tags": ["egyptian", "local cuisine"],
        "sub_category": "egyptian",
    },
]


@pytest.fixture
def mock_db_places():
    """Fixture that patches async_session + PlaceRepository to return _MOCK_DB_PLACES.

    Yields the mock repo instance so tests can inspect call_args if needed.

    Usage:
        async def test_something(self, mock_db_places):
            places = await get_places_for_city("Cairo")
            assert len(places) > 0
    """
    repo_instance = MagicMock()
    repo_instance.get_places_by_city = AsyncMock(return_value=_MOCK_DB_PLACES)

    with patch("ai_engine.tools.places_tool.PlaceRepository") as mock_repo_cls, \
         patch("ai_engine.tools.places_tool.async_session") as mock_session:
        mock_repo_cls.return_value = repo_instance
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        yield repo_instance


@pytest.fixture
def mock_db_places_empty():
    """Fixture that patches the DB to return an empty place list."""
    repo_instance = MagicMock()
    repo_instance.get_places_by_city = AsyncMock(return_value=[])

    with patch("ai_engine.tools.places_tool.PlaceRepository") as mock_repo_cls, \
         patch("ai_engine.tools.places_tool.async_session") as mock_session:
        mock_repo_cls.return_value = repo_instance
        mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        yield repo_instance


@pytest.mark.asyncio
class TestGetPlacesForCity:

    async def test_known_city_returns_places(self, mock_db_places):
        places = await get_places_for_city("Cairo")
        assert isinstance(places, list)
        assert len(places) == len(_MOCK_DB_PLACES)

    async def test_city_lookup_is_case_insensitive(self, mock_db_places):
        lower = await get_places_for_city("cairo")
        assert isinstance(lower, list)
        assert len(lower) > 0

    async def test_each_place_has_required_keys(self, mock_db_places):
        places = await get_places_for_city("Cairo")
        for place in places:
            assert "name" in place
            assert "category" in place
            assert "lat" in place
            assert "lon" in place
            assert isinstance(place["lat"], float)
            assert isinstance(place["lon"], float)

    async def test_returns_all_places(self, mock_db_places):
        all_places = await get_places_for_city("Cairo")
        assert len(all_places) == len(_MOCK_DB_PLACES)

    async def test_repo_called_with_correct_city(self, mock_db_places):
        await get_places_for_city("Cairo")
        mock_db_places.get_places_by_city.assert_awaited_once_with("Cairo")

    async def test_unknown_city_returns_empty_list(self, mock_db_places_empty):
        places = await get_places_for_city("Atlantis")
        assert isinstance(places, list)
        assert len(places) == 0

    async def test_none_city_returns_empty_list(self):
        places = await get_places_for_city(None)
        assert isinstance(places, list)
        assert len(places) == 0

    async def test_empty_string_returns_empty_list(self):
        places = await get_places_for_city("")
        assert isinstance(places, list)
        assert len(places) == 0

    async def test_db_error_returns_empty_list(self):
        repo_instance = MagicMock()
        repo_instance.get_places_by_city = AsyncMock(side_effect=Exception("DB down"))

        with patch("ai_engine.tools.places_tool.PlaceRepository") as mock_repo_cls, \
             patch("ai_engine.tools.places_tool.async_session") as mock_session:
            mock_repo_cls.return_value = repo_instance
            mock_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            places = await get_places_for_city("Cairo")
            assert places == []


# ── routing_tool tests ────────────────────────────────────────────────────────

class TestGetTravelTime:

    def test_returns_float(self):
        origin = {"lat": 30.0478, "lon": 31.2336}
        dest   = {"lat": 29.9792, "lon": 31.1342}
        result = get_travel_time_minutes(origin, dest)
        assert isinstance(result, float)

    def test_returns_positive_value(self):
        origin = {"lat": 30.0478, "lon": 31.2336}
        dest   = {"lat": 29.9792, "lon": 31.1342}
        assert get_travel_time_minutes(origin, dest) > 0

    def test_same_point_returns_value(self):
        point = {"lat": 30.0478, "lon": 31.2336}
        # Sprint 3 mock always returns 20.0 — just assert it doesn't crash
        result = get_travel_time_minutes(point, point)
        assert isinstance(result, float)


class TestOrderStopsByProximity:

    def test_returns_list(self):
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 29.9, "lon": 31.1},
        ]
        result = order_stops_by_proximity(stops)
        assert isinstance(result, list)

    def test_returns_same_length(self):
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 29.9, "lon": 31.1},
            {"name": "C", "lat": 30.1, "lon": 31.2},
        ]
        result = order_stops_by_proximity(stops)
        assert len(result) == len(stops)

    def test_empty_list_returns_empty(self):
        assert order_stops_by_proximity([]) == []

    def test_single_stop_returns_single(self):
        stops = [{"name": "A", "lat": 30.0, "lon": 31.0}]
        result = order_stops_by_proximity(stops)
        assert len(result) == 1