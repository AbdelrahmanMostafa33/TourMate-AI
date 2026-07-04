"""
Integration tests for saved_places.py route endpoints.

Tests cover requirement #21:
    - Bookmark/save places for future reference
    - Add personal notes to saved places
    - List saved places with full place data
    - Unsave/remove saved places

Uses FastAPI TestClient with:
    - In-memory SQLite database (via conftest.py db_session fixture)
    - Mocked get_current_user dependency (no Firebase needed)
    - Dependency override pattern (same as test_flight_routes.py)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.place import Place, HotelDetails, AttractionDetails
from app.models.saved_place import SavedPlace
from app.models.enums import PlaceCategory, AccommodationType


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID = "save_test_user"
OTHER_USER_ID = "other_save_user"
PLACE_ID_1 = "place_attraction_001"
PLACE_ID_2 = "place_hotel_001"


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


def _mock_current_user(uid: str = TEST_USER_ID):
    return lambda: {"uid": uid, "email": f"{uid}@tourmate.com"}


def _make_client(db_session, user_override=None):
    """Create a TestClient with dependency overrides for auth + db."""
    overrides = {}
    if user_override is not None:
        overrides[get_current_user] = user_override
    else:
        overrides[get_current_user] = _mock_current_user()
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture
async def seeded_db(db_session) -> None:
    """Seed the database with a test user, another user, and 2 places (attraction + hotel)."""
    user = User(
        user_id=TEST_USER_ID,
        email="save_user@tourmate.com",
        full_name="Save Test User",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other_save@tourmate.com",
        full_name="Other Save User",
    )
    db_session.add(other)

    # Place 1: Attraction
    place1 = Place(
        place_id=PLACE_ID_1,
        name="Egyptian Museum",
        description="World-famous museum in Tahrir Square",
        category=PlaceCategory.attraction,
        rating=4.7,
        review_count=2000,
        popularity_score=95.0,
        city="Cairo",
        country="Egypt",
        lat=30.0478,
        lng=31.2336,
        address="Tahrir Square, Cairo",
        phone="+202-1234-5678",
        website="https://egyptianmuseum.org",
        price_level=2,
        photo_urls=["https://example.com/museum.jpg"],
    )
    db_session.add(place1)
    db_session.add(AttractionDetails(
        place_id=PLACE_ID_1,
        subcategory="museum",
        entry_fee=200.0,
    ))

    # Place 2: Hotel
    place2 = Place(
        place_id=PLACE_ID_2,
        name="Marriott Mena House",
        category=PlaceCategory.hotel,
        rating=4.6,
        review_count=1500,
        popularity_score=88.0,
        city="Cairo",
        country="Egypt",
        lat=29.9758,
        lng=31.1334,
        address="6 Pyramids Road, Giza",
    )
    db_session.add(place2)
    db_session.add(HotelDetails(
        place_id=PLACE_ID_2,
        star_class=5,
        nightly_rate=250.0,
        amenities=["pool", "spa", "restaurant", "free_wifi"],
        accommodation_type=AccommodationType.luxury,
    ))

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/saved-places/  —  Save a place  (Requirement #21)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestSavePlace:
    """POST /api/v1/saved-places/ — Bookmark a place for future reference."""

    async def test_save_place_success(self, db_session, seeded_db):
        """Saving a place returns 201 with saved place metadata."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["place_id"] == PLACE_ID_1
        assert data["user_id"] == TEST_USER_ID
        assert data["note"] is None
        assert "saved_place_id" in data
        assert "saved_at" in data

        # Verify it's in the DB
        result = await db_session.execute(
            select(SavedPlace).where(
                SavedPlace.user_id == TEST_USER_ID,
                SavedPlace.place_id == PLACE_ID_1,
            )
        )
        sp = result.scalar_one_or_none()
        assert sp is not None

    async def test_save_place_with_note(self, db_session, seeded_db):
        """Saving a place with a personal note stores the note."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/saved-places/",
            json={
                "place_id": PLACE_ID_1,
                "note": "Must visit on my next trip!",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["note"] == "Must visit on my next trip!"
        assert data["place_id"] == PLACE_ID_1

    async def test_save_place_duplicate_returns_409(self, db_session, seeded_db):
        """Saving the same place twice returns 409."""
        client = _make_client(db_session)

        # First save
        resp1 = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert resp1.status_code == 201

        # Second save (same place)
        resp2 = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert resp2.status_code == 409
        assert "already saved" in resp2.json()["detail"].lower()

    async def test_save_place_different_place_allows_second(self, db_session, seeded_db):
        """Saving two different places from the same user works."""
        client = _make_client(db_session)

        resp1 = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_2},
        )
        assert resp2.status_code == 201
        assert resp2.json()["place_id"] == PLACE_ID_2

    async def test_save_place_other_user_can_save_same(self, db_session, seeded_db):
        """Different users can save the same place (unique per user-place pair)."""
        # User A saves
        client_a = _make_client(db_session)
        resp_a = client_a.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert resp_a.status_code == 201

        # User B saves the same place
        client_b = _make_client(db_session, _mock_current_user(OTHER_USER_ID))
        resp_b = client_b.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert resp_b.status_code == 201
        assert resp_b.json()["user_id"] == OTHER_USER_ID

    async def test_save_place_missing_place_id_returns_422(self, db_session, seeded_db):
        """Missing required place_id field returns 422."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/saved-places/",
            json={},
        )
        assert response.status_code == 422

    async def test_save_place_without_auth_returns_401(self, db_session, seeded_db):
        """Saving a place without auth returns 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/v1/saved-places/  —  List saved places  (Requirement #21)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetSavedPlaces:
    """GET /api/v1/saved-places/ — List saved places with full place data."""

    async def _seed_saved(self, db_session):
        """Save 2 places for TEST_USER_ID."""
        db_session.add(SavedPlace(
            saved_place_id="sp_001",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID_1,
            note="Love this museum!",
        ))
        db_session.add(SavedPlace(
            saved_place_id="sp_002",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID_2,
            note="Want to stay here.",
        ))
        await db_session.commit()

    async def test_get_saved_places_returns_list(self, db_session, seeded_db):
        """Returns all saved places for the authenticated user."""
        await self._seed_saved(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        saved_ids = {item["saved_place_id"] for item in data}
        assert "sp_001" in saved_ids
        assert "sp_002" in saved_ids

    async def test_get_saved_places_includes_place_data(self, db_session, seeded_db):
        """Each saved item includes full place details (using 'id' for place_id)."""
        await self._seed_saved(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        data = response.json()
        for item in data:
            assert "place" in item
            place = item["place"]
            # _place_to_dict uses "id" as the key for place_id
            assert "id" in place
            assert place["id"] == item["place_id"]
            assert "name" in place
            assert "category" in place
            assert "rating" in place

    async def test_get_saved_places_includes_attraction_details(self, db_session, seeded_db):
        """Attraction saved places include sub_category."""
        await self._seed_saved(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        data = response.json()
        # Find the attraction
        for item in data:
            if item["place_id"] == PLACE_ID_1:
                assert item["place"]["sub_category"] == "museum"
                break
        else:
            pytest.fail("Attraction place not found in saved places")

    async def test_get_saved_places_includes_hotel_details(self, db_session, seeded_db):
        """Hotel saved places include accommodation_type and amenities."""
        await self._seed_saved(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        data = response.json()
        for item in data:
            if item["place_id"] == PLACE_ID_2:
                assert item["place"]["accommodation_type"] == "luxury"
                assert "pool" in item["place"].get("amenities", [])
                break
        else:
            pytest.fail("Hotel place not found in saved places")

    async def test_get_saved_places_empty_list(self, db_session, seeded_db):
        """User with no saved places returns empty list."""
        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_saved_places_own_only(self, db_session, seeded_db):
        """Only returns the current user's saved places, not other users'."""
        # Save for TEST_USER_ID
        await self._seed_saved(db_session)

        # Save for OTHER_USER_ID
        db_session.add(SavedPlace(
            saved_place_id="sp_other",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID_1,
        ))
        await db_session.commit()

        # As TEST_USER_ID, we should only see sp_001 and sp_002
        client = _make_client(db_session)
        response = client.get("/api/v1/saved-places/")

        data = response.json()
        saved_ids = {item["saved_place_id"] for item in data}
        assert "sp_other" not in saved_ids
        assert len(data) == 2

    async def test_get_saved_places_without_auth_returns_401(self, db_session, seeded_db):
        """Listing saved places requires auth."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/saved-places/")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DELETE /api/v1/saved-places/{saved_place_id}  —  Unsave  (Requirement #21)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUnsavePlace:
    """DELETE /api/v1/saved-places/{saved_place_id} — Remove a saved place."""

    async def test_unsave_own_place_success(self, db_session, seeded_db):
        """Un-saving own saved place returns 200 and removes from DB."""
        # Seed a saved place
        sp = SavedPlace(
            saved_place_id="to_remove",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID_1,
            note="Will remove this",
        )
        db_session.add(sp)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/saved-places/to_remove")

        assert response.status_code == 200
        assert response.json()["message"] == "Saved place removed"

        # Verify it's gone from DB
        result = await db_session.execute(
            select(SavedPlace).where(SavedPlace.saved_place_id == "to_remove")
        )
        assert result.scalar_one_or_none() is None

    async def test_unsave_other_users_place_returns_404(self, db_session, seeded_db):
        """Cannot unsave another user's saved place (filtered by user_id)."""
        sp = SavedPlace(
            saved_place_id="others_remove",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID_1,
        )
        db_session.add(sp)
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/saved-places/others_remove")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_unsave_nonexistent_returns_404(self, db_session, seeded_db):
        """Un-saving a non-existent saved place returns 404."""
        client = _make_client(db_session)
        response = client.delete("/api/v1/saved-places/nonexistent_sp")

        assert response.status_code == 404

    async def test_unsave_without_auth_returns_401(self, db_session, seeded_db):
        """Un-saving a place without auth returns 401."""
        sp = SavedPlace(
            saved_place_id="auth_remove",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID_1,
        )
        db_session.add(sp)
        await db_session.commit()

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.delete("/api/v1/saved-places/auth_remove")
        assert response.status_code == 401

    async def test_unsave_then_resave_works(self, db_session, seeded_db):
        """After unsaving, the same user can save the place again."""
        # Seed a saved place
        sp = SavedPlace(
            saved_place_id="resave_test",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID_1,
        )
        db_session.add(sp)
        await db_session.commit()

        client = _make_client(db_session)

        # Unsave
        del_resp = client.delete("/api/v1/saved-places/resave_test")
        assert del_resp.status_code == 200

        # Re-save (should work since unique constraint is per active record)
        save_resp = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_1},
        )
        assert save_resp.status_code == 201
        assert save_resp.json()["place_id"] == PLACE_ID_1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Full saved place lifecycle  (Requirement #21)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFullSavedPlaceLifecycle:
    """End-to-end: save with note → list with place data → unsave → verify gone."""

    async def test_full_lifecycle(self, db_session, seeded_db):
        """Complete happy path for the saved place feature."""
        client = _make_client(db_session)

        # ── 1. Save a place with a note ─────────────────────────────────
        save_resp = client.post(
            "/api/v1/saved-places/",
            json={
                "place_id": PLACE_ID_1,
                "note": "A must-see attraction!",
            },
        )
        assert save_resp.status_code == 201
        saved_place_id = save_resp.json()["saved_place_id"]
        assert save_resp.json()["note"] == "A must-see attraction!"

        # ── 2. Save a second place ───────────────────────────────────────
        save_resp2 = client.post(
            "/api/v1/saved-places/",
            json={"place_id": PLACE_ID_2},
        )
        assert save_resp2.status_code == 201

        # ── 3. List all saved places ─────────────────────────────────────
        list_resp = client.get("/api/v1/saved-places/")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert len(data) == 2

        # Verify the first saved place has the note
        for item in data:
            if item["saved_place_id"] == saved_place_id:
                assert item["place"]["name"] == "Egyptian Museum"
                break

        # ── 4. Unsave the first place ────────────────────────────────────
        del_resp = client.delete(f"/api/v1/saved-places/{saved_place_id}")
        assert del_resp.status_code == 200

        # ── 5. Verify only 1 saved place remains ─────────────────────────
        list_resp2 = client.get("/api/v1/saved-places/")
        assert list_resp2.status_code == 200
        assert len(list_resp2.json()) == 1
        assert list_resp2.json()[0]["place_id"] == PLACE_ID_2
