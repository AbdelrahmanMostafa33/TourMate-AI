"""
Integration tests for reviews.py route endpoints.

Tests cover requirements #19, #20:
    #19: Create, read, update, delete reviews — one review per user per place
    #20: Like/unlike reviews, view own review history

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
from app.core.security import get_current_user, get_optional_user
from app.models.user import User
from app.models.place import Place
from app.models.review import Review, ReviewLike
from app.models.enums import PlaceCategory
from sqlalchemy import update


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_USER_ID = "review_test_user"
OTHER_USER_ID = "other_review_user"
PLACE_ID = "place_to_review"
REVIEW_ID = "existing_review_001"


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
    """Return a callable that returns a mock Firebase user dict."""
    return lambda: {"uid": uid, "email": f"{uid}@tourmate.com"}


def _mock_other_user():
    """Return a callable for a different user."""
    return lambda: {"uid": OTHER_USER_ID, "email": f"{OTHER_USER_ID}@tourmate.com"}


def _make_client(db_session, user_override=None, optional_user_override=None):
    """Create a TestClient with dependency overrides for auth + db + optional auth."""
    overrides = {}
    if user_override is not None:
        overrides[get_current_user] = user_override
    else:
        overrides[get_current_user] = _mock_current_user()
    # Some endpoints use get_optional_user — set it to match the current user by default
    if optional_user_override is not None:
        overrides[get_optional_user] = optional_user_override
    else:
        overrides[get_optional_user] = _mock_current_user()
    overrides[get_db] = lambda: db_session
    app.dependency_overrides.update(overrides)
    return TestClient(app)


@pytest.fixture
async def seeded_db(db_session) -> None:
    """Seed the database with a test user, a second user, and a place."""
    user = User(
        user_id=TEST_USER_ID,
        email="review_user@tourmate.com",
        full_name="Review Test User",
    )
    db_session.add(user)

    other = User(
        user_id=OTHER_USER_ID,
        email="other_user@tourmate.com",
        full_name="Other Review User",
    )
    db_session.add(other)

    place = Place(
        place_id=PLACE_ID,
        name="Test Attraction",
        category=PlaceCategory.attraction,
        rating=4.5,
        city="Cairo",
        country="Egypt",
        lat=30.0,
        lng=31.0,
    )
    db_session.add(place)
    await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/reviews/  —  Create review  (Requirement #19)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestCreateReview:
    """POST /api/v1/reviews/ — Create a review for a place."""

    async def test_create_review_success(self, db_session, seeded_db):
        """Given valid ReviewCreate, return 201 with review data."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/reviews/",
            json={
                "place_id": PLACE_ID,
                "rating": 5,
                "comment": "Amazing place!",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["place_id"] == PLACE_ID
        assert data["user_id"] == TEST_USER_ID
        assert data["rating"] == 5
        assert data["comment"] == "Amazing place!"
        assert data["likes_count"] == 0
        assert "review_id" in data
        assert "review_date" in data

    async def test_create_review_minimal(self, db_session, seeded_db):
        """Creating a review without comment (optional) still succeeds."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 3},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 3
        assert data["comment"] is None

    async def test_create_review_one_per_user_per_place(self, db_session, seeded_db):
        """Creating a second review for the same place returns 409 (requirement #19)."""
        client = _make_client(db_session)

        # First review
        resp1 = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 4, "comment": "Great!"},
        )
        assert resp1.status_code == 201

        # Second review for same place — should fail
        resp2 = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 5, "comment": "Even better!"},
        )
        assert resp2.status_code == 409
        assert "already reviewed" in resp2.json()["detail"].lower()

    async def test_create_review_different_place_allows_second(self, db_session, seeded_db):
        """Different places allow multiple reviews from the same user."""
        # Seed a second place
        place2 = Place(
            place_id="second_place",
            name="Second Attraction",
            category=PlaceCategory.restaurant,
            city="Luxor",
            country="Egypt",
        )
        db_session.add(place2)
        await db_session.commit()

        client = _make_client(db_session)

        resp1 = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 4},
        )
        assert resp1.status_code == 201

        resp2 = client.post(
            "/api/v1/reviews/",
            json={"place_id": "second_place", "rating": 5},
        )
        assert resp2.status_code == 201
        assert resp2.json()["place_id"] == "second_place"

    async def test_create_review_rating_out_of_bounds(self, db_session, seeded_db):
        """Rating below 1 or above 5 returns 422."""
        client = _make_client(db_session)

        # Rating 0
        resp1 = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 0},
        )
        assert resp1.status_code == 422

        # Rating 6
        resp2 = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 6},
        )
        assert resp2.status_code == 422

    async def test_create_review_missing_place_id_returns_422(self, db_session, seeded_db):
        """Missing required place_id field returns 422."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/reviews/",
            json={"rating": 4},
        )
        assert response.status_code == 422

    async def test_create_review_without_auth_returns_401(self, db_session, seeded_db):
        """Creating a review without auth returns 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 4},
        )
        assert response.status_code == 401

    async def test_create_review_other_user_can_review_same_place(self, db_session, seeded_db):
        """Different user can review the same place (one-per-user, not global)."""
        # User A reviews
        client_a = _make_client(db_session)
        resp_a = client_a.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 5},
        )
        assert resp_a.status_code == 201

        # User B reviews the same place
        client_b = _make_client(db_session, _mock_other_user())
        resp_b = client_b.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 3},
        )
        assert resp_b.status_code == 201
        assert resp_b.json()["user_id"] == OTHER_USER_ID


