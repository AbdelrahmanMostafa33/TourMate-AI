"""
Integration tests for auth.py route endpoints.

Tests cover:
    - POST /api/v1/auth/register         — Firebase-verified user registration (#01)
    - POST /api/v1/auth/login             — Firebase-verified login (auto-create) (#01)
    - POST /api/v1/auth/test-register     — No-auth registration (dev/testing only)
    - Auth guard behavior                 — Missing/expired/invalid token (#01, #02)

Uses FastAPI TestClient with:
    - In-memory SQLite database (via conftest.py db_session fixture)
    - Mocked get_current_user dependency (no Firebase needed)
    - Dependency override pattern (same as test_flight_routes.py)

Note on requirement #02 (token refresh): Token refresh is handled entirely client-side
by the Firebase SDK and has no backend endpoint. Backend auth is stateless — it only
verifies the token on each request. Thus token refresh is not testable on the backend.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

TEST_UID = "firebase_uid_001"
TEST_EMAIL = "test@tourmate.com"


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


def _mock_current_user(uid: str = TEST_UID, email: str = TEST_EMAIL):
    """Return a callable that returns a mock Firebase user dict."""
    return lambda: {"uid": uid, "email": email, "name": "Test User"}



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


# ═══════════════════════════════════════════════════════════════════════════════
# 1. POST /api/v1/auth/register  (Requirement #01)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestRegisterEndpoint:
    """POST /api/v1/auth/register — Create user record after Firebase auth."""

    async def test_register_creates_new_user(self, db_session):
        """Given valid RegisterRequest + Firebase token, create user in DB."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Test User",
                "email": "test@tourmate.com",
                "phone_number": "+201234567890",
                "home_city": "Cairo",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == TEST_UID
        assert data["full_name"] == "Test User"
        assert data["email"] == TEST_EMAIL
        assert data["phone_number"] == "+201234567890"
        assert data["home_city"] == "Cairo"
        assert "registration_date" in data

        # Verify user is persisted in DB
        result = await db_session.execute(
            select(User).where(User.user_id == TEST_UID)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.full_name == "Test User"

    async def test_register_duplicate_user_returns_400(self, db_session):
        """Registering the same Firebase UID twice returns 400."""
        client = _make_client(db_session)

        # First registration
        resp1 = client.post(
            "/api/v1/auth/register",
            json={"full_name": "First", "email": "test@tourmate.com"},
        )
        assert resp1.status_code == 201

        # Second registration (same Firebase UID from token)
        resp2 = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Second", "email": "test@tourmate.com"},
        )
        assert resp2.status_code == 400
        assert "already exists" in resp2.json()["detail"].lower()

    async def test_register_with_minimal_optional_fields(self, db_session):
        """Omitting optional fields (phone_number, home_city) still succeeds."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Minimal User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "Minimal User"
        assert data["email"] == TEST_EMAIL  # from token, not body
        assert data["phone_number"] is None
        assert data["home_city"] is None

    async def test_register_missing_full_name_returns_422(self, db_session):
        """Missing required 'full_name' field returns 422."""
        client = _make_client(db_session)

        response = client.post(
            "/api/v1/auth/register",
            json={"email": "test@tourmate.com"},
        )
        assert response.status_code == 422

    async def test_register_empty_body_returns_422(self, db_session):
        """Empty request body returns 422."""
        client = _make_client(db_session)

        response = client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422

    async def test_register_without_auth_returns_401(self, db_session):
        """No auth header returns 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/register",
            json={"full_name": "No Auth", "email": "noauth@tourmate.com"},
        )
        assert response.status_code == 401

    async def test_register_with_invalid_token_returns_401(self, db_session):
        """Request with invalid/expired Firebase token returns 401.

        The real ``get_current_user`` dependency raises ``HTTPException(401)``
        when the token is invalid, so we simulate that exact behavior.
        """
        from fastapi import HTTPException, status

        def _raise_unauthorized():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = _raise_unauthorized
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Bad Token", "email": "bad@tourmate.com"},
        )
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 2. POST /api/v1/auth/login  (Requirement #01)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestLoginEndpoint:
    """POST /api/v1/auth/login — Login (auto-create if not exists)."""

    async def test_login_existing_user_returns_user(self, db_session):
        """Existing user logs in → returns user data unchanged."""
        # Seed a user
        user = User(
            user_id=TEST_UID,
            email="existing@tourmate.com",
            full_name="Existing User",
            home_city="Luxor",
        )
        db_session.add(user)
        await db_session.commit()

        client = _make_client(db_session)

        response = client.post("/api/v1/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == TEST_UID
        assert data["full_name"] == "Existing User"
        assert data["email"] == "existing@tourmate.com"
        assert data["home_city"] == "Luxor"

    async def test_login_new_user_auto_creates(self, db_session):
        """New (unknown) user logs in → user is auto-created with minimal fields."""
        client = _make_client(db_session)

        response = client.post("/api/v1/auth/login")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == TEST_UID
        assert data["email"] == TEST_EMAIL
        assert data["full_name"] is None  # auto-created, no name set yet

        # Verify user is now in DB
        result = await db_session.execute(
            select(User).where(User.user_id == TEST_UID)
        )
        db_user = result.scalar_one_or_none()
        assert db_user is not None
        assert db_user.email == TEST_EMAIL

    async def test_login_idempotent_returns_same_user(self, db_session):
        """Multiple logins by the same user return the same user record."""
        client = _make_client(db_session)

        # First login → auto-create
        resp1 = client.post("/api/v1/auth/login")
        assert resp1.status_code == 200
        user_id_1 = resp1.json()["user_id"]

        # Second login → same user
        resp2 = client.post("/api/v1/auth/login")
        assert resp2.status_code == 200
        assert resp2.json()["user_id"] == user_id_1

    async def test_login_without_auth_returns_401(self, db_session):
        """Login without auth header returns 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post("/api/v1/auth/login")
        assert response.status_code == 401

    async def test_login_with_invalid_token_returns_401(self, db_session):
        """Login with invalid/expired token returns 401."""
        from fastapi import HTTPException, status

        def _raise_unauthorized():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = _raise_unauthorized
        client = TestClient(app)

        response = client.post("/api/v1/auth/login")
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# 3. POST /api/v1/auth/test-register  (dev/testing only, no auth required)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestTestRegisterEndpoint:
    """POST /api/v1/auth/test-register — No-auth registration (dev/testing)."""

    async def test_test_register_creates_user_without_auth(self, db_session):
        """Test-register works without any Firebase token."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/test-register",
            json={
                "full_name": "Test Dev User",
                "email": "dev@test.com",
                "phone_number": "+201111111111",
                "home_city": "Alexandria",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "Test Dev User"
        assert data["email"] == "dev@test.com"
        assert data["home_city"] == "Alexandria"
        assert "user_id" in data  # UUID generated

    async def test_test_register_with_minimal_fields(self, db_session):
        """Test-register works with only required full_name and email (NOT NULL)."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/test-register",
            json={"full_name": "Minimal Dev", "email": "minimal@test.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "Minimal Dev"
        assert data["email"] == "minimal@test.com"
        assert data["phone_number"] is None  # optional
        assert data["home_city"] is None     # optional

    async def test_test_register_generates_unique_ids(self, db_session):
        """Each test-register call generates a unique UUID user_id."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        resp1 = client.post(
            "/api/v1/auth/test-register",
            json={"full_name": "User A", "email": "a@test.com"},
        )
        resp2 = client.post(
            "/api/v1/auth/test-register",
            json={"full_name": "User B", "email": "b@test.com"},
        )

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["user_id"] != resp2.json()["user_id"]

    async def test_test_register_empty_body_returns_422(self, db_session):
        """Test-register with empty body returns 422 (missing required full_name)."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post("/api/v1/auth/test-register", json={})
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Auth Guard — Protected endpoints reject unauthenticated requests (#01)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
class TestAuthGuardOnEndpoints:
    """Auth-required endpoints reject unauthenticated requests."""

    async def test_register_endpoint_protected(self, db_session):
        """GET /api/v1/auth/register is protected — no auth → 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Test"},
        )
        assert response.status_code == 401

    async def test_login_endpoint_protected(self, db_session):
        """GET /api/v1/auth/login is protected — no auth → 401."""
        app.dependency_overrides[get_db] = lambda: db_session
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
        client = TestClient(app)

        response = client.post("/api/v1/auth/login")
        assert response.status_code == 401

    async def test_register_with_bearer_no_token_returns_401(self, db_session):
        """'Bearer ' header without actual token value returns 401."""
        from app.core.security import get_current_user

        # Use the real get_current_user — the empty token causes verify_token
        # to return None (no Firebase initialized), which triggers 401.
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = get_current_user
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Test"},
            headers={"Authorization": "Bearer "},
        )
        # Without Firebase, verify_token returns None → get_current_user raises 401
        assert response.status_code == 401

    async def test_register_with_wrong_auth_scheme_returns_401(self, db_session):
        """Using 'Basic' instead of 'Bearer' returns 401."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_current_user] = get_current_user
        client = TestClient(app)

        response = client.post(
            "/api/v1/auth/register",
            json={"full_name": "Test"},
            headers={"Authorization": "Basic some_token"},
        )
        # 'Basic' doesn't start with 'Bearer' so get_current_user raises 401
        assert response.status_code == 401
