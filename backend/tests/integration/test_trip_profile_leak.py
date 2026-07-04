"""
Integration test: TripProfile data must NOT leak to user-facing API responses.

Requirement #07 — TripProfile contains sensitive AI-internal data
(budget_level, travel_style, pace, interests, food_preferences,
accommodation_preferences) that is used solely by the AI engine to
generate recommendations.  This data must never appear in:

  • GET /trips/{trip_id}          (TripResponse)
  • GET /trips/                   (list — TripSummary)
  • GET /trips/{trip_id}/itinerary (TripResponse)

The only endpoint that SHOULD return TripProfile data is the explicit
dedicated endpoint:  GET /trips/{trip_id}/profile  (TripProfileResponse).

We test both the negative (no leak) and positive (authorized endpoint works)
scenarios in a single fixture per class.
"""

from datetime import date
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.user import User
from app.models.profile import TripProfile
from app.models.itinerary import Itinerary, Day
from app.models.enums import BudgetLevel, TravelStyle, TripPace, ConversationStatus


# ═══════════════════════════════════════════════════════════════════════════════
# Shared test constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID   = "leak_test_user_001"
OTHER_USER_ID  = "leak_test_other_001"
TRIP_ID        = "leak_test_trip_001"
PROFILE_ID     = "leak_test_profile_001"

# TripProfile-specific fields that must NOT appear in user-facing endpoints.
# ``updated_at`` is deliberately excluded — ``TripResponse`` has its own
# ``updated_at`` field (the Trip's timestamp), which is a valid user-facing
# field.  Only fields unique to TripProfile (AI-internal data) are listed.
LEAK_FIELDS = {
    "budget_level",
    "travel_style",
    "pace",
    "interests",
    "food_preferences",
    "accommodation_preferences",
    "profile_id",
    "generated_at",
}

