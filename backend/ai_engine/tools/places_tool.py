# backend/ai_engine/tools/places_tool.py

import json
from pathlib import Path
from typing import List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 4: Loads real place data from the curated JSON file.
# Falls back to a small hardcoded list if the file is missing.
# ─────────────────────────────────────────────────────────────────────────────

# Each place dict shape: { "name": str, "category": str, "lat": float, "lon": float }



# Path to the real data file (relative to this file's location)
_DATA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cairo_places.json"

# How many top places to keep per category type (sorted by popularity_score)
_MAX_ATTRACTIONS = 40
_MAX_RESTAURANTS = 20
_MAX_HOTELS = 10




def _derive_category(place: dict) -> str:
    """Derive a simple category string from sub_category or interest_tags."""
    # Hotels are always categorized as "hotel" regardless of amenities like food/nightlife.
    sub = (place.get("sub_category") or place.get("subtype") or "").lower()
    if "hotel" in sub:
        return "hotel"

    # Tags are already simple (e.g. "history", "food", "art").
    # Use the first tag as the category.
    tags = place.get("interest_tags", [])
    if tags:
        return tags[0]

    # Fallback: use sub_category lowercased.
    return sub if sub else "attraction"


def _place_to_dict(place: dict) -> dict:
    """Convert a raw JSON place record to the dict shape expected by the planner."""
    return {
        "id": place["id"],
        "name": place["name"],
        "category": _derive_category(place),
        "sub_category": place.get("sub_category") or place.get("subtype") or "",
        "lat": place["lat"],
        "lon": place["lon"],
        "description": place.get("description", ""),
        "rating": place.get("rating", 0),
        "review_count": place.get("review_count", 0),
        "popularity_score": place.get("popularity_score", 0),
        "interest_tags": place.get("interest_tags", []),
        "address": place.get("address", ""),
        "hours": place.get("hours") or {},
        "photos": (place.get("photos") or [])[:1],
        "maps_link": place.get("maps_link"),
    }


def _load_real_places() -> dict[str, List[dict]]:
    """Load and curate top places from the real data file."""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            all_places = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"[PlacesTool] Warning: Could not load {_DATA_FILE}: {e}")
        return {}

    # Select top attractions by popularity
    attractions = sorted(
        [p for p in all_places if p.get("category") == "attractions"],
        key=lambda x: x.get("popularity_score", 0),
        reverse=True,
    )[:_MAX_ATTRACTIONS]

    # Select top restaurants by popularity
    restaurants = sorted(
        [p for p in all_places if p.get("category") == "restaurant"],
        key=lambda x: x.get("popularity_score", 0),
        reverse=True,
    )[:_MAX_RESTAURANTS]

    # Select top hotels by popularity
    hotels = sorted(
        [p for p in all_places if p.get("category") == "hotel"],
        key=lambda x: x.get("popularity_score", 0),
        reverse=True,
    )[:_MAX_HOTELS]

    cairo_places = [_place_to_dict(p) for p in attractions + restaurants + hotels]

    return {"cairo": cairo_places}


# Load real places at module import time (once)
_REAL_PLACES = _load_real_places()

# Alexandria mock data (no JSON file available yet)
_ALEXANDRIA_MOCK: List[dict] = [
    {"name": "Bibliotheca Alexandrina", "category": "museum", "lat": 31.2089, "lon": 29.9092},
    {"name": "Montaza Palace Gardens", "category": "nature", "lat": 31.2837, "lon": 30.0144},
    {"name": "Qaitbay Citadel", "category": "historic", "lat": 31.2138, "lon": 29.8853},
    {"name": "Stanley Beach", "category": "beach", "lat": 31.2362, "lon": 29.9601},
]

# Merge real places with any remaining mock data
_MOCK_PLACES: dict[str, List[dict]] = {**_REAL_PLACES}
if "alexandria" not in _MOCK_PLACES:
    _MOCK_PLACES["alexandria"] = _ALEXANDRIA_MOCK

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
    Returns a list of Places for the given destination city.

    Each Place is a dict with: name, category, lat, lon.
    The planning agent passes this list to the LLM to build the itinerary.

    Sprint 4: Loads real data from cairo_places.json.

    Args:
        city:      Destination city name (case-insensitive). E.g. "Cairo".
        interests: Optional list of user interests for filtering.
                   E.g. ["history", "food"]. Comes from BehavioralProfile["interests"].

    Returns:
        List of place dicts. Never returns an empty list — falls back to
        _DEFAULT_PLACES if the city is unknown or filtering removes everything.
    """

    # Normalize city name to lowercase and remove extra spaces
    # so lookups are case-insensitive.
    # Examples:
    # "Cairo" -> "cairo"
    # "  Cairo  " -> "cairo"
    city_key = city.lower().strip() if city else ""

    # Retrieve places for the requested city.
    # If the city does not exist in the dataset,
    # use the default places list as a fallback.
    places = _MOCK_PLACES.get(city_key, _DEFAULT_PLACES)

    # ---------------------------------------------------------
    # Interest-Based Filtering
    # ---------------------------------------------------------
    # If the user profile contains interests,
    # filter places to show only the most relevant ones.
    #
    # Hotels are always preserved because they are used
    # as accommodation suggestions and should not be removed
    # by interest filtering.
    #
    # Both user interests and place tags are already lowercase
    # simple strings (e.g. "history", "food"), so no .lower() needed.
    if interests:

        interests_set = {i for i in interests if i}

        # Keep a place if ANY of the following conditions are true:
        # 1. It is a hotel.
        # 2. Its category matches a user interest.
        # 3. Its name contains an interest keyword.
        # 4. One of its interest_tags matches a user interest.
        filtered = [
            p for p in places
            if p["category"] == "hotel"
            or p["category"] in interests_set
            or any(
                kw in p["name"].lower()
                for kw in interests_set
            )
            or any(
                t in interests_set
                for t in p.get("interest_tags", [])
            )
        ]

        # Safety fallback:
        # If filtering removes every place,
        # return the original city places instead.
        # This guarantees that the planning agent
        # always has candidate places to work with.
        return filtered if filtered else places

    # If no interests were supplied,
    # return all places for the city.
    return places