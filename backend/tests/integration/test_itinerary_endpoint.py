"""
Integration tests for GET /api/v1/itinerary/{trip_id}.

Verifies that the endpoint returns a properly structured ItineraryResponse
with nested DayResponse and StopResponse objects.

Uses the shared db_session fixture from conftest.py (in-memory SQLite).
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.enums import TimeOfDay, StopStatus
from app.core.security import get_current_user


# ── Dependencies Override ─────────────────────────────────────────────────

TEST_USER_ID = "test_user_123"


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Backup and restore app.dependency_overrides around each test.

    Prevents leakage of mocked dependencies between tests.
    """
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _override_get_current_user():
    return {"uid": TEST_USER_ID}


def _override_get_current_user_not_found():
    return {"uid": "other_user"}


# ═════════════════════════════════════════════════════════════════════════════
# 1. Happy Path — Itinerary with Days and Stops
# ═════════════════════════════════════════════════════════════════════════════


class TestGetItineraryEndpoint:
    """GET /api/v1/itinerary/{trip_id} returns proper ItineraryResponse."""

    @pytest.mark.asyncio
    async def test_get_itinerary_returns_days_and_stops(self, db_session):
        """
        Given a trip with an itinerary containing days with stops,
        when we call GET /api/v1/itinerary/{trip_id},
        then we get a properly nested response with all data.
        """
        # ── 1. Seed the database ──────────────────────────────────────────
        # Create trip
        trip = Trip(
            trip_id="test_trip_001",
            user_id=TEST_USER_ID,
            destination="Cairo",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 4),
        )
        db_session.add(trip)

        # Create itinerary
        itinerary = Itinerary(
            itinerary_id="test_itinerary_001",
            trip_id="test_trip_001",
        )
        db_session.add(itinerary)

        # Create days with stops
        day1 = Day(
            day_id="day_001",
            itinerary_id="test_itinerary_001",
            day_number=1,
            date=date(2026, 7, 1),
            theme="Pyramids Day",
        )
        db_session.add(day1)

        day2 = Day(
            day_id="day_002",
            itinerary_id="test_itinerary_001",
            day_number=2,
            date=date(2026, 7, 2),
            theme="Museums & Markets",
        )
        db_session.add(day2)

        # Stops for day 1
        stop1 = ItineraryStop(
            stop_id="stop_001",
            day_id="day_001",
            place_snapshot={
                "name": "Pyramids of Giza",
                "category": "attractions",
                "lat": 29.9792,
                "lon": 31.1342,
            },
            duration_minutes=180,
            order_in_day=1,
            time_of_day=TimeOfDay.MORNING,
            estimated_cost=20.0,
            ai_notes="Must-see ancient wonder",
            status=StopStatus.planned,
        )
        db_session.add(stop1)

        stop2 = ItineraryStop(
            stop_id="stop_002",
            day_id="day_001",
            place_snapshot={"name": "Great Sphinx", "category": "attractions"},
            duration_minutes=60,
            order_in_day=2,
            time_of_day=TimeOfDay.MORNING,
            status=StopStatus.planned,
        )
        db_session.add(stop2)

        # Stops for day 2
        stop3 = ItineraryStop(
            stop_id="stop_003",
            day_id="day_002",
            place_snapshot={
                "name": "Egyptian Museum",
                "category": "attractions",
            },
            duration_minutes=150,
            order_in_day=1,
            time_of_day=TimeOfDay.MORNING,
            status=StopStatus.planned,
        )
        db_session.add(stop3)

        await db_session.commit()

        # ── 2. Override dependencies ──────────────────────────────────────
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        # ── 3. Call the endpoint ──────────────────────────────────────────
        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_001")

        # ── 4. Assertions ─────────────────────────────────────────────────
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
        data = response.json()

        # Top-level itinerary fields
        assert data["itinerary_id"] == "test_itinerary_001"
        assert data["trip_id"] == "test_trip_001"
        assert data["version_number"] == 1
        assert data["status"] == "draft"

        # Days
        assert len(data["days"]) == 2
        day1_resp = data["days"][0]
        assert day1_resp["day_number"] == 1
        assert day1_resp["theme"] == "Pyramids Day"
        assert day1_resp["day_id"] == "day_001"

        day2_resp = data["days"][1]
        assert day2_resp["day_number"] == 2
        assert day2_resp["theme"] == "Museums & Markets"

        # Stops on day 1 (ordered by order_in_day)
        assert len(day1_resp["stops"]) == 2
        s1 = day1_resp["stops"][0]
        assert s1["stop_id"] == "stop_001"
        assert s1["place_snapshot"]["name"] == "Pyramids of Giza"
        assert s1["duration_minutes"] == 180
        assert s1["order_in_day"] == 1
        assert s1["time_of_day"] == "morning"
        assert s1["estimated_cost"] == 20.0
        assert s1["ai_notes"] == "Must-see ancient wonder"
        assert s1["status"] == "planned"

        s2 = day1_resp["stops"][1]
        assert s2["stop_id"] == "stop_002"
        assert s2["place_snapshot"]["name"] == "Great Sphinx"
        assert s2["duration_minutes"] == 60
        assert s2["order_in_day"] == 2

        # Stops on day 2
        assert len(day2_resp["stops"]) == 1
        s3 = day2_resp["stops"][0]
        assert s3["place_snapshot"]["name"] == "Egyptian Museum"
        assert s3["duration_minutes"] == 150
        assert s3["order_in_day"] == 1

    @pytest.mark.asyncio
    async def test_get_itinerary_trip_not_found(self, db_session):
        """Non-existent trip_id → 404."""
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/nonexistent_trip")

        assert response.status_code == 404
        assert response.json()["detail"] == "Trip not found"

    @pytest.mark.asyncio
    async def test_get_itinerary_wrong_user(self, db_session):
        """Trip belongs to another user → 404 (not found, not forbidden)."""
        # Create trip for another user
        trip = Trip(
            trip_id="test_trip_002",
            user_id="other_user",
            destination="Cairo",
        )
        db_session.add(trip)
        itinerary = Itinerary(
            itinerary_id="test_itinerary_002",
            trip_id="test_trip_002",
        )
        db_session.add(itinerary)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_002")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_itinerary_no_itinerary_yet(self, db_session):
        """Trip exists but has no itinerary → 404."""
        trip = Trip(
            trip_id="test_trip_003",
            user_id=TEST_USER_ID,
            destination="Cairo",
        )
        db_session.add(trip)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_003")

        assert response.status_code == 404
        assert response.json()["detail"] == "No itinerary found for this trip"

    @pytest.mark.asyncio
    async def test_get_itinerary_unauthenticated(self, db_session):
        """No auth → 401 or 403 (depends on auth middleware)."""
        # Clear all overrides to test actual auth
        app.dependency_overrides.clear()
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_001")

        # Without a valid token, Firebase auth should fail
        assert response.status_code in (401, 403, 422), (
            f"Expected auth error, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_get_itinerary_returns_hotel_stops_correctly(self, db_session):
        """
        Accommodation suggestions stored as stops should appear in the response
        with category "hotel" and time_of_day "night".
        """
        trip = Trip(trip_id="test_trip_004", user_id=TEST_USER_ID, destination="Cairo")
        db_session.add(trip)
        itinerary = Itinerary(itinerary_id="test_itinerary_004", trip_id="test_trip_004")
        db_session.add(itinerary)
        day = Day(day_id="day_004", itinerary_id="test_itinerary_004", day_number=1)
        db_session.add(day)
        activity = ItineraryStop(
            stop_id="stop_004a",
            day_id="day_004",
            place_snapshot={"name": "Egyptian Museum", "category": "attractions"},
            order_in_day=1,
            time_of_day=TimeOfDay.MORNING,
            duration_minutes=150,
            status=StopStatus.planned,
        )
        db_session.add(activity)
        hotel = ItineraryStop(
            stop_id="stop_004b",
            day_id="day_004",
            place_snapshot={"name": "Marriott Mena House", "category": "hotel"},
            order_in_day=2,
            time_of_day=TimeOfDay.NIGHT,
            status=StopStatus.planned,
        )
        db_session.add(hotel)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_004")
        assert response.status_code == 200

        data = response.json()
        stops = data["days"][0]["stops"]
        assert len(stops) == 2
        assert stops[0]["place_snapshot"]["category"] == "attractions"
        assert stops[1]["place_snapshot"]["category"] == "hotel"
        assert stops[1]["time_of_day"] == "night"

    @pytest.mark.asyncio
    async def test_get_itinerary_days_with_empty_stops(self, db_session):
        """Days with no stops should return empty list, not null."""
        trip = Trip(trip_id="test_trip_005", user_id=TEST_USER_ID, destination="Cairo")
        db_session.add(trip)
        itinerary = Itinerary(itinerary_id="test_itinerary_005", trip_id="test_trip_005")
        db_session.add(itinerary)
        day = Day(day_id="day_005", itinerary_id="test_itinerary_005", day_number=1, theme="Empty Day")
        db_session.add(day)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_db] = lambda: db_session

        client = TestClient(app)
        response = client.get("/api/v1/itinerary/test_trip_005")
        assert response.status_code == 200

        data = response.json()
        assert len(data["days"]) == 1
        assert data["days"][0]["stops"] == [], "Empty stops list expected [] not None"
        assert data["days"][0]["theme"] == "Empty Day"
