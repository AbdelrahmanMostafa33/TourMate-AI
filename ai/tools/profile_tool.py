# ai/tools/profile_tool.py

import httpx
from graph.state import BehavioralProfile
from config.settings import settings


async def load_behavioral_profile(user_id: str, token: str) -> BehavioralProfile:
    """
    Fetches the user's behavioral profile from the FastAPI backend.

    This function acts as a bridge between:
    - The AI layer (LangGraph agents)
    - The backend (PostgreSQL via FastAPI)

    It retrieves user profile data and maps it into the BehavioralProfile
    structure used inside the TripState.

    Args:
        user_id: Firebase UID identifying the user
        token: Firebase auth token for secure API access

    Returns:
        BehavioralProfile TypedDict ready to be injected into TripState
    """

    # ── Make authenticated request to backend ───────────────────────
    # Uses async HTTP client for non-blocking execution in the agent pipeline
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.backend_base_url}/api/v1/users/profile",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0  # Prevents hanging requests
        )

        # Raises exception if status code is not 2xx
        response.raise_for_status()

    # Parse JSON response from backend
    data = response.json()

    # ── Map backend response → BehavioralProfile ────────────────────
    # NOTE:
    # The current endpoint appears to return only partial profile data
    # (persona + interests). Other fields are defaulted.

    return BehavioralProfile(
        user_id=user_id,

        # ── Demographics (not returned by this endpoint) ────────────
        age=None,
        sex=None,
        travel_companion=None,
        location=None,

        # ── Slider preferences (missing → default to None) ──────────
        # These should ideally come from a "full profile" endpoint
        adventure_relaxing=None,
        nature_culture=None,
        popular_local=None,
        budget_level=None,
        early_night=None,
        independent_social=None,

        # ── Multi-select fields ─────────────────────────────────────
        # Only interests are currently returned; others default empty
        accommodation_styles=[],
        dining_preferences=[],
        interests=data.get("interests", []),
        traveler_types=[],

        # ── Persona (AI-generated, stored in backend) ───────────────
        persona_name=data.get("persona_name"),
        persona_bio=data.get("persona_bio"),
        suggested_questions=data.get("suggested_questions", []),

        # ── Quiz status ─────────────────────────────────────────────
        quiz_completed=data.get("quiz_completed", False),
    )