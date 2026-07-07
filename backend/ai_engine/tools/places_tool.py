"""
Place search tool — retrieves places from the database.

Used by the Place Retriever to load all available places for a
destination city before filtering and scoring.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_places_for_city(city: str) -> list[dict]:
    """Retrieve all places for a specific city.

    This is the initial loading step for itinerary generation.
    Hotels are NOT excluded here — the Place Retriever skips them
    in ``_apply_filters()``.  This function returns ALL places so the
    retriever has the full set to work with.

    Args:
        city: Destination city name.

    Returns:
        List of place dicts, or empty list on failure.
    """
    if not city:
        logger.warning("[PlacesTool] get_places_for_city called without city")
        return []

    try:
        from app.core.database import async_session
        from app.repositories.place_repo import PlaceRepository

        async with async_session() as session:
            repo = PlaceRepository(session)
            places = await repo.get_places_by_city_diverse(
                city=city,
            )
            logger.info(
                "[PlacesTool] Loaded %d places for '%s'",
                len(places or []), city,
            )
            return places or []

    except Exception as exc:
        logger.error("[PlacesTool] Failed to load places for '%s': %s", city, exc)
        return []
