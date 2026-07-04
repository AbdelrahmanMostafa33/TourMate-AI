"""
Integration tests for traveler_persona update — requirement #08.

Tests:

  PUT /users/profile
    - Update traveler_persona directly
    - Update other profile fields (full_name, phone_number, home_city)
    - Partial update (only traveler_persona, others unchanged)
    - Returns 404 when user not found
    - Requires auth

  GET /users/profile  (read-back verification)
    - Returns traveler_persona after update
    - Returns correct value
    - Includes trip_profile when trip_id is provided
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.profile import TripProfile
from app.models.trip import Trip
from app.models.enums import BudgetLevel, TravelStyle, TripPace


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID  = "persona_user_001"
OTHER_USER_ID = "persona_other_001"
TRIP_ID       = "persona_trip_001"
PROFILE_ID    = "persona_profile_001"


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
    """Seed a user with some profile data."""
    user = User(
        user_id=TEST_USER_ID,
        email="persona@tourmate.com",
        full_name="Persona User",
        phone_number="+201234567890",
        home_city="Alexandria",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other_persona@tourmate.com",
        full_name="Other Persona User",
    )
    db_session.add(other)
    await db_session.commit()


@pytest.fixture
async def seeded_user_with_trip_profile(db_session, seeded_user) -> None:
    """Seed user + trip + TripProfile for profile read-back test."""
    trip = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        trip_name="Persona Test Trip",
        destination="Cairo",
    )
    db_session.add(trip)

    profile = TripProfile(
        profile_id=PROFILE_ID,
        trip_id=TRIP_ID,
        budget_level=BudgetLevel.MODERATE,
        travel_style=TravelStyle.CULTURAL,
        pace=TripPace.MODERATE,
        interests=["history", "art"],
        food_preferences=["local cuisine"],
        accommodation_preferences=["boutique hotel"],
    )
    db_session.add(profile)
    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: PUT /users/profile — update traveler_persona
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUpdateTravelerPersona:
    """PUT /users/profile — update traveler_persona directly."""

    async def test_update_traveler_persona_successfully(
        self, db_session, seeded_user,
    ):
        """Setting traveler_persona via PUT /users/profile works."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "A budget-conscious cultural explorer who loves history and local cuisine."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] == (
            "A budget-conscious cultural explorer who loves history and local cuisine."
        )

    async def test_update_multiple_fields(
        self, db_session, seeded_user,
    ):
        """Updating multiple profile fields at once."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/users/profile",
            json={
                "full_name": "Updated Name",
                "phone_number": "+201111111111",
                "home_city": "Cairo",
                "traveler_persona": "An adventure-loving solo traveler.",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["phone_number"] == "+201111111111"
        assert data["home_city"] == "Cairo"
        assert data["traveler_persona"] == "An adventure-loving solo traveler."

    async def test_partial_update_only_traveler_persona(
        self, db_session, seeded_user,
    ):
        """Sending only traveler_persona leaves other fields unchanged."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "A luxury relaxation seeker."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] == "A luxury relaxation seeker."
        assert data["full_name"] == "Persona User"  # unchanged
        assert data["phone_number"] == "+201234567890"  # unchanged
        assert data["home_city"] == "Alexandria"  # unchanged

    async def test_update_traveler_persona_empty_string(
        self, db_session, seeded_user,
    ):
        """Setting traveler_persona to empty string is allowed."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": ""},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] == ""

    async def test_update_traveler_persona_returns_404_for_missing_user(
        self, db_session,
    ):
        """Non-existent user returns 404 (no user seeded)."""
        # Don't use seeded_user fixture — no user exists
        # But auth returns TEST_USER_ID which has no matching DB row
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "Any persona"},
        )

        assert response.status_code == 404

    async def test_update_traveler_persona_requires_auth(
        self, db_session, seeded_user,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "A test persona."},
        )
        assert response.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: GET /users/profile — read back traveler_persona
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetTravelerPersona:
    """GET /users/profile — verify traveler_persona is returned."""

    async def test_get_profile_returns_traveler_persona(
        self, db_session, seeded_user,
    ):
        """After updating, traveler_persona is readable via GET."""
        client = _make_client(db_session)

        # First update
        client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "A cultural foodie exploring Egypt."},
        )

        # Then read back
        response = client.get("/api/v1/users/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] == "A cultural foodie exploring Egypt."

    async def test_get_profile_returns_null_when_not_set(
        self, db_session, seeded_user,
    ):
        """Before setting, traveler_persona is None."""
        client = _make_client(db_session)
        response = client.get("/api/v1/users/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] is None

    async def test_get_profile_includes_trip_profile(
        self, db_session, seeded_user_with_trip_profile,
    ):
        """GET /users/profile?trip_id=... includes trip_profile."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/users/profile?trip_id={TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["trip_profile"] is not None
        assert data["trip_profile"]["profile_id"] == PROFILE_ID
        assert data["trip_profile"]["trip_id"] == TRIP_ID
        assert data["trip_profile"]["budget_level"] == BudgetLevel.MODERATE.value
        assert data["trip_profile"]["travel_style"] == TravelStyle.CULTURAL.value
        assert data["trip_profile"]["pace"] == TripPace.MODERATE.value
        assert "history" in data["trip_profile"]["interests"]
        assert "local cuisine" in data["trip_profile"]["food_preferences"]
        assert "boutique hotel" in data["trip_profile"]["accommodation_preferences"]

    async def test_get_profile_returns_404_for_missing_user(
        self, db_session,
    ):
        """No user in DB returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/users/profile")
        assert response.status_code == 404

    async def test_get_profile_requires_auth(
        self, db_session, seeded_user,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/users/profile")
        assert response.status_code in (401, 403, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests: GET /users/profile/full — full profile endpoint
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetFullProfile:
    """GET /users/profile/full — full user profile."""

    async def test_full_profile_returns_traveler_persona(
        self, db_session, seeded_user,
    ):
        """Full profile endpoint also returns traveler_persona."""
        client = _make_client(db_session)

        client.put(
            "/api/v1/users/profile",
            json={"traveler_persona": "A full profile persona."},
        )

        response = client.get("/api/v1/users/profile/full")

        assert response.status_code == 200
        data = response.json()
        assert data["traveler_persona"] == "A full profile persona."
        assert data["trip_profile"] is None  # full profile doesn't include trip_profile

    async def test_full_profile_requires_auth(
        self, db_session, seeded_user,
    ):
        """No auth returns 401/403/422."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/users/profile/full")
        assert response.status_code in (401, 403, 422)
