"""
Integration tests for the dedicated Itinerary endpoint.

Covers:
  GET /api/v1/itinerary/{trip_id}  — Get full itinerary with nested days and stops

Requirement #22: The itinerary endpoint must expose the full trip plan
(Itinerary → Days → Stops) with all relevant fields, proper ordering,
and correct access controls.
"""

from datetime import date, datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.user import User
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation
from app.models.enums import (
    ItineraryStatus, StopStatus, TravelMode, TimeOfDay,
    ConversationStatus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID    = "itin_test_user_001"
OTHER_USER_ID   = "itin_test_other_001"
TRIP_ID         = "itin_test_trip_001"
TRIP_ID_NO_ITIN = "itin_test_no_itin_001"
ITIN_ID         = "itin_test_itin_001"
DAY_1_ID        = "itin_test_day_1"
DAY_2_ID        = "itin_test_day_2"
STOP_1_ID       = "itin_test_stop_1"
STOP_2_ID       = "itin_test_stop_2"
STOP_3_ID       = "itin_test_stop_3"
CONVERSATION_ID = "itin_test_conv_001"


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _mock_current_user():
    return {"uid": TEST_USER_ID}


def _make_client(db_session, user_override=None):
    overrides = {}
    overrides[get_current_user] = user_override or _mock_current_user
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture
async def seeded_user(db_session) -> None:
    """Seed a minimal user for 404/ownership tests."""
    user = User(
        user_id=TEST_USER_ID,
        email="itin_test@tourmate.com",
        full_name="Itinerary Test User",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other@tourmate.com",
        full_name="Other User",
    )
    db_session.add(other)
    await db_session.commit()


@pytest.fixture
async def seeded_trip_without_itinerary(db_session, seeded_user) -> None:
    """Seed a trip with NO itinerary — for 404 tests."""
    trip = Trip(
        trip_id=TRIP_ID_NO_ITIN,
        user_id=TEST_USER_ID,
        trip_name="No Itinerary Trip",
        destination="Aswan",
    )
    db_session.add(trip)
    await db_session.commit()


@pytest.fixture
async def seeded_full_itinerary(db_session, seeded_user) -> None:
    """Seed a trip with a full itinerary including 2 days and 3 stops."""
    # ── Trip ───────────────────────────────────────────────────────────
    trip = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        trip_name="Itinerary Test Trip",
        destination="Cairo",
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 3),
    )
    db_session.add(trip)

    # ── Itinerary ──────────────────────────────────────────────────────
    itinerary = Itinerary(
        itinerary_id=ITIN_ID,
        trip_id=TRIP_ID,
        version_number=2,
        description="Updated itinerary based on user feedback",
        status=ItineraryStatus.active,
    )
    db_session.add(itinerary)

    # ── Day 1 ──────────────────────────────────────────────────────────
    day1 = Day(
        day_id=DAY_1_ID,
        itinerary_id=ITIN_ID,
        day_number=1,
        date=date(2026, 10, 1),
        theme="Historical Cairo",
        description="Explore the rich history of Cairo",
    )
    db_session.add(day1)

    # ── Day 1 Stops ────────────────────────────────────────────────────
    stop1 = ItineraryStop(
        stop_id=STOP_1_ID,
        day_id=DAY_1_ID,
        place_id=None,  # no DB place — snapshot-only
        place_snapshot={
            "name": "Egyptian Museum",
            "category": "attraction",
            "sub_category": "museum",
            "lat": 30.0478,
            "lon": 31.2336,
            "rating": 4.7,
            "address": "Tahrir Square, Cairo",
            "description": "Home of Tutankhamun's treasures",
            "phone": "+20-2-1234567",
            "website": "https://egyptianmuseum.gov.eg",
            "photo": "https://example.com/egyptian_museum.jpg",
            "maps_link": "https://maps.google.com/?q=Egyptian+Museum",
        },
        duration_minutes=120,
        order_in_day=1,
        time_of_day=TimeOfDay.MORNING,
        minutes_from_prev_stop=None,
        travel_mode=None,
        estimated_cost=20.0,
        ai_notes="Must-see museum with an incredible collection of artifacts.",
        status=StopStatus.planned,
    )
    db_session.add(stop1)

    stop2 = ItineraryStop(
        stop_id=STOP_2_ID,
        day_id=DAY_1_ID,
        place_snapshot={
            "name": "Khan El Khalili",
            "category": "attraction",
            "sub_category": "market",
            "lat": 30.0478,
            "lon": 31.2336,
            "rating": 4.5,
        },
        duration_minutes=90,
        order_in_day=2,
        time_of_day=TimeOfDay.AFTERNOON,
        minutes_from_prev_stop=15,
        travel_mode=TravelMode.walking,
        estimated_cost=0.0,
        ai_notes="Famous bazaar for souvenirs and local crafts.",
        status=StopStatus.planned,
    )
    db_session.add(stop2)

    # ── Day 2 ──────────────────────────────────────────────────────────
    day2 = Day(
        day_id=DAY_2_ID,
        itinerary_id=ITIN_ID,
        day_number=2,
        date=date(2026, 10, 2),
        theme="Pyramids & Modern Cairo",
        description="Visit the Giza plateau and enjoy modern Cairo",
    )
    db_session.add(day2)

    # ── Day 2 Stops ────────────────────────────────────────────────────
    stop3 = ItineraryStop(
        stop_id=STOP_3_ID,
        day_id=DAY_2_ID,
        place_snapshot={
            "name": "Pyramids of Giza",
            "category": "attraction",
            "sub_category": "historic",
            "lat": 29.9792,
            "lon": 31.1342,
            "rating": 4.8,
        },
        duration_minutes=180,
        order_in_day=1,
        time_of_day=TimeOfDay.MORNING,
        minutes_from_prev_stop=None,
        travel_mode=TravelMode.driving,
        estimated_cost=30.0,
        ai_notes="Iconic pyramids — one of the Seven Wonders.",
        status=StopStatus.planned,
    )
    db_session.add(stop3)

    # ── Conversation (for trip linking) ─────────────────────────────────
    conv = Conversation(
        conversation_id=CONVERSATION_ID,
        user_id=TEST_USER_ID,
        status=ConversationStatus.active,
    )
    db_session.add(conv)
    trip.conversation_id = CONVERSATION_ID

    await db_session.commit()