# Fields that TripProfileResponse legitimately returns (positive control)
PROFILE_RESPONSE_FIELDS = {
    "profile_id", "trip_id",
    "budget_level", "travel_style", "pace",
    "interests", "food_preferences", "accommodation_preferences",
    "generated_at", "updated_at",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _cleanup_overrides():
    """Backup and restore app.dependency_overrides around each test."""
    backup = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(backup)


def _mock_current_user():
    return {"uid": TEST_USER_ID}


def _make_client(db_session, user_override=None):
    """Create a TestClient with auth + db overrides."""
    overrides = {}
    overrides[get_current_user] = user_override or _mock_current_user
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture
async def seeded_trip_with_profile(db_session) -> None:
    """Seed a user + trip + TripProfile with all fields populated.

    Also seeds a second user + trip (to verify list endpoint returns
    only own trips — and that neither leaks profile data).
    """
    # ── User ────────────────────────────────────────────────────────────
    user = User(
        user_id=TEST_USER_ID,
        email="leak_test@tourmate.com",
        full_name="Leak Test User",
    )
    db_session.add(user)

    # Other user
    other_user = User(
        user_id=OTHER_USER_ID,
        email="other@tourmate.com",
        full_name="Other User",
    )
    db_session.add(other_user)
    await db_session.flush()

    # ── Trip (main) ─────────────────────────────────────────────────────
    trip = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        trip_name="Leak Test Trip",
        destination="Cairo",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 9, 5),
        number_of_travelers=2,
    )
    db_session.add(trip)

    # Itinerary + Day + Stop (needed for itinerary endpoint to succeed)
    itinerary = Itinerary(
        itinerary_id="leak_itin_001",
        trip_id=TRIP_ID,
    )
    db_session.add(itinerary)
    day = Day(
        itinerary_id="leak_itin_001",
        day_number=1,
        date=date(2026, 9, 1),
    )
    db_session.add(day)

    # ── TripProfile — ALL fields populated ──────────────────────────────
    profile = TripProfile(
        profile_id=PROFILE_ID,
        trip_id=TRIP_ID,
        budget_level=BudgetLevel.MODERATE,
        travel_style=TravelStyle.CULTURAL,
        pace=TripPace.MODERATE,
        interests=["history", "art", "food", "architecture"],
        food_preferences=["local cuisine", "street food"],
        accommodation_preferences=["boutique hotel", "riad"],
    )
    db_session.add(profile)

    # ── Other user's trip (should not appear in main user's list) ───────
    other_trip = Trip(
        trip_id="other_leak_trip",
        user_id=OTHER_USER_ID,
        trip_name="Other Trip",
        destination="Luxor",
    )
    db_session.add(other_trip)

    other_profile = TripProfile(
        profile_id="other_leak_profile",
        trip_id="other_leak_trip",
        budget_level=BudgetLevel.LUXURY,
        travel_style=TravelStyle.RELAXATION,
        pace=TripPace.RELAXED,
        interests=["spa", "shopping"],
        food_preferences=["fine dining"],
        accommodation_preferences=["5-star resort"],
    )
    db_session.add(other_profile)

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Single-trip endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetTripDoesNotLeakProfile:
    """GET /trips/{trip_id} — TripResponse must NOT contain TripProfile fields."""

    PROFILE_FIELDS = LEAK_FIELDS

    async def test_get_trip_excludes_all_profile_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """The GET /trips/{trip_id} response must not contain any TripProfile field."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/trips/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        # Verify no TripProfile fields leaked
        leaked = self.PROFILE_FIELDS & data.keys()
        assert not leaked, (
            f"TripProfile fields leaked in GET /trips/{{trip_id}}: {leaked}"
        )

    async def test_get_trip_returns_expected_trip_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """Verify basic trip fields are still present."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/trips/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        assert data["trip_id"] == TRIP_ID
        assert data["trip_name"] == "Leak Test Trip"
        assert data["destination"] == "Cairo"
        assert data["user_id"] == TEST_USER_ID
        assert "itineraries" in data
        assert "pending_bookings_count" in data

    async def test_get_trip_when_profile_loaded_via_relationship(
        self, db_session, seeded_trip_with_profile,
    ):
        """Even if trip_profiles relationship is loaded, it must not leak.

        This test loads the trip with the trip_profiles relationship to
        simulate a scenario where lazy loading or an eager load occurs,
        then verifies the response still excludes profile data.
        """
        # Force-load trip_profiles on the ORM object
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await db_session.execute(
            select(Trip)
            .options(selectinload(Trip.trip_profiles))
            .where(Trip.trip_id == TRIP_ID)
        )
        trip = result.scalar_one()

        # Verify the profile IS loaded on the ORM object
        assert len(trip.trip_profiles) == 1
        profile = trip.trip_profiles[0]
        assert profile.budget_level == BudgetLevel.MODERATE

        # Now hit the API — profile fields must still be absent
        client = _make_client(db_session)
        response = client.get(f"/api/v1/trips/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()

        leaked = self.PROFILE_FIELDS & data.keys()
        assert not leaked, (
            f"TripProfile fields leaked after eager load: {leaked}"
        )


@pytest.mark.asyncio
class TestGetItineraryDoesNotLeakProfile:
    """GET /trips/{trip_id}/itinerary — must NOT contain TripProfile fields."""

    async def test_get_itinerary_excludes_all_profile_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        client = _make_client(db_session)
        response = client.get(f"/api/v1/trips/{TRIP_ID}/itinerary")

        assert response.status_code == 200
        data = response.json()

        # Must return trip+itinerary data
        assert data["trip_id"] == TRIP_ID
        assert "itineraries" in data

        # Must NOT leak TripProfile fields
        leaked = LEAK_FIELDS & data.keys()
        assert not leaked, (
            f"TripProfile fields leaked in GET /trips/{{trip_id}}/itinerary: {leaked}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: Trip list endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestListTripsDoesNotLeakProfile:
    """GET /trips/ — TripSummary list must NOT contain TripProfile fields."""

    async def test_list_trips_excludes_all_profile_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """Each trip in the list must not contain any TripProfile field."""
        client = _make_client(db_session)
        response = client.get("/api/v1/trips/")

        assert response.status_code == 200
        data = response.json()

        # Should see own trip
        assert len(data) >= 1
        own_trip = next((t for t in data if t["trip_id"] == TRIP_ID), None)
        assert own_trip is not None, "Own trip should appear in list"

        # Verify no TripProfile fields on any trip in the list
        for trip_entry in data:
            leaked = LEAK_FIELDS & trip_entry.keys()
            assert not leaked, (
                f"TripProfile fields leaked in GET /trips/ for trip "
                f"{trip_entry.get('trip_id')}: {leaked}"
            )

    async def test_list_trips_excludes_other_users_trips(
        self, db_session, seeded_trip_with_profile,
    ):
        """Other user's trip should not appear in list (regardless of profile)."""
        client = _make_client(db_session)
        response = client.get("/api/v1/trips/")

        assert response.status_code == 200
        data = response.json()
        trip_ids = [t["trip_id"] for t in data]
        assert "other_leak_trip" not in trip_ids, (
            "Other user's trip should not appear in list"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Positive control: dedicated profile endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDedicatedProfileEndpoint:
    """GET /trips/{trip_id}/profile — SHOULD return TripProfile data (positive control)."""

    async def test_profile_endpoint_returns_all_profile_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """The dedicated profile endpoint must return all TripProfile fields."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/trips/{TRIP_ID}/profile")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected profile fields are present
        for field in PROFILE_RESPONSE_FIELDS:
            assert field in data, (
                f"Expected field '{field}' missing from profile endpoint response"
            )

        # Verify specific values match what we seeded
        assert data["profile_id"] == PROFILE_ID
        assert data["trip_id"] == TRIP_ID
        assert data["budget_level"] == BudgetLevel.MODERATE.value
        assert data["travel_style"] == TravelStyle.CULTURAL.value
        assert data["pace"] == TripPace.MODERATE.value
        assert "history" in data["interests"]
        assert "local cuisine" in data["food_preferences"]
        assert "boutique hotel" in data["accommodation_preferences"]

    async def test_profile_endpoint_not_found_without_profile(
        self, db_session,
    ):
        """Trip without a profile returns 404."""
        # Seed a bare trip with no profile
        user = User(
            user_id=TEST_USER_ID,
            email="bare@tourmate.com",
            full_name="Bare User",
        )
        db_session.add(user)
        trip = Trip(
            trip_id="bare_trip_no_profile",
            user_id=TEST_USER_ID,
            destination="Aswan",
        )
        db_session.add(trip)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get("/api/v1/trips/bare_trip_no_profile/profile")
        assert response.status_code == 404

    async def test_profile_endpoint_requires_auth(
        self, db_session, seeded_trip_with_profile,
    ):
        """Profile endpoint requires authentication."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/trips/{TRIP_ID}/profile")
        assert response.status_code in (401, 403, 422)

    async def test_profile_endpoint_requires_ownership(
        self, db_session, seeded_trip_with_profile,
    ):
        """Other user cannot access trip's profile."""
        client = _make_client(
            db_session,
            user_override=lambda: {"uid": OTHER_USER_ID},
        )
        response = client.get(f"/api/v1/trips/{TRIP_ID}/profile")
        assert response.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-check: chat history must not leak profile data via card_data
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestChatHistoryDoesNotLeakProfile:
    """GET /chat/{trip_id}/history — card_data must not contain TripProfile fields."""

    PROFILES_ASSOCIATED_KEYS = {
        "budget_level", "travel_style", "pace",
        "interests", "food_preferences", "accommodation_preferences",
    }

    async def test_chat_history_card_data_excludes_profile(
        self, db_session, seeded_trip_with_profile,
    ):
        """Chat history messages must not embed TripProfile data in card_data."""
        from app.models.chat import Conversation, Message

        # Seed a conversation with a message containing card_data
        conv = Conversation(
            conversation_id="leak_conv_001",
            user_id=TEST_USER_ID,
            status=ConversationStatus.active,
        )
        db_session.add(conv)

        # Link trip to conversation
        from sqlalchemy import select as sa_select
        trip_result = await db_session.execute(
            sa_select(Trip).where(Trip.trip_id == TRIP_ID)
        )
        trip = trip_result.scalar_one()
        trip.conversation_id = "leak_conv_001"

        msg = Message(
            message_id="leak_msg_001",
            conversation_id="leak_conv_001",
            sender="agent",
            content="Here is your itinerary!",
            card_data={
                "itinerary_data": {"destination": "Cairo", "days": []},
                "hotel_options": {"options": [], "message": None},
                "rendered_cards": ["itinerary"],
            },
        )
        db_session.add(msg)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/chat/{TRIP_ID}/history")

        assert response.status_code == 200
        messages = response.json()
        assert len(messages) >= 1

        for msg_data in messages:
            card_data = msg_data.get("card_data")
            if not card_data:
                continue
            # Walk all nested dict values looking for profile keys
            for key, value in _walk_nested(card_data):
                assert key not in self.PROFILES_ASSOCIATED_KEYS, (
                    f"TripProfile key '{key}' leaked in chat history card_data: "
                    f"value={value}"
                )


def _walk_nested(obj, prefix=""):
    """Yield (key, value) pairs from nested dicts/lists."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            full_key = f"{prefix}.{k}" if prefix else k
            yield (full_key, v)
            yield from _walk_nested(v, full_key)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from _walk_nested(item, f"{prefix}[{i}]")


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-check: flight context must not leak TripProfile data
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFlightContextDoesNotLeakProfile:
    """GET /flights/trip/{trip_id}/context — must NOT contain TripProfile fields.

    The ``TripFlightContext`` schema only returns:
      trip_id, trip_name, home_city, home_city_iata,
      destination_city, destination_iata,
      suggested_departure_date, suggested_return_date, suggested_adults

    None of these are TripProfile fields.  The service only queries
    ``Trip`` and ``User`` tables — never ``TripProfile``.
    """

    # These fields are the ONLY ones that should appear in TripFlightContext
    EXPECTED_FLIGHT_CONTEXT_FIELDS = {
        "trip_id", "trip_name",
        "home_city", "home_city_iata",
        "destination_city", "destination_iata",
        "suggested_departure_date", "suggested_return_date",
        "suggested_adults",
    }

    async def test_flight_context_excludes_all_profile_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """Flight context response must not contain any TripProfile field."""
        from unittest.mock import patch

        # The flight context service tries to resolve home_city and destination
        # to IATA codes via amadeus_client.  Mock amadeus_client to avoid
        # real API calls (which would fail in the test environment).
        with patch("app.services.flight_service.amadeus_client") as mock_amadeus:
            mock_amadeus.search_cities.return_value = [
                {
                    "iataCode": "HBE",
                    "name": "BORG EL ARAB",
                    "subType": "AIRPORT",
                    "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
                },
            ]

            client = _make_client(db_session)
            response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")

        assert response.status_code == 200
        data = response.json()

        # Verify no TripProfile fields leaked
        leaked = LEAK_FIELDS & data.keys()
        assert not leaked, (
            f"TripProfile fields leaked in GET /flights/trip/{{trip_id}}/context: {leaked}"
        )

    async def test_flight_context_returns_only_expected_fields(
        self, db_session, seeded_trip_with_profile,
    ):
        """Flight context response contains only TripFlightContext fields."""
        from unittest.mock import patch

        with patch("app.services.flight_service.amadeus_client") as mock_amadeus:
            mock_amadeus.search_cities.return_value = [
                {
                    "iataCode": "HBE",
                    "name": "BORG EL ARAB",
                    "subType": "AIRPORT",
                    "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
                },
            ]

            client = _make_client(db_session)
            response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")

        assert response.status_code == 200
        data = response.json()

        # Every key in the response should be an expected flight context field
        unexpected = set(data.keys()) - self.EXPECTED_FLIGHT_CONTEXT_FIELDS
        assert not unexpected, (
            f"Unexpected fields in flight context response: {unexpected}"
        )

    async def test_flight_context_contains_expected_trip_data(
        self, db_session, seeded_trip_with_profile,
    ):
        """Flight context returns the trip's basic data correctly."""
        from unittest.mock import patch

        with patch("app.services.flight_service.amadeus_client") as mock_amadeus:
            mock_amadeus.search_cities.return_value = [
                {
                    "iataCode": "HBE",
                    "name": "BORG EL ARAB",
                    "subType": "AIRPORT",
                    "address": {"cityName": "ALEXANDRIA", "countryName": "EGYPT"},
                },
            ]

            client = _make_client(db_session)
            response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")

        assert response.status_code == 200
        data = response.json()

        assert data["trip_id"] == TRIP_ID
        assert data["trip_name"] == "Leak Test Trip"
        assert data["destination_city"] == "Cairo"
        assert data["suggested_departure_date"] == "2026-09-01"
        assert data["suggested_return_date"] == "2026-09-05"
        assert data["suggested_adults"] == 2

    async def test_flight_context_requires_auth(
        self, db_session, seeded_trip_with_profile,
    ):
        """Flight context requires authentication."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/flights/trip/{TRIP_ID}/context")
        assert response.status_code in (401, 403, 422)
