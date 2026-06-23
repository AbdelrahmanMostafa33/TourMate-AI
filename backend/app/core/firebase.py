import firebase_admin
from firebase_admin import credentials, auth
from app.core.config import settings
from google.auth import jwt as google_jwt
from datetime import timedelta
import json as _json

CLOCK_TOLERANCE = timedelta(seconds=10)

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS)
    firebase_admin.initialize_app(cred)

# ── Extract project ID from the credential file for clock-skew fallback ──
try:
    with open(settings.FIREBASE_CREDENTIALS) as _f:
        _FIREBASE_PROJECT_ID: str = _json.load(_f)["project_id"]
except Exception:
    _FIREBASE_PROJECT_ID = ""

def verify_token(token: str) -> dict:
    """Verify a Firebase ID token.

    First attempts the standard Firebase verification.  If that fails
    with a clock-skew error (device clock slightly ahead/behind server),
    falls back to ``google.auth.jwt.decode`` with a tolerance window.
    """
    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception as e:
        msg = str(e).lower()
        # ── Clock-skew fallback ──────────────────────────────────────────
        if ("used too early" in msg or "used too late" in msg) and _FIREBASE_PROJECT_ID:
            try:
                claims = google_jwt.decode(
                    token,
                    audience=_FIREBASE_PROJECT_ID,
                    clock_skew_in_seconds=int(CLOCK_TOLERANCE.total_seconds()),
                )
                return dict(claims)
            except Exception as inner_e:
                print("Firebase clock-skew fallback failed:", inner_e)
                return None
        # ── Other errors ──────────────────────────────────────────────────
        print("Firebase token verification error:", e)
        return None