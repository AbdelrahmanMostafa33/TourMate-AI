# ai_engine/tools/profile_tool.py

# Import the httpx library for making asynchronous HTTP requests.
import httpx

# Import the TripProfile TypedDict/schema used to structure profile data.
from ai_engine.graph.state import TripProfile

# Import application settings (e.g., backend API base URL).
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

    # Create an asynchronous HTTP client.
    async with httpx.AsyncClient() as client:

        # Send a GET request to the backend to retrieve
        # the profile associated with the given trip.
        response = await client.get(
            # API endpoint for retrieving a trip profile.
            f"{settings.backend_base_url}/api/v1/trips/{trip_id}/profile",

            # Pass the Firebase authentication token.
            headers={"Authorization": f"Bearer {token}"},

            # Maximum wait time for the request.
            timeout=5.0,
        )

        # Raise an exception if the request failed
        # (e.g., 404, 401, 500, etc.).
        response.raise_for_status()

    # Convert the JSON response body into a Python dictionary.
    data = response.json()

    # Construct and return a TripProfile object.
    # .get() is used to safely retrieve fields,
    # providing default values when missing.
    return TripProfile(
        # Unique identifier for the generated profile.
        profile_id=data.get("profile_id"),

        # Trip ID comes from the function argument.
        trip_id=trip_id,

        # User's estimated budget category.
        budget_level=data.get("budget_level"),

        # Preferred travel style (e.g., cultural, luxury).
        travel_style=data.get("travel_style"),

        # Preferred travel pace.
        pace=data.get("pace"),

        # List of interests; defaults to an empty list.
        interests=data.get("interests", []),

        # Preferred food types.
        food_preferences=data.get("food_preferences", []),

        # Preferred accommodation types.
        accommodation_preferences=data.get("accommodation_preferences", []),

        # Scoring fields: API no longer returns these, so defaults are used.
        # They remain in the TypedDict as runtime values for agent computations
        # and image signal enrichment (multimodal_fusion.py).
        luxury_score=0.5,
        culture_score=0.5,
        adventure_score=0.5,


        # Confidence score representing profile reliability.
        confidence=0.0,

        # Timestamp when the profile was first generated.
        generated_at=data.get("generated_at"),

        # Timestamp of the latest profile update.
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

    # Return a predefined profile without calling the backend.
    # Useful for local development and unit testing.
    return TripProfile(

        # Mock profile identifier.
        profile_id="mock_profile_001",

        # Use the provided or default mock trip ID.
        trip_id=trip_id,

        # Sample budget preference.
        budget_level="moderate",

        # Sample travel style.
        travel_style="cultural",

        # Sample travel pace.
        pace="moderate",

        # Example interests.
        interests=["history", "art", "food"],

        # Example food preferences.
        food_preferences=["local cuisine", "street food"],

        # Example accommodation preferences.
        accommodation_preferences=["boutique hotel", "airbnb"],

        # Example AI preference scores.
        luxury_score=0.5,
        culture_score=0.75,
        adventure_score=0.35,


        # Example confidence level.
        confidence=0.83,

        # No timestamps for mock data.
        generated_at=None,
        updated_at=None,
    )