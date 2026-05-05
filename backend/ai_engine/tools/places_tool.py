# backend/ai_engine/tools/places_tool.py

from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 3: Mock implementation.
# Sprint 4 (Task 4.4): Replace the body of get_places_for_city() with a call to:
#   from app.external.overpass_client import query_tourist_places
#   return query_tourist_places(city, radius_km=10, interests=interests)
# The function signature and return shape stay exactly the same.
# ─────────────────────────────────────────────────────────────────────────────

# Each place dict shape: { "name": str, "category": str, "lat": float, "lon": float }
_MOCK_PLACES: dict[str, List[dict]] = {
    "cairo": [
        {"name": "Egyptian Museum",      "category": "museum",    "lat": 30.0478, "lon": 31.2336},
        {"name": "Khan el-Khalili",      "category": "market",    "lat": 30.0477, "lon": 31.2625},
        {"name": "Pyramids of Giza",     "category": "landmark",  "lat": 29.9792, "lon": 31.1342},
        {"name": "Al-Azhar Mosque",      "category": "religious", "lat": 30.0459, "lon": 31.2625},
        {"name": "Coptic Cairo",         "category": "historic",  "lat": 30.0054, "lon": 31.2296},
        {"name": "Zamalek Art Gallery",  "category": "art",       "lat": 30.0626, "lon": 31.2191},
        {"name": "Nile Corniche",        "category": "nature",    "lat": 30.0444, "lon": 31.2357},
        {"name": "El-Fishawy Cafe",      "category": "food",      "lat": 30.0476, "lon": 31.2618},
    ],
    "alexandria": [
        {"name": "Bibliotheca Alexandrina", "category": "museum",   "lat": 31.2089, "lon": 29.9092},
        {"name": "Montaza Palace Gardens",  "category": "nature",   "lat": 31.2837, "lon": 30.0144},
        {"name": "Qaitbay Citadel",         "category": "historic", "lat": 31.2138, "lon": 29.8853},
        {"name": "Stanley Beach",           "category": "beach",    "lat": 31.2362, "lon": 29.9601},
    ],
}

_DEFAULT_PLACES: List[dict] = [
    {"name": "City Center",    "category": "landmark", "lat": 0.0, "lon": 0.0},
    {"name": "Local Market",   "category": "market",   "lat": 0.0, "lon": 0.0},
    {"name": "Main Museum",    "category": "museum",   "lat": 0.0, "lon": 0.0},
]


def get_places_for_city(
    city: str,
    interests: Optional[List[str]] = None,
) -> List[dict]:
    """
    Returns a list of POIs for the given destination city.

    Each POI is a dict with: name, category, lat, lon.
    The planning agent passes this list to the LLM to build the itinerary.

    Sprint 3: Returns mock data.
    Sprint 4: Calls overpass_client.query_tourist_places() with the same signature.

    Args:
        city:      Destination city name (case-insensitive). E.g. "Cairo".
        interests: Optional list of user interests for filtering.
                   E.g. ["history", "food"]. Comes from BehavioralProfile["interests"].

    Returns:
        List of place dicts. Never returns an empty list — falls back to
        _DEFAULT_PLACES if the city is unknown or filtering removes everything.
    """
    city_key = city.lower().strip() if city else ""
    places = _MOCK_PLACES.get(city_key, _DEFAULT_PLACES)

    # Apply interest-based filtering if interests are provided
    if interests:
        interests_lower = {i.lower() for i in interests if i}
        filtered = [
            p for p in places
            if p["category"] in interests_lower
            or any(kw in p["name"].lower() for kw in interests_lower)
        ]
        # Never return empty — fall back to unfiltered list
        return filtered if filtered else places

    return places