# backend/ai_engine/tools/places_tool.py

"""
Places Tool — retrieves real place data from the database.

This module acts as the data-access layer between the AI agents
and the places database. Instead of loading places from static
JSON files or generating mock data, it queries the database
through PlaceRepository.

The tool is asynchronous because database operations use
an async SQLAlchemy session.

If the database is unavailable or no results are found,
the function returns an empty list rather than fake data.
"""

import logging
from typing import List

# Factory used to create asynchronous database sessions.
from app.core.database import async_session

# Repository responsible for place-related database queries.
from app.repositories.place_repo import PlaceRepository

# Module-level logger used for monitoring and debugging.
logger = logging.getLogger(__name__)


async def get_places_for_city(
    city: str,
) -> List[dict]:
    """
    Retrieve all places belonging to a specific city.

    This function serves as the primary entry point for
    loading destination data before itinerary generation.

    The returned places are not filtered by interests,
    budget, trip style, or ranking score. Those tasks
    are handled later by Retrieval and Ranking Agents.

    Example:
        Input:  "Cairo"
        Output: [
            {
                "name": "Egyptian Museum",
                "category": "Museum",
                "rating": 4.7,
                ...
            },
            ...
        ]

    Args:
        city:
            Destination city name provided by the user.

    Returns:
        List of place dictionaries.

        Returns:
        - All matching places if found.
        - Empty list if city is invalid.
        - Empty list if database access fails.
        - Empty list if no places exist for that city.
    """

    # Remove leading/trailing whitespace.
    # Prevents lookup failures caused by inputs such as:
    # " Cairo ", "  Paris", etc.
    city_key = (city or "").strip()

    # Validate input before making a database call.
    # If city is empty, None, or only spaces,
    # immediately return an empty result.
    if not city_key:
        logger.warning(
            "[PlacesTool] Empty city name, returning empty list"
        )
        return []

    try:
        # Create a temporary asynchronous database session.
        # The session is automatically closed when leaving
        # the async context manager.
        async with async_session() as session:

            # Instantiate the repository responsible
            # for place-related queries.
            repo = PlaceRepository(session)

            # Use the diverse query that samples top K from each subcategory.
            places = await repo.get_places_by_city_diverse(
                city_key,
                per_subcategory=20,
                max_restaurants=15,
                max_hotels=10,
            )

        logger.info(
            "[PlacesTool] Loaded %d places for %s (stratified by subcategory)",
            len(places),
            city_key,
        )

    except Exception as e:
        # Catch any database-related failures:
        # - Connection issues
        # - Query errors
        # - Session failures
        # - Repository exceptions
        #
        # Log the error and return an empty list so the
        # planning workflow can fail gracefully.
        logger.error(
            "[PlacesTool] Database query failed for %s: %s",
            city_key,
            e,
        )
        return []

    # Return the complete set of places for the city.
    #
    # Example flow:
    # User → "Plan a trip to Cairo"
    #       ↓
    # get_places_for_city("Cairo")
    #       ↓
    # Returns all Cairo places
    #       ↓
    # Retrieval Agent filters relevant places
    #       ↓
    # Ranking Agent scores and sorts them
    #       ↓
    # Planner builds itinerary
    return places