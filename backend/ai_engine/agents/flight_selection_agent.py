"""
Flight Selection Agent — conversational flight search and selection.

Integrates with the existing Amadeus client for flight search.
This agent does NOT handle payment — it only handles the conversational
flow of searching and selecting flights.  Payment is managed by the
Flutter client via the existing REST API endpoints.

Flow:
  1. User provides origin city → agent searches flights
  2. Agent formats flight options for display
  3. User picks a flight → agent extracts the selection

The actual booking (Stripe PaymentIntent + confirm) happens outside
of this agent, through the existing flight REST API endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Flight Search ───────────────────────────────────────────────────────────


def _build_city_to_iata_map() -> dict[str, str]:
    """Local IATA code map used as a fallback before calling Amadeus."""
    return {
        "cairo": "CAI",
        "istanbul": "IST",
        "london": "LHR",
        "dubai": "DXB",
        "paris": "CDG",
        "rome": "FCO",
        "amsterdam": "AMS",
        "madrid": "MAD",
        "berlin": "BER",
        "barcelona": "BCN",
        "tokyo": "NRT",
        "sydney": "SYD",
        "miami": "MIA",
        "new york": "JFK",
        "los angeles": "LAX",
        "chicago": "ORD",
        "sharm el sheikh": "SSH",
        "hurghada": "HRG",
        "luxor": "LXR",
        "aswan": "ASW",
        "alexandria": "HBE",
        "abu simbel": "ABS",
    }


_CITY_TO_IATA = _build_city_to_iata_map()


def resolve_city_to_iata(city_name: str) -> str | None:
    """Resolve a city name to an IATA code.

    First checks the local dictionary, then falls back to the
    Amadeus API.  Returns None if resolution fails.
    """
    lower = city_name.lower().strip()
    if lower in _CITY_TO_IATA:
        return _CITY_TO_IATA[lower]

    # Fallback: try Amadeus autocomplete
    try:
        from app.services.amadeus_client import amadeus_client
        raw_results = amadeus_client.search_cities(city_name, max_results=3)
        for raw in raw_results:
            iata = raw.get("iataCode", "")
            if iata:
                return iata
    except Exception as exc:
        logger.warning(
            "[FlightAgent] Amadeus city resolution failed for '%s': %s",
            city_name, exc,
        )

    return None


async def search_flights_for_trip(
    origin_city: str,
    destination_city: str,
    departure_date: str | None = None,
    adults: int = 1,
    cabin_class: str | None = None,
    return_date: str | None = None,
) -> list[dict]:
    """Search for flights between two cities.

    Resolves city names to IATA codes, then searches via Amadeus.
    Returns a list of flight offer dicts with human-readable formatting.

    Args:
        origin_city:      City name for origin (e.g. "Cairo").
        destination_city: City name for destination (e.g. "Istanbul").
        departure_date:   Optional ISO date string (e.g. "2026-07-15").
                          Falls back to "next month" if not provided.
        adults:           Number of adult passengers.
        cabin_class:      Optional cabin class filter (e.g. "ECONOMY",
                          "PREMIUM_ECONOMY", "BUSINESS", "FIRST").
        return_date:      Optional return date for round-trip search
                          (ISO date string, e.g. "2026-07-22").

    Returns:
        A list of dicts, each containing parsed flight info.
        Empty list if search fails or no results.
    """
    # Resolve IATA codes
    origin_iata = resolve_city_to_iata(origin_city)
    dest_iata = resolve_city_to_iata(destination_city)

    if not origin_iata:
        logger.warning("[FlightAgent] Could not resolve origin city: %s", origin_city)
        return []
    if not dest_iata:
        logger.warning("[FlightAgent] Could not resolve destination city: %s", destination_city)
        return []

    # Default departure date: 30 days from now if not provided
    if not departure_date:
        from datetime import timedelta
        departure_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    # Search via Amadeus
    try:
        from app.services.amadeus_client import amadeus_client
        raw_offers = amadeus_client.search_flights(
            origin=origin_iata,
            destination=dest_iata,
            departure_date=departure_date,
            adults=adults,
            max_results=5,
            travel_class=cabin_class,
            return_date=return_date,
        )
    except Exception as exc:
        logger.error("[FlightAgent] Flight search failed: %s", exc)
        return []

    if not raw_offers:
        return []

    # Parse offers into a clean format
    parsed: list[dict] = []
    for idx, offer in enumerate(raw_offers):
        try:
            item = _parse_offer(offer, idx)
            parsed.append(item)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.warning("[FlightAgent] Skipping malformed offer %d: %s", idx, exc)
            continue

    return parsed


def _parse_offer(offer: dict, idx: int) -> dict:
    """Parse a raw Amadeus offer dict into a clean format for display."""
    airline_code = offer["validatingAirlineCodes"][0]
    itinerary = offer["itineraries"][0]
    segment = itinerary["segments"][0]
    last_segment = itinerary["segments"][-1]
    flight_number = f"{segment['carrierCode']}{segment['number']}"

    departure_at = datetime.fromisoformat(
        segment["departure"]["at"].replace("Z", "+00:00")
    )
    arrival_at = datetime.fromisoformat(
        last_segment["arrival"]["at"].replace("Z", "+00:00")
    )

    cabin_class = (
        offer["travelerPricings"][0]
        ["fareDetailsBySegment"][0]
        ["cabin"]
    )

    total_price = float(offer["price"]["total"])
    currency = offer["price"]["currency"]
    price_per_adult = float(offer["price"]["base"])

    # Try to get airline name from Amadeus reference data
    airline_name = airline_code
    try:
        from app.services.amadeus_client import amadeus_client
        response = amadeus_client._client.reference_data.airlines.get(
            airlineCodes=airline_code
        )
        airline_name = response.data[0]["businessName"]
    except Exception:
        pass

    # Format datetimes for display
    depart_formatted = departure_at.strftime("%b %d, %H:%M")
    arrival_formatted = arrival_at.strftime("%b %d, %H:%M")

    return {
        "offer_index": idx,
        "airline_code": airline_code,
        "airline_name": airline_name,
        "flight_number": flight_number,
        "origin_iata": segment["departure"]["iataCode"],
        "destination_iata": last_segment["arrival"]["iataCode"],
        "departure_at": departure_at.isoformat(),
        "arrival_at": arrival_at.isoformat(),
        "departure_at_formatted": depart_formatted,
        "arrival_at_formatted": arrival_formatted,
        "cabin_class": cabin_class,
        "total_price": total_price,
        "currency": currency,
        "price_per_adult": price_per_adult,
        "stops": len(itinerary["segments"]) - 1,
        "duration": itinerary.get("duration", ""),
        "raw_offer": offer,
    }


# ── Flight Display Formatting ───────────────────────────────────────────────


def format_flight_options(offers: list[dict], cabin_class_filter: str | None = None) -> str:
    """Format flight offers as a readable string for the user.

    Returns a formatted string with numbered flight options including
    airline, flight number, times, price, and cabin class.

    Args:
        offers:            List of flight offer dicts.
        cabin_class_filter: If set, shows a header noting the filter.
    """
    if not offers:
        filter_note = f" for {cabin_class_filter.capitalize()} class" if cabin_class_filter else ""
        return f"No {cabin_class_filter.lower() if cabin_class_filter else ''} flights found for this route."

    _NUMBER_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]

    lines = []
    for i, offer in enumerate(offers):
        num_emoji = _NUMBER_EMOJI[i] if i < len(_NUMBER_EMOJI) else f"{i + 1}."

        airline = offer.get("airline_name", offer.get("airline_code", "Unknown"))
        flight_num = offer.get("flight_number", "")
        origin = offer.get("origin_iata", "")
        dest = offer.get("destination_iata", "")
        depart = offer.get("departure_at_formatted", "")
        arrival = offer.get("arrival_at_formatted", "")
        price = offer.get("total_price", 0)
        currency = offer.get("currency", "")
        cabin = offer.get("cabin_class", "").capitalize()
        stops = offer.get("stops", 0)
        duration = offer.get("duration", "")

        stop_str = "Direct" if stops == 0 else f"{stops} stop(s)"
        cabin_str = f" ({cabin})" if cabin else ""

        lines.append(f"{num_emoji} **{airline}** {flight_num}")
        lines.append(f"   ✈️ {origin} → {dest}")
        lines.append(f"   🕐 {depart} → {arrival}")
        lines.append(f"   ⏱ {duration}" if duration else "")
        lines.append(f"   💰 {price} {currency}{cabin_str}")
        lines.append(f"   🔄 {stop_str}")
        lines.append("")

    return "\n".join(lines)


def extract_flight_selection(
    user_message: str,
    offers: list[dict],
    selected_number: int | None = None,
) -> dict | None:
    """Extract the user's flight selection from their message or index.

    Args:
        user_message:    The user's natural language message.
        offers:          The list of flight offers shown to the user.
        selected_number: Optional 1-based index from the message interpreter.

    Returns:
        The selected flight offer dict, or None if no match.
    """
    if not offers:
        return None

    # 1. Direct index match
    if selected_number is not None and 1 <= selected_number <= len(offers):
        logger.info(
            "[FlightAgent] User picked by number %d → %s",
            selected_number,
            offers[selected_number - 1].get("flight_number", "?"),
        )
        return offers[selected_number - 1]

    # 2. Keyword matching
    msg_lower = user_message.lower()

    # Try to match by airline name
    for offer in offers:
        airline = (offer.get("airline_name") or "").lower()
        airline_code = (offer.get("airline_code") or "").lower()
        flight_num = (offer.get("flight_number") or "").lower()
        if airline and airline in msg_lower:
            logger.info(
                "[FlightAgent] User picked by airline '%s' → %s",
                airline, offer.get("flight_number", "?"),
            )
            return offer
        if flight_num and flight_num in msg_lower:
            logger.info(
                "[FlightAgent] User picked by flight number '%s' → %s",
                flight_num, offer.get("flight_number", "?"),
            )
            return offer
        if airline_code and airline_code in msg_lower:
            logger.info(
                "[FlightAgent] User picked by airline code '%s' → %s",
                airline_code, offer.get("flight_number", "?"),
            )
            return offer

    # 3. Check for number words
    import re
    num_match = re.search(r"(?:flight|option|number|#)\s*(\d+)", msg_lower)
    if num_match:
        idx = int(num_match.group(1)) - 1
        if 0 <= idx < len(offers):
            logger.info(
                "[FlightAgent] Regex match: flight %d → %s",
                idx + 1, offers[idx].get("flight_number", "?"),
            )
            return offers[idx]

    # 4. Word-based: "first", "second", "third", "fourth", "fifth"
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
            if 0 <= idx < len(offers):
                logger.info(
                    "[FlightAgent] Word match '%s' → %s",
                    word, offers[idx].get("flight_number", "?"),
                )
                return offers[idx]

    # 5. Default: first offer if user seems to be selecting
    selection_keywords = ["i'll take", "i want", "pick", "choose", "select", "go with", "book"]
    if any(kw in msg_lower for kw in selection_keywords):
        logger.info(
            "[FlightAgent] Defaulting to first offer for selection message",
        )
        return offers[0]

    return None
