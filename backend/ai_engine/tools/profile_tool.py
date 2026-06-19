# ai_engine/tools/profile_tool.py

import httpx
from ai_engine.graph.state import TripProfile
from app.core.config import settings


async def load_trip_profile(trip_id: str, token: str) -> TripProfile:
    """
    Fetches the trip's profile from the FastAPI backend.

    Each trip has its own profile built from conversation context.
    Replaces the old user-level load_behavioral_profile().

    Args:
        trip_id: Trip identifier
        token: Firebase auth token

    Returns:
        TripProfile TypedDict
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.backend_base_url}/api/v1/trips/{trip_id}/profile",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        response.raise_for_status()

    data = response.json()

    return TripProfile(
        profile_id=data.get("profile_id"),
        trip_id=trip_id,
        budget_level=data.get("budget_level"),
        travel_style=data.get("travel_style"),
        pace=data.get("pace"),
        interests=data.get("interests", []),
        food_preferences=data.get("food_preferences", []),
        accommodation_preferences=data.get("accommodation_preferences", []),
        luxury_score=data.get("luxury_score", 0.5),
        culture_score=data.get("culture_score", 0.5),
        adventure_score=data.get("adventure_score", 0.5),
        shopping_score=data.get("shopping_score", 0.3),
        family_score=data.get("family_score", 0.3),
        confidence=data.get("confidence", 0.0),
        generated_at=data.get("generated_at"),
        updated_at=data.get("updated_at"),
    )

def load_mock_profile(trip_id: str = "mock_trip_001") -> TripProfile:
    """
    Returns a hardcoded TripProfile for development and testing.

    Args:
        trip_id: Optional override for the mock trip ID.

    Returns:
        A fully populated TripProfile.
    """
    return TripProfile(
        profile_id="mock_profile_001",
        trip_id=trip_id,
        budget_level="moderate",
        travel_style="cultural",
        pace="moderate",
        interests=["history", "art", "food"],
        food_preferences=["local cuisine", "street food"],
        accommodation_preferences=["boutique hotel", "airbnb"],
        luxury_score=0.5,
        culture_score=0.75,
        adventure_score=0.35,
        shopping_score=0.15,
        family_score=0.2,
        confidence=0.83,
        generated_at=None,
        updated_at=None,
    )