@pytest.fixture
async def seeded_multiple_versions(db_session, seeded_user) -> None:
    """Seed a trip with multiple itinerary versions — latest should be returned."""
    trip = Trip(
        trip_id="itin_versions_trip",
        user_id=TEST_USER_ID,
        trip_name="Versions Trip",
        destination="Luxor",
    )
    db_session.add(trip)

    # Older version
    itin_old = Itinerary(
        itinerary_id="itin_old_001",
        trip_id="itin_versions_trip",
        version_number=1,
        description="First draft",
        status=ItineraryStatus.draft,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )
    db_session.add(itin_old)
    day_old = Day(
        day_id="itin_old_day_1",
        itinerary_id="itin_old_001",
        day_number=1,
        theme="Old plan",
    )
    db_session.add(day_old)

    # Newer version
    itin_new = Itinerary(
        itinerary_id="itin_new_001",
        trip_id="itin_versions_trip",
        version_number=2,
        description="Refined plan after feedback",
        status=ItineraryStatus.active,
        created_at=datetime(2026, 2, 1),
        updated_at=datetime(2026, 2, 1),
    )
    db_session.add(itin_new)
    day_new = Day(
        day_id="itin_new_day_1",
        itinerary_id="itin_new_001",
        day_number=1,
        theme="New refined plan",
    )
    db_session.add(day_new)

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: GET /itinerary/{trip_id}
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetItinerary:
    """GET /api/v1/itinerary/{trip_id} — Full itinerary with nested days and stops."""

    async def test_returns_full_itinerary_response(
        self, db_session, seeded_full_itinerary,
    ):
        """Returns ItineraryResponse with all nested days and stops."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        # ── Itinerary fields ───────────────────────────────────────────
        assert data["itinerary_id"] == ITIN_ID
        assert data["trip_id"] == TRIP_ID
        assert data["version_number"] == 2
        assert data["description"] == "Updated itinerary based on user feedback"
        assert data["status"] == ItineraryStatus.active.value
        assert "created_at" in data
        assert "updated_at" in data

        # ── Days ───────────────────────────────────────────────────────
        assert len(data["days"]) == 2
        assert data["days"][0]["day_number"] == 1
        assert data["days"][0]["theme"] == "Historical Cairo"
        assert data["days"][0]["description"] == "Explore the rich history of Cairo"
        assert data["days"][0]["date"] == "2026-10-01"
        assert data["days"][1]["day_number"] == 2
        assert data["days"][1]["theme"] == "Pyramids & Modern Cairo"
        assert data["days"][1]["date"] == "2026-10-02"

    async def test_days_ordered_by_day_number(
        self, db_session, seeded_full_itinerary,
    ):
        """Days are returned in ascending day_number order."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        day_numbers = [d["day_number"] for d in data["days"]]
        assert day_numbers == [1, 2], f"Expected [1, 2], got {day_numbers}"

    async def test_stops_ordered_by_order_in_day(
        self, db_session, seeded_full_itinerary,
    ):
        """Stops within each day are ordered by order_in_day."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        day1_stops = data["days"][0]["stops"]
        assert len(day1_stops) == 2
        assert day1_stops[0]["order_in_day"] == 1
        assert day1_stops[1]["order_in_day"] == 2

        day2_stops = data["days"][1]["stops"]
        assert len(day2_stops) == 1
        assert day2_stops[0]["order_in_day"] == 1

    async def test_stop_response_contains_all_fields(
        self, db_session, seeded_full_itinerary,
    ):
        """Each stop in the response includes all StopResponse fields."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        stop = data["days"][0]["stops"][0]

        assert "stop_id" in stop
        assert "day_id" in stop
        assert "place_id" in stop
        assert "place_snapshot" in stop
        assert "duration_minutes" in stop
        assert "order_in_day" in stop
        assert "time_of_day" in stop
        assert "minutes_from_prev_stop" in stop
        assert "travel_mode" in stop
        assert "estimated_cost" in stop
        assert "ai_notes" in stop
        assert "status" in stop
        assert "created_at" in stop

    async def test_stop_includes_place_snapshot_data(
        self, db_session, seeded_full_itinerary,
    ):
        """Place snapshot is returned with expected fields."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        stop = data["days"][0]["stops"][0]

        snapshot = stop["place_snapshot"]
        assert snapshot is not None
        assert snapshot["name"] == "Egyptian Museum"
        assert snapshot["category"] == "attraction"
        assert snapshot["sub_category"] == "museum"
        assert snapshot["lat"] == 30.0478
        assert snapshot["lon"] == 31.2336
        assert snapshot["rating"] == 4.7
        assert snapshot["address"] == "Tahrir Square, Cairo"
        assert snapshot["phone"] == "+20-2-1234567"
        assert snapshot["website"] == "https://egyptianmuseum.gov.eg"

    async def test_travel_mode_and_time_of_day_are_serialized(
        self, db_session, seeded_full_itinerary,
    ):
        """Enum fields (travel_mode, time_of_day) are serialized as strings."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        # Day 1, stop 2: walking + afternoon
        stop2 = data["days"][0]["stops"][1]
        assert stop2["travel_mode"] == TravelMode.walking.value
        assert stop2["time_of_day"] == TimeOfDay.AFTERNOON.value
        assert stop2["minutes_from_prev_stop"] == 15
        assert stop2["estimated_cost"] == 0.0

        # Day 2, stop 1: driving + morning
        stop3 = data["days"][1]["stops"][0]
        assert stop3["travel_mode"] == TravelMode.driving.value
        assert stop3["time_of_day"] == TimeOfDay.MORNING.value
        assert stop3["minutes_from_prev_stop"] is None
        assert stop3["estimated_cost"] == 30.0

    async def test_returns_missing_fields_as_null(
        self, db_session, seeded_full_itinerary,
    ):
        """Nullable fields (e.g. place_id=None) are returned as null."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        stop = data["days"][0]["stops"][0]

        # This stop has place_id=None (no DB Place record)
        assert stop["place_id"] is None

    async def test_returns_latest_itinerary_version(
        self, db_session, seeded_multiple_versions,
    ):
        """When multiple itinerary versions exist, the latest is returned."""
        client = _make_client(db_session)
        response = client.get("/api/v1/itinerary/itin_versions_trip")

        assert response.status_code == 200
        data = response.json()

        # Should return version 2 (latest)
        assert data["version_number"] == 2
        assert data["description"] == "Refined plan after feedback"
        assert data["status"] == ItineraryStatus.active.value
        assert len(data["days"]) == 1
        assert data["days"][0]["theme"] == "New refined plan"

    async def test_returns_404_when_trip_not_found(
        self, db_session, seeded_full_itinerary,
    ):
        """Non-existent trip returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/itinerary/nonexistent_trip")
        assert response.status_code == 404

    async def test_returns_404_when_no_itinerary(
        self, db_session, seeded_trip_without_itinerary,
    ):
        """Trip with no itinerary returns 404."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/itinerary/{TRIP_ID_NO_ITIN}")
        assert response.status_code == 404
        assert "No itinerary found" in response.text

    async def test_returns_404_for_other_users_trip(
        self, db_session, seeded_full_itinerary,
    ):
        """Other user's trip returns 404 (ownership check)."""
        client = _make_client(db_session, lambda: {"uid": OTHER_USER_ID})
        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")
        assert response.status_code == 404

    async def test_requires_auth(
        self, db_session, seeded_full_itinerary,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/itinerary/{TRIP_ID}")
        assert response.status_code in (401, 403, 422)

    async def test_empty_stops_list_when_day_has_no_stops(
        self, db_session, seeded_user,
    ):
        """A day with no stops returns an empty stops list, not absent."""
        trip = Trip(
            trip_id="empty_stops_trip",
            user_id=TEST_USER_ID,
            destination="Test",
        )
        db_session.add(trip)
        itin = Itinerary(
            itinerary_id="empty_stops_itin",
            trip_id="empty_stops_trip",
        )
        db_session.add(itin)
        day = Day(
            day_id="empty_stops_day",
            itinerary_id="empty_stops_itin",
            day_number=1,
        )
        db_session.add(day)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get("/api/v1/itinerary/empty_stops_trip")

        assert response.status_code == 200
        data = response.json()
        assert len(data["days"]) == 1
        assert data["days"][0]["stops"] == []

    async def test_hotel_stop_serialized_correctly(
        self, db_session, seeded_user,
    ):
        """Hotel stops appear with correct category and time_of_day."""
        trip = Trip(
            trip_id="hotel_stop_trip",
            user_id=TEST_USER_ID,
            destination="Cairo",
        )
        db_session.add(trip)
        itin = Itinerary(
            itinerary_id="hotel_stop_itin",
            trip_id="hotel_stop_trip",
        )
        db_session.add(itin)
        day = Day(
            day_id="hotel_stop_day",
            itinerary_id="hotel_stop_itin",
            day_number=1,
        )
        db_session.add(day)
        activity = ItineraryStop(
            stop_id="hotel_stop_act",
            day_id="hotel_stop_day",
            place_snapshot={"name": "Egyptian Museum", "category": "attractions"},
            order_in_day=1,
            time_of_day=TimeOfDay.MORNING,
            duration_minutes=150,
            status=StopStatus.planned,
        )
        db_session.add(activity)
        hotel = ItineraryStop(
            stop_id="hotel_stop_hotel",
            day_id="hotel_stop_day",
            place_snapshot={"name": "Marriott Mena House", "category": "hotel"},
            order_in_day=2,
            time_of_day=TimeOfDay.NIGHT,
            status=StopStatus.planned,
        )
        db_session.add(hotel)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get("/api/v1/itinerary/hotel_stop_trip")
        assert response.status_code == 200

        data = response.json()
        stops = data["days"][0]["stops"]
        assert len(stops) == 2
        assert stops[0]["place_snapshot"]["category"] == "attractions"
        assert stops[1]["place_snapshot"]["category"] == "hotel"
        assert stops[1]["time_of_day"] == "night"
