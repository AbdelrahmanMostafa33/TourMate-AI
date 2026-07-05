import logging

import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings

logger = logging.getLogger(__name__)

# firebase-admin 7.x clamps clock_skew_seconds to 0-60 internally.
# We use 60 to tolerate server/device clock differences of up to 1 minute.
_CLOCK_SKEW_SECONDS = 60

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred)


def verify_token(token: str) -> dict:
    """Verify a Firebase ID token with 60-second clock-skew tolerance.

    ``firebase_admin.auth.verify_id_token`` supports a built-in
    ``clock_skew_seconds`` parameter (clamped to 0-60 internally) that
    tolerates clock drift between the server and token issuer without
    needing custom fallback logic.

    Returns the decoded token claims dict on success, or ``None`` if
    verification fails.
    """
    try:
        decoded = auth.verify_id_token(
            token,
            clock_skew_seconds=_CLOCK_SKEW_SECONDS,
        )
        return decoded
    except Exception as exc:
        logger.warning(
            "[Firebase] verify_id_token failed (clock_skew=%ss): %s",
            _CLOCK_SKEW_SECONDS, exc,
        )
        return None