"""
Hotel Selection Agent — conversational hotel search and selection.

Completely decoupled from the itinerary pipeline. Hotels are searched
directly from the database (not from the candidate pool), so the user
gets fresh, up-to-date results every time.

Flow:
  1. After itinerary approval → HOTEL_SELECTION phase → search hotels by city
  2. Agent formats hotel options for display (with accommodation type, rating, price)
  3. User picks a hotel → agent extracts the selection

The actual booking (Stripe PaymentIntent + confirm) happens outside
of this agent, through the existing booking REST API endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from ai_engine.tools.slot_normalizer import map_accommodation_to_type

logger = logging.getLogger(__name__)


# ── Hotel Search ───────────────────────────────────────────────────────────


async def search_hotels_for_trip(
    city: str,
    country: str | None = None,
    accommodation_type: str | None = None,
    preferred_star_class: int | None = None,
    budget_level: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Search for hotels in a city directly from the database.

    Unlike the old pipeline (which sampled hotels into the candidate pool),
    this function queries the database fresh every time, so results are
    always up-to-date and respect the user's current preferences.

    Args:
        city:              Destination city name (e.g. "Cairo").
        country:           Optional country for disambiguation.
        accommodation_type: Optional canonical type filter:
                           "hotel", "hostel", "resort", "luxury".
        preferred_star_class: Optional star class filter (1-5).
        budget_level:      Optional budget level: "budget", "moderate", "luxury".
        max_results:       Max hotels to return (default 10).

    Returns:
        A list of hotel dicts with rich metadata, or empty list if none found.
    """
    if not city:
        logger.warning("[HotelAgent] search_hotels_for_trip called without city")
        return []

    logger.info(
        "[HotelAgent] Searching hotels in '%s' (type=%s, stars=%s, budget=%s)",
        city, accommodation_type, preferred_star_class, budget_level,
    )

    try:
        from app.core.database import async_session
        from app.repositories.place_repo import PlaceRepository

        async with async_session() as session:
            repo = PlaceRepository(session)

            # Price level mapping from budget_level
            # NOTE: Place.price_level is a general 1-5 cost indicator, not nightly rate.
            # Budget filtering by actual nightly_rate requires a dedicated query.
            price_level = None
            if budget_level == "budget":
                price_level = 1
            elif budget_level == "moderate":
                price_level = 3
            # luxury → no price cap

            hotels = await repo.search_places(
                city=city,
                country=country,
                categories=["hotel"],
                accommodation_type=accommodation_type,
                star_class=preferred_star_class,
                max_price_level=price_level,
                sort_by="popularity_score",
                sort_desc=True,
                limit=max_results,
            )

            # hotels is a tuple (places_list, total_count)
            if isinstance(hotels, tuple):
                hotels = hotels[0]

            logger.info(
                "[HotelAgent] Found %d hotels in '%s'",
                len(hotels or []), city,
            )
            return hotels or []

    except Exception as exc:
        logger.error("[HotelAgent] Hotel search failed for '%s': %s", city, exc)
        return []


# ── Hotel Selection Extraction ────────────────────────────────────────────


def extract_hotel_selection(
    user_message: str,
    hotels: list[dict],
    selected_number: int | None = None,
) -> dict | None:
    """Extract the user's hotel selection from their message or index.

    Args:
        user_message:    The user's natural language message.
        hotels:          The list of hotel dicts shown to the user.
        selected_number: Optional 1-based index from the message interpreter.

    Returns:
        The selected hotel dict, or None if no match.
    """
    if not hotels:
        return None

    # 1. Direct index match
    if selected_number is not None and 1 <= selected_number <= len(hotels):
        logger.info(
            "[HotelAgent] User picked by number %d → %s",
            selected_number,
            hotels[selected_number - 1].get("name", "?"),
        )
        return hotels[selected_number - 1]

    # 2. Keyword matching against hotel names
    msg_lower = user_message.lower()
    for hotel in hotels:
        name = (hotel.get("name") or "").lower()
        if name and name in msg_lower:
            logger.info(
                "[HotelAgent] User picked by name '%s' → %s",
                hotel["name"], hotel.get("id", "?"),
            )
            return hotel

    # 3. Check for number words
    import re
    num_match = re.search(r"(?:hotel|option|number|#)\s*(\d+)", msg_lower)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(hotels):
            logger.info(
                "[HotelAgent] Regex match: hotel %d → %s",
                idx + 1, hotels[idx].get("name", "?"),
            )
            return hotels[idx]

    # 4. Word-based: "first", "second", "third", etc.
    word_map = {
        "first": 0, "1st": 0,
        "second": 1, "2nd": 1,
        "third": 2, "3rd": 2,
        "fourth": 3, "4th": 3,
        "fifth": 4, "5th": 4,
    }
    words = msg_lower.split()
    for word in words:
        if word in word_map:
            idx = word_map[word]
            if 0 <= idx < len(hotels):
                logger.info(
                    "[HotelAgent] Word match '%s' → %s",
                    word, hotels[idx].get("name", "?"),
                )
                return hotels[idx]

    # 5. Default: first hotel if user seems to be selecting
    selection_keywords = ["i'll take", "i want", "pick", "choose", "select", "go with", "book"]
    if any(kw in msg_lower for kw in selection_keywords):
        logger.info("[HotelAgent] Defaulting to first hotel for selection message")
        return hotels[0]

    return None


# ── Hotel Display Formatting ──────────────────────────────────────────────


def format_hotel_options(hotels: list[dict]) -> str:
    """Format hotel options as a readable string for the user.

    Returns a formatted string with numbered hotel options including
    name, accommodation type, rating, star class, and price.

    Args:
        hotels: List of hotel dicts from the database (with rich metadata).
    """
    if not hotels:
        return "No hotels found for this destination."

    _NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    lines = []
    for i, hotel in enumerate(hotels):
        num_emoji = _NUMBER_EMOJI[i] if i < len(_NUMBER_EMOJI) else f"{i + 1}."

        name = hotel.get("name", "Unknown")
        acc_type = hotel.get("accommodation_type", "hotel")
        rating = hotel.get("rating", 0)
        star_class = hotel.get("star_class") or hotel.get("hotel_details", {}).get("star_class")
        nightly_rate = hotel.get("nightly_rate") or hotel.get("hotel_details", {}).get("nightly_rate", 0)
        address = hotel.get("address", "")

        star_str = f" ⭐{'⭐' * (star_class - 1) if star_class and star_class > 1 else ''}" if star_class else ""
        price_str = f" — 💰 {nightly_rate:.0f} /night" if nightly_rate else ""
        rating_str = f" ({rating:.1f}★)" if rating else ""

        lines.append(f"{num_emoji} **{name}**{rating_str}{star_str}")
        lines.append(f"   🏨 {acc_type.capitalize()}{price_str}")
        if address:
            lines.append(f"   📍 {address[:60]}")
        lines.append("")

    return "\n".join(lines)