# ═══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/v1/reviews/  —  Get reviews for a place (Requirement #19)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetReviewsForPlace:
    """GET /api/v1/reviews/place/{place_id} — List reviews with summary."""

    async def _seed_reviews(self, db_session):
        """Seed 2 reviews from different users."""
        db_session.add(Review(
            review_id="rev_001",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=5,
            comment="Excellent!",
        ))
        db_session.add(Review(
            review_id="rev_002",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID,
            rating=3,
            comment="Decent.",
        ))
        await db_session.commit()

    async def test_get_reviews_returns_list_with_summary(self, db_session, seeded_db):
        """Returns reviews list with total, average rating, and likes_count."""
        await self._seed_reviews(db_session)

        client = _make_client(db_session)
        response = client.get(f"/api/v1/reviews/place/{PLACE_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["place_id"] == PLACE_ID
        assert data["total_reviews"] == 2
        assert data["average_rating"] == 4.0  # (5 + 3) / 2
        assert len(data["reviews"]) == 2

        # Most recent first (rev_002 has later timestamp by default)
        names = {r["review_id"] for r in data["reviews"]}
        assert "rev_001" in names
        assert "rev_002" in names

        # Each review includes likes_count
        for review in data["reviews"]:
            assert "likes_count" in review
            assert review["likes_count"] >= 0

    async def test_get_reviews_no_reviews(self, db_session, seeded_db):
        """Place with no reviews returns empty list."""
        client = _make_client(db_session)
        response = client.get(f"/api/v1/reviews/place/{PLACE_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["total_reviews"] == 0
        assert data["average_rating"] is None
        assert data["reviews"] == []

    async def test_get_reviews_includes_user_name(self, db_session, seeded_db):
        """Each review includes the reviewer's full_name."""
        await self._seed_reviews(db_session)

        client = _make_client(db_session)
        response = client.get(f"/api/v1/reviews/place/{PLACE_ID}")

        data = response.json()
        names = {r["user_name"] for r in data["reviews"]}
        assert "Review Test User" in names
        assert "Other Review User" in names

    async def test_get_reviews_shows_liked_by_user_when_authenticated(self, db_session, seeded_db):
        """Authenticated user sees which reviews they liked."""
        await self._seed_reviews(db_session)

        # User A likes rev_002 (written by Other User)
        db_session.add(ReviewLike(user_id=TEST_USER_ID, review_id="rev_002"))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get(f"/api/v1/reviews/place/{PLACE_ID}")

        data = response.json()
        reviews_by_id = {r["review_id"]: r for r in data["reviews"]}
        assert reviews_by_id["rev_002"]["liked_by_user"] is True, (
            "User liked rev_002, so liked_by_user should be True"
        )
        assert reviews_by_id["rev_001"]["liked_by_user"] is False

    async def test_get_reviews_liked_by_user_none_when_unauthenticated(self, db_session, seeded_db):
        """Unauthenticated user — liked_by_user is False for all."""
        await self._seed_reviews(db_session)

        # Override both get_current_user and get_optional_user to return None
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        if get_optional_user in app.dependency_overrides:
            del app.dependency_overrides[get_optional_user]
        client = TestClient(app)

        response = client.get(f"/api/v1/reviews/place/{PLACE_ID}")

        assert response.status_code == 200
        data = response.json()
        for review in data["reviews"]:
            assert review["liked_by_user"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GET /api/v1/reviews/my-reviews  —  View own reviews  (Requirement #20)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetMyReviews:
    """GET /api/v1/reviews/my-reviews — Current user's review history."""

    async def _seed_reviews(self, db_session):
        """Seed reviews for TEST_USER_ID and OTHER_USER_ID."""
        db_session.add(Review(
            review_id="my_rev_1", user_id=TEST_USER_ID, place_id=PLACE_ID,
            rating=5, comment="Love it!",
        ))
        db_session.add(Review(
            review_id="my_rev_2", user_id=TEST_USER_ID, place_id=PLACE_ID,
            rating=4, comment="Nice.",
        ))
        db_session.add(Review(
            review_id="other_rev", user_id=OTHER_USER_ID, place_id=PLACE_ID,
            rating=2, comment="Meh.",
        ))
        await db_session.commit()

    async def test_get_my_reviews_returns_own_reviews(self, db_session, seeded_db):
        """Only returns reviews by the authenticated user."""
        await self._seed_reviews(db_session)

        client = _make_client(db_session)
        response = client.get("/api/v1/reviews/my-reviews")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        review_ids = {r["review_id"] for r in data}
        assert "my_rev_1" in review_ids
        assert "my_rev_2" in review_ids
        assert "other_rev" not in review_ids

    async def test_get_my_reviews_empty(self, db_session, seeded_db):
        """User with no reviews returns empty list."""
        client = _make_client(db_session)
        response = client.get("/api/v1/reviews/my-reviews")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_my_reviews_without_auth_returns_401(self, db_session, seeded_db):
        """My-reviews endpoint requires auth."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/reviews/my-reviews")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 4. GET /api/v1/reviews/{review_id}  —  Get single review  (Requirement #19)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestGetSingleReview:
    """GET /api/v1/reviews/{review_id} — Get a single review by ID."""

    async def test_get_review_found(self, db_session, seeded_db):
        """Existing review returns full data."""
        db_session.add(Review(
            review_id="single_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=4,
            comment="Nice place!",
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.get("/api/v1/reviews/single_rev")

        assert response.status_code == 200
        data = response.json()
        assert data["review_id"] == "single_rev"
        assert data["rating"] == 4
        assert data["comment"] == "Nice place!"

    async def test_get_review_not_found_returns_404(self, db_session, seeded_db):
        """Non-existent review_id returns 404."""
        client = _make_client(db_session)
        response = client.get("/api/v1/reviews/nonexistent_review")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_review_without_auth_still_works(self, db_session, seeded_db):
        """GET single review is public (no auth required)."""
        db_session.add(Review(
            review_id="public_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=3,
        ))
        await db_session.commit()

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.get("/api/v1/reviews/public_rev")
        assert response.status_code == 200
        assert response.json()["review_id"] == "public_rev"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. PUT /api/v1/reviews/{review_id}  —  Update own review  (Requirement #19)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestUpdateReview:
    """PUT /api/v1/reviews/{review_id} — Update own review."""

    async def _seed_own_review(self, db_session):
        db_session.add(Review(
            review_id="update_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=3,
            comment="Okay.",
        ))
        await db_session.commit()

    async def test_update_rating(self, db_session, seeded_db):
        """Update rating only."""
        await self._seed_own_review(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/update_rev",
            json={"rating": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Okay."  # unchanged

    async def test_update_comment(self, db_session, seeded_db):
        """Update comment only."""
        await self._seed_own_review(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/update_rev",
            json={"comment": "Updated comment!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 3   # unchanged
        assert data["comment"] == "Updated comment!"

    async def test_update_both_fields(self, db_session, seeded_db):
        """Update both rating and comment."""
        await self._seed_own_review(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/update_rev",
            json={"rating": 4, "comment": "Better after update!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 4
        assert data["comment"] == "Better after update!"

    async def test_update_other_users_review_returns_404(self, db_session, seeded_db):
        """Cannot update another user's review (filtered by user_id)."""
        db_session.add(Review(
            review_id="other_rev",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID,
            rating=5,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/other_rev",
            json={"rating": 1},
        )

        # Returns 404 (not 403) because the query filters by user_id
        assert response.status_code == 404

    async def test_update_nonexistent_review_returns_404(self, db_session, seeded_db):
        """Updating a non-existent review returns 404."""
        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/nonexistent",
            json={"rating": 4},
        )
        assert response.status_code == 404

    async def test_update_rating_out_of_bounds_returns_422(self, db_session, seeded_db):
        """Updating with invalid rating returns 422."""
        await self._seed_own_review(db_session)

        client = _make_client(db_session)
        response = client.put(
            "/api/v1/reviews/update_rev",
            json={"rating": 7},
        )
        assert response.status_code == 422

    async def test_update_without_auth_returns_401(self, db_session, seeded_db):
        """Updating a review without auth returns 401."""
        await self._seed_own_review(db_session)

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.put(
            "/api/v1/reviews/update_rev",
            json={"rating": 4},
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 6. POST /api/v1/reviews/{review_id}/like  —  Like/unlike  (Requirement #20)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestLikeReview:
    """POST /api/v1/reviews/{review_id}/like — Toggle like on a review."""

    async def _seed_review(self, db_session):
        db_session.add(Review(
            review_id="likeable_rev",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID,
            rating=4,
            comment="A review to like.",
        ))
        await db_session.commit()

    async def test_like_review_increments_count(self, db_session, seeded_db):
        """Liking a review increments likes_count by 1."""
        await self._seed_review(db_session)

        client = _make_client(db_session)
        response = client.post("/api/v1/reviews/likeable_rev/like")

        assert response.status_code == 200
        data = response.json()
        assert data["likes_count"] == 1

    async def _seed_review_with_like(self, db_session):
        """Seed a review that already has 1 like from TEST_USER_ID."""
        db_session.add(Review(
            review_id="likeable_rev",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID,
            rating=4,
            comment="A review to like.",
            likes_count=1,
        ))
        db_session.add(ReviewLike(user_id=TEST_USER_ID, review_id="likeable_rev"))
        await db_session.commit()

    async def test_unlike_review_decrements_count(self, db_session, seeded_db):
        """Un-liking a review decrements likes_count by 1."""
        await self._seed_review_with_like(db_session)

        client = _make_client(db_session)
        response = client.post("/api/v1/reviews/likeable_rev/like")

        assert response.status_code == 200
        data = response.json()
        assert data["likes_count"] == 0

    async def test_like_own_review_allowed(self, db_session, seeded_db):
        """Users can like their own review (no restriction)."""
        db_session.add(Review(
            review_id="own_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=5,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.post("/api/v1/reviews/own_rev/like")

        assert response.status_code == 200
        assert response.json()["likes_count"] == 1

    async def test_like_nonexistent_review_returns_404(self, db_session, seeded_db):
        """Liking a non-existent review returns 404."""
        client = _make_client(db_session)
        response = client.post("/api/v1/reviews/nonexistent/like")

        assert response.status_code == 404

    async def test_like_without_auth_returns_401(self, db_session, seeded_db):
        """Liking a review without auth returns 401."""
        await self._seed_review(db_session)

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post("/api/v1/reviews/likeable_rev/like")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 7. DELETE /api/v1/reviews/{review_id}  —  Delete own review  (Requirement #19)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestDeleteReview:
    """DELETE /api/v1/reviews/{review_id} — Delete own review."""

    async def test_delete_own_review_success(self, db_session, seeded_db):
        """Deleting own review returns 200 and removes it from DB."""
        db_session.add(Review(
            review_id="deletable_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=4,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/reviews/deletable_rev")

        assert response.status_code == 200
        assert response.json()["message"] == "Review deleted"

        # Verify it's gone from DB
        result = await db_session.execute(
            select(Review).where(Review.review_id == "deletable_rev")
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_other_users_review_returns_404(self, db_session, seeded_db):
        """Cannot delete another user's review (filtered by user_id)."""
        db_session.add(Review(
            review_id="others_rev",
            user_id=OTHER_USER_ID,
            place_id=PLACE_ID,
            rating=3,
        ))
        await db_session.commit()

        client = _make_client(db_session)
        response = client.delete("/api/v1/reviews/others_rev")

        assert response.status_code == 404

    async def test_delete_nonexistent_review_returns_404(self, db_session, seeded_db):
        """Deleting a non-existent review returns 404."""
        client = _make_client(db_session)
        response = client.delete("/api/v1/reviews/nonexistent")

        assert response.status_code == 404

    async def test_delete_without_auth_returns_401(self, db_session, seeded_db):
        """Deleting a review without auth returns 401."""
        db_session.add(Review(
            review_id="auth_rev",
            user_id=TEST_USER_ID,
            place_id=PLACE_ID,
            rating=5,
        ))
        await db_session.commit()

        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.delete("/api/v1/reviews/auth_rev")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Full review lifecycle  (Requirements #19, #20)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestFullReviewLifecycle:
    """End-to-end: create → read → update → like → unlike → delete."""

    async def test_full_review_lifecycle(self, db_session, seeded_db):
        """Complete happy path for a review through its entire lifecycle."""
        client = _make_client(db_session)

        # ── 1. Create review ─────────────────────────────────────────────
        create_resp = client.post(
            "/api/v1/reviews/",
            json={"place_id": PLACE_ID, "rating": 4, "comment": "Good place!"},
        )
        assert create_resp.status_code == 201
        review_id = create_resp.json()["review_id"]

        # ── 2. Get reviews for place ──────────────────────────────────────
        list_resp = client.get(f"/api/v1/reviews/place/{PLACE_ID}")
        assert list_resp.status_code == 200
        assert list_resp.json()["total_reviews"] >= 1

        # ── 3. Get single review ──────────────────────────────────────────
        get_resp = client.get(f"/api/v1/reviews/{review_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["rating"] == 4

        # ── 4. Update review ──────────────────────────────────────────────
        update_resp = client.put(
            f"/api/v1/reviews/{review_id}",
            json={"rating": 5, "comment": "Updated — even better!"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["rating"] == 5
        assert update_resp.json()["comment"] == "Updated — even better!"

        # ── 5. Like review ────────────────────────────────────────────────
        like_resp = client.post(f"/api/v1/reviews/{review_id}/like")
        assert like_resp.status_code == 200
        assert like_resp.json()["likes_count"] == 1

        # ── 6. Unlike review ──────────────────────────────────────────────
        unlike_resp = client.post(f"/api/v1/reviews/{review_id}/like")
        assert unlike_resp.status_code == 200
        assert unlike_resp.json()["likes_count"] == 0

        # ── 7. Get my reviews ─────────────────────────────────────────────
        my_resp = client.get("/api/v1/reviews/my-reviews")
        assert my_resp.status_code == 200
        assert len(my_resp.json()) >= 1

        # ── 8. Delete review ──────────────────────────────────────────────
        delete_resp = client.delete(f"/api/v1/reviews/{review_id}")
        assert delete_resp.status_code == 200

        # ── 9. Verify deletion ────────────────────────────────────────────
        get_deleted = client.get(f"/api/v1/reviews/{review_id}")
        assert get_deleted.status_code == 404
