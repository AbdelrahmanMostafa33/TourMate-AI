"""
Integration tests for feedback.py route endpoints.

Tests cover requirement #32:
    - Collect user feedback on completed trips and itineraries
    - CRUD operations for feedback
    - Different feedback types (thumbs_up, thumbs_down, rating, comment)
    - Trip-level feedback retrieval

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
from app.models.trip import Trip
from app.models.feedback import Feedback
from app.models.enums import TripStatus, FeedbackType


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID = "feedback_test_user"
OTHER_USER_ID = "other_feedback_user"
TRIP_ID = "feedback_trip_001"
ANOTHER_TRIP_ID = "feedback_trip_002"


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
    """Seed the database with a test user, another user, and 2 trips."""
    user = User(
        user_id=TEST_USER_ID,
        email="feedback_user@tourmate.com",
        full_name="Feedback Test User",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other_feedback@tourmate.com",
        full_name="Other Feedback User",
    )
    db_session.add(other)

    trip1 = Trip(
        trip_id=TRIP_ID,
        user_id=TEST_USER_ID,
        destination="Cairo, Egypt",
        status=TripStatus.completed,
    )
    db_session.add(trip1)

    trip2 = Trip(
        trip_id=ANOTHER_TRIP_ID,
        user_id=TEST_USER_ID,
        destination="Luxor, Egypt",
        status=TripStatus.completed,
    )
    db_session.add(trip2)

    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/feedback/  —  Create feedback  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCreateFeedback:
    """POST /api/v1/feedback/ — Submit feedback on a completed trip."""

    async def test_create_thumbs_up(self, db_session, seeded_db):
        """Creating thumbs_up feedback returns 201."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "thumbs_up",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "thumbs_up"
        assert data["user_id"] == TEST_USER_ID
        assert data["trip_id"] == TRIP_ID
        assert data["rating"] is None
        assert data["comment"] is None
        assert "feedback_id" in data
        assert "submitted_at" in data

    async def test_create_thumbs_down(self, db_session, seeded_db):
        """Creating thumbs_down feedback works."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "thumbs_down",
            },
        )
        assert response.status_code == 201
        assert response.json()["feedback_type"] == "thumbs_down"

    async def test_create_rating_feedback(self, db_session, seeded_db):
        """Feedback with numeric rating (1-5) for a trip."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "rating",
                "rating": 4,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "rating"
        assert data["rating"] == 4

    async def test_create_comment_feedback(self, db_session, seeded_db):
        """Feedback with a written comment."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "comment",
                "comment": "Amazing trip! The itinerary was perfect.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["feedback_type"] == "comment"
        assert data["comment"] == "Amazing trip! The itinerary was perfect."

    async def test_create_feedback_without_trip_id(self, db_session, seeded_db):
        """Feedback can be created without a specific trip_id."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "feedback_type": "thumbs_up",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["trip_id"] is None
        assert data["feedback_type"] == "thumbs_up"

    async def test_create_feedback_missing_type_returns_422(self, db_session, seeded_db):
        """Missing required feedback_type field returns 422."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={"trip_id": TRIP_ID},
        )
        assert response.status_code == 422

    async def test_create_feedback_invalid_type_returns_422(self, db_session, seeded_db):
        """Invalid feedback_type value returns 422."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "INVALID_TYPE",
            },
        )
        assert response.status_code == 422

    async def test_create_feedback_without_auth_returns_401(self, db_session, seeded_db):
        """Creating feedback without auth returns 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": TRIP_ID,
                "feedback_type": "thumbs_up",
            },
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/v1/feedback/  —  Get my feedback  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetMyFeedback:
    """GET /api/v1/feedback/ — Retrieve all feedback by the current user."""

    async def _seed_feedback(self, db_session):
        """Seed 2 feedback entries for TEST_USER_ID and 1 for OTHER_USER_ID.
        Uses explicit timestamps to ensure deterministic ordering."""
        from datetime import datetime

        db_session.add(Feedback(
            feedback_id="fb_my_001",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
            submitted_at=datetime(2026, 7, 1, 10, 0, 0),  # older
        ))
        db_session.add(Feedback(
            feedback_id="fb_my_002",
            user_id=TEST_USER_ID,
            trip_id=ANOTHER_TRIP_ID,
            feedback_type=FeedbackType.comment,
            comment="Great Luxor trip!",
            submitted_at=datetime(2026, 7, 2, 10, 0, 0),  # newer
        ))
        db_session.add(Feedback(
            feedback_id="fb_other_001",
            user_id=OTHER_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_down,
            submitted_at=datetime(2026, 7, 3, 10, 0, 0),
        ))
        await db_session.commit()

    async def test_get_my_feedback_returns_own_only(self, db_session, seeded_db):
        """Only returns feedback by the authenticated user."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/feedback/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        fb_ids = {f["feedback_id"] for f in data}
        assert "fb_my_001" in fb_ids
        assert "fb_my_002" in fb_ids
        assert "fb_other_001" not in fb_ids

    async def test_get_my_feedback_ordered_by_date_desc(self, db_session, seeded_db):
        """Feedback is returned newest first (newest submitted_at first)."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/feedback/")

        data = response.json()
        assert len(data) == 2
        # fb_my_002 has later submitted_at, so it should be first
        assert data[0]["feedback_id"] == "fb_my_002"
        assert data[1]["feedback_id"] == "fb_my_001"

    async def test_get_my_feedback_empty(self, db_session, seeded_db):
        """User with no feedback returns empty list."""
        client = _make_client(db_session)
        response = client.get("/api/v1/feedback/")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_my_feedback_without_auth_returns_401(self, db_session, seeded_db):
        """Getting my feedback requires auth."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/feedback/")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GET /api/v1/feedback/trip/{trip_id}  —  Trip feedback  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetFeedbackForTrip:
    """GET /api/v1/feedback/trip/{trip_id} — Feedback for a specific trip."""

    async def _seed_feedback(self, db_session):
        """Seed feedback for TRIP_ID and ANOTHER_TRIP_ID."""
        db_session.add(Feedback(
            feedback_id="fb_trip_001",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.rating,
            rating=5,
        ))
        db_session.add(Feedback(
            feedback_id="fb_trip_002",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.comment,
            comment="Loved every moment!",
        ))
        # Feedback for a different trip — should not appear
        db_session.add(Feedback(
            feedback_id="fb_other_trip",
            user_id=TEST_USER_ID,
            trip_id=ANOTHER_TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

    async def test_get_feedback_for_trip(self, db_session, seeded_db):
        """Returns only feedback entries for the given trip."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.get(f"/api/v1/feedback/trip/{TRIP_ID}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        fb_ids = {f["feedback_id"] for f in data}
        assert "fb_trip_001" in fb_ids
        assert "fb_trip_002" in fb_ids
        assert "fb_other_trip" not in fb_ids

    async def test_get_feedback_for_trip_empty(self, db_session, seeded_db):
        """Trip with no feedback returns empty list."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/feedback/trip/{TRIP_ID}")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_feedback_for_trip_without_auth_returns_401(self, db_session, seeded_db):
        """Trip feedback endpoint requires auth."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/feedback/trip/{TRIP_ID}")
        assert response.status_code == 401

    async def test_get_feedback_for_trip_own_only(self, db_session, seeded_db):
        """Only returns the current user's feedback for the trip."""
        # Add other user's feedback on the same trip
        db_session.add(Feedback(
            feedback_id="fb_other_same_trip",
            user_id=OTHER_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_down,
        ))
        # Add own feedback
        db_session.add(Feedback(
            feedback_id="fb_own_trip",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/feedback/trip/{TRIP_ID}")

        data = response.json()
        assert len(data) == 1
        assert data[0]["feedback_id"] == "fb_own_trip"
        assert data[0]["feedback_type"] == "thumbs_up"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. PUT /api/v1/feedback/{feedback_id}  —  Update feedback  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUpdateFeedback:
    """PUT /api/v1/feedback/{feedback_id} — Update own feedback."""

    async def _seed_feedback(self, db_session):
        db_session.add(Feedback(
            feedback_id="updatable_fb",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

    async def test_update_feedback_type(self, db_session, seeded_db):
        """Change feedback_type from thumbs_up to thumbs_down."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/feedback/updatable_fb",
            json={"feedback_type": "thumbs_down"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_type"] == "thumbs_down"

    async def test_update_feedback_rating(self, db_session, seeded_db):
        """Add a rating to existing feedback."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/feedback/updatable_fb",
            json={"feedback_type": "rating", "rating": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_type"] == "rating"
        assert data["rating"] == 5

    async def test_update_feedback_comment(self, db_session, seeded_db):
        """Add a comment to existing feedback."""
        await self._seed_feedback(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/feedback/updatable_fb",
            json={"comment": "Changed my mind, it was great!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["comment"] == "Changed my mind, it was great!"
        assert data["feedback_type"] == "thumbs_up"  # unchanged

    async def test_update_other_users_feedback_returns_404(self, db_session, seeded_db):
        """Cannot update another user's feedback."""
        db_session.add(Feedback(
            feedback_id="others_fb",
            user_id=OTHER_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/feedback/others_fb",
            json={"feedback_type": "thumbs_down"},
        )
        assert response.status_code == 404

    async def test_update_nonexistent_feedback_returns_404(self, db_session, seeded_db):
        """Updating non-existent feedback returns 404."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/feedback/nonexistent",
            json={"feedback_type": "thumbs_down"},
        )
        assert response.status_code == 404

    async def test_update_without_auth_returns_401(self, db_session, seeded_db):
        """Updating feedback without auth returns 401."""
        await self._seed_feedback(db_session)

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.put(
            "/api/v1/feedback/updatable_fb",
            json={"feedback_type": "thumbs_down"},
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DELETE /api/v1/feedback/{feedback_id}  —  Delete feedback  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDeleteFeedback:
    """DELETE /api/v1/feedback/{feedback_id} — Delete own feedback."""

    async def test_delete_own_feedback_success(self, db_session, seeded_db):
        """Deleting own feedback returns 200 and removes it from DB."""
        db_session.add(Feedback(
            feedback_id="deletable_fb",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/feedback/deletable_fb")

        assert response.status_code == 200
        assert response.json()["message"] == "Feedback deleted"

        # Verify it's gone from DB
        result = await db_session.execute(
            select(Feedback).where(Feedback.feedback_id == "deletable_fb")
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_other_users_feedback_returns_404(self, db_session, seeded_db):
        """Cannot delete another user's feedback."""
        db_session.add(Feedback(
            feedback_id="others_del",
            user_id=OTHER_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/feedback/others_del")
        assert response.status_code == 404

    async def test_delete_nonexistent_feedback_returns_404(self, db_session, seeded_db):
        """Deleting non-existent feedback returns 404."""
        client = _make_client(db_session)
        response = client.delete("/api/v1/feedback/nonexistent")
        assert response.status_code == 404

    async def test_delete_without_auth_returns_401(self, db_session, seeded_db):
        """Deleting feedback without auth returns 401."""
        db_session.add(Feedback(
            feedback_id="auth_del",
            user_id=TEST_USER_ID,
            trip_id=TRIP_ID,
            feedback_type=FeedbackType.thumbs_up,
        ))
        await db_session.commit()

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.delete("/api/v1/feedback/auth_del")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Full feedback lifecycle  (Requirement #32)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFullFeedbackLifecycle:
    """End-to-end: create → get my feedback → get trip feedback → update → delete."""

    async def test_full_lifecycle(self, db_session, seeded_db):
        """Complete happy path for the feedback feature."""
        client = _make_client(db_session)

        # ── 1. Create thumbs_up for trip 1 ───────────────────────────────
        resp1 = client.post(
            "/api/v1/feedback/",
            json={"trip_id": TRIP_ID, "feedback_type": "thumbs_up"},
        )
        assert resp1.status_code == 201
        fb_id = resp1.json()["feedback_id"]

        # ── 2. Create rating feedback for trip 1 ──────────────────────────
        resp2 = client.post(
            "/api/v1/feedback/",
            json={"trip_id": TRIP_ID, "feedback_type": "rating", "rating": 5},
        )
        assert resp2.status_code == 201

        # ── 3. Create comment feedback for trip 2 ─────────────────────────
        resp3 = client.post(
            "/api/v1/feedback/",
            json={
                "trip_id": ANOTHER_TRIP_ID,
                "feedback_type": "comment",
                "comment": "Wonderful experience!",
            },
        )
        assert resp3.status_code == 201

        # ── 4. Get my feedback — should return all 3 ──────────────────────
        my_resp = client.get("/api/v1/feedback/")
        assert my_resp.status_code == 200
        assert len(my_resp.json()) == 3

        # ── 5. Get feedback for trip 1 — should return 2 ──────────────────
        trip_resp = client.get(f"/api/v1/feedback/trip/{TRIP_ID}")
        assert trip_resp.status_code == 200
        assert len(trip_resp.json()) == 2

        # ── 6. Update the first feedback ──────────────────────────────────
        update_resp = client.put(
            f"/api/v1/feedback/{fb_id}",
            json={"feedback_type": "thumbs_down"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["feedback_type"] == "thumbs_down"

        # ── 7. Delete the first feedback ──────────────────────────────────
        del_resp = client.delete(f"/api/v1/feedback/{fb_id}")
        assert del_resp.status_code == 200

        # ── 8. Verify only 2 feedback remain ──────────────────────────────
        final_resp = client.get("/api/v1/feedback/")
        assert final_resp.status_code == 200
        assert len(final_resp.json()) == 2
