"""
Unit tests for app.core.security and app.core.firebase.

Tests cover:
    - security.get_current_user()       — auth dependency
    - security.get_optional_user()      — optional auth dependency
    - firebase.verify_token()           — Firebase token verification with clock-skew fallback
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from fastapi import HTTPException, status


# ═══════════════════════════════════════════════════════════════════════════════
# 1. firebase.verify_token
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerifyToken:
    """firebase.verify_token — Firebase token verification."""

    @patch("app.core.firebase.auth")
    def test_valid_token_returns_decoded(self, mock_auth):
        """A valid Firebase token returns the decoded claims dict."""
        mock_auth.verify_id_token.return_value = {
            "uid": "test_uid",
            "email": "test@example.com",
        }
        from app.core.firebase import verify_token

        result = verify_token("valid_token")
        assert result == {"uid": "test_uid", "email": "test@example.com"}
        mock_auth.verify_id_token.assert_called_once_with("valid_token")

    @patch("app.core.firebase.auth")
    def test_expired_token_returns_none(self, mock_auth):
        """An expired token with no clock-skew fallback returns None."""
        mock_auth.verify_id_token.side_effect = Exception("Token expired")

        from app.core.firebase import verify_token

        # No clock-skew fallback because FIREBASE_PROJECT_ID is set via settings
        # We patch settings to raise so the fallback is skipped
        with patch("app.core.firebase._FIREBASE_PROJECT_ID", ""):
            result = verify_token("expired_token")
        assert result is None

    @patch("app.core.firebase.auth")
    @patch("app.core.firebase.google_jwt")
    @patch("app.core.firebase._FIREBASE_PROJECT_ID", "test-project")
    def test_clock_skew_fallback_succeeds(self, mock_google_jwt, mock_auth):
        """When Firebase raises 'used too early', fall back to google_jwt.decode."""
        mock_auth.verify_id_token.side_effect = Exception(
            "Firebase ID token has incorrect 'iat' (used too early)"
        )
        mock_google_jwt.decode.return_value = {
            "uid": "skew_user",
            "email": "skew@example.com",
        }

        from app.core.firebase import verify_token

        result = verify_token("skewed_token")
        assert result == {"uid": "skew_user", "email": "skew@example.com"}
        mock_google_jwt.decode.assert_called_once()

    @patch("app.core.firebase.auth")
    @patch("app.core.firebase.google_jwt")
    @patch("app.core.firebase._FIREBASE_PROJECT_ID", "test-project")
    def test_clock_skew_fallback_fails_returns_none(self, mock_google_jwt, mock_auth):
        """When both Firebase and google_jwt.decode fail, return None."""
        mock_auth.verify_id_token.side_effect = Exception(
            "Firebase ID token used too late"
        )
        mock_google_jwt.decode.side_effect = Exception("JWT decode failed")

        from app.core.firebase import verify_token

        result = verify_token("double_fail_token")
        assert result is None

    @patch("app.core.firebase.auth")
    @patch("app.core.firebase.google_jwt")
    @patch("app.core.firebase._FIREBASE_PROJECT_ID", "test-project")
    def test_clock_skew_claims_none_returns_none(self, mock_google_jwt, mock_auth):
        """When google_jwt.decode returns None (silent failure), return None."""
        mock_auth.verify_id_token.side_effect = Exception(
            "Firebase ID token used too early"
        )
        mock_google_jwt.decode.return_value = None

        from app.core.firebase import verify_token

        result = verify_token("null_claims_token")
        assert result is None

    @patch("app.core.firebase.auth")
    def test_non_clock_error_returns_none(self, mock_auth):
        """A Firebase error that is NOT clock-skew related returns None."""
        mock_auth.verify_id_token.side_effect = Exception("Invalid token signature")

        from app.core.firebase import verify_token

        result = verify_token("bad_sig_token")
        assert result is None

    @patch("app.core.firebase.auth")
    def test_verify_id_token_unknown_exception_returns_none(self, mock_auth):
        """Any unexpected exception from verify_id_token returns None."""
        mock_auth.verify_id_token.side_effect = RuntimeError("Unexpected Firebase error")

        from app.core.firebase import verify_token

        result = verify_token("unexpected_error_token")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 2. security.get_current_user
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetCurrentUser:
    """security.get_current_user — Authorization dependency."""

    def test_missing_header_raises_401(self):
        """No Authorization header → 401."""
        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization=None))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_header_detail_message(self):
        """No Authorization header → clear error message."""
        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization=None))
        assert "Authorization header required" in exc_info.value.detail

    def test_invalid_format_raises_401(self):
        """Header without 'Bearer ' → 401."""
        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization="Token no_bearer"))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_format_detail_message(self):
        """Header without 'Bearer ' → clear error message."""
        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization="Token no_bearer"))
        assert "Invalid token format" in exc_info.value.detail

    def test_empty_bearer_token_raises_401(self):
        """Bearer with empty/whitespace token → 401."""
        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization="Bearer "))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.core.security.verify_token")
    def test_valid_token_returns_user(self, mock_verify):
        """Valid 'Bearer <token>' → returns user dict from Firebase."""
        mock_verify.return_value = {"uid": "my_uid", "email": "me@example.com"}

        from app.core.security import get_current_user

        import asyncio
        result = asyncio.run(get_current_user(authorization="Bearer my_token"))
        assert result["uid"] == "my_uid"
        assert result["email"] == "me@example.com"
        mock_verify.assert_called_once_with("my_token")

    @patch("app.core.security.verify_token")
    def test_verify_token_returns_none_raises_401(self, mock_verify):
        """When verify_token returns None (invalid/expired), raise 401."""
        mock_verify.return_value = None

        from app.core.security import get_current_user

        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user(authorization="Bearer bad_token"))
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or expired token" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════════════════════════
# 3. security.get_optional_user
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetOptionalUser:
    """security.get_optional_user — Optional auth dependency (returns None instead of 401)."""

    def test_no_header_returns_none(self):
        """No Authorization header → None (no error)."""
        from app.core.security import get_optional_user

        import asyncio
        result = asyncio.run(get_optional_user(authorization=None))
        assert result is None

    def test_no_bearer_prefix_returns_none(self):
        """Header without 'Bearer' → None (no error)."""
        from app.core.security import get_optional_user

        import asyncio
        result = asyncio.run(get_optional_user(authorization="PlainText"))
        assert result is None

    @patch("app.core.security.verify_token")
    def test_valid_token_returns_user(self, mock_verify):
        """Valid 'Bearer <token>' → returns Firebase user dict."""
        mock_verify.return_value = {"uid": "opt_uid"}

        from app.core.security import get_optional_user

        import asyncio
        result = asyncio.run(get_optional_user(authorization="Bearer good_token"))
        assert result["uid"] == "opt_uid"

    @patch("app.core.security.verify_token")
    def test_invalid_token_returns_none(self, mock_verify):
        """Invalid token → verify_token returns None → get_optional_user returns None."""
        mock_verify.return_value = None

        from app.core.security import get_optional_user

        import asyncio
        result = asyncio.run(get_optional_user(authorization="Bearer bad_token"))
        assert result is None
