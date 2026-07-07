"""
Hotel Agent — compatibility shim for the _orchestrator compiled handler.

The new hotel_selection_agent.py handles all hotel search/selection via
direct DB queries (like flights). This shim provides ``run_hotel_selection``
in the format expected by the compiled ``hotel_handler.pyc`` so the
_orchestrator module continues to work without source reconstruction.

Hotels are now completely decoupled from the itinerary pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

from ai_engine.agents.hotel_selection_agent import (
    search_hotels_for_trip,
    extract_hotel_selection,
    format_hotel_options,
)
from ai_engine.conversation.conversation_state import ConversationState

logger = logging.getLogger(__name__)


async def run_hotel_selection(state: ConversationState, **kwargs) -> ConversationState:
    """Run hotel selection by querying the database directly.

    Called by the compiled ``hotel_handler._run_hotel_selection_and_present``.
    Instead of the old pipeline approach (pool-based sampling),
    this searches fresh from the DB every time.

    Returns the updated ``ConversationState`` with:
      - ``state.slots.hotel_search_results`` populated
    """
    if not state.slots.destination_city:
        logger.warning("[HotelAgentShim] No destination city for hotel search")
        return state

    city = state.slots.destination_city
    acc_prefs = state.slots.accommodation_preferences or []
    star_class = state.slots.preferred_hotel_star_class
    budget = state.slots.budget_level

    # Derive canonical accommodation type from preferences
    accommodation_type = None
    if acc_prefs:
        from ai_engine.tools.slot_normalizer import map_accommodation_to_type
        accommodation_type = map_accommodation_to_type(acc_prefs)

    logger.info(
        "[HotelAgentShim] Searching hotels in '%s' (type=%s, stars=%s, budget=%s)",
        city, accommodation_type, star_class, budget,
    )

    try:
        hotels = await search_hotels_for_trip(
            city=city,
            accommodation_type=accommodation_type,
            preferred_star_class=star_class,
            budget_level=budget,
            max_results=10,
        )

        state.slots.hotel_search_results = hotels

        # Compatibility: also populate itinerary.accommodation_suggestions
        # for the compiled _orchestrator/handlers/hotel_handler.pyc which
        # reads from this key after run_hotel_selection returns.
        # TODO: Remove when hotel_handler.py source is created.
        if state.itinerary is not None:
            state.itinerary["accommodation_suggestions"] = [
                {
                    "id": h.get("id", ""),
                    "name": h.get("name", ""),
                    "sub_category": h.get("sub_category", ""),
                    "accommodation_type": h.get("accommodation_type", ""),
                    "lat": h.get("lat", 0),
                    "lon": h.get("lon", 0),
                    "rating": h.get("rating", 0),
                    "why_recommended": f"{h.get('accommodation_type', 'Hotel').capitalize()} near your route.",
                    "nightly_rate": h.get("nightly_rate", 0),
                }
                for h in hotels
            ]

        logger.info(
            "[HotelAgentShim] Found %d hotels in '%s'",
            len(hotels), city,
        )
    except Exception as exc:
        logger.error("[HotelAgentShim] Hotel search failed: %s", exc)
        state.slots.hotel_search_results = []

    return state
