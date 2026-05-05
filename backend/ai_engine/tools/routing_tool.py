# backend/ai_engine/tools/routing_tool.py

from typing import List

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 3: Mock implementation.
# Sprint 4 (Task 4.3): Replace the bodies of both functions with calls to:
#   from app.external.osrm_client import get_duration
#   return get_duration(origin["lat"], origin["lon"], dest["lat"], dest["lon"])
# Function signatures and return shapes stay the same.
# ─────────────────────────────────────────────────────────────────────────────


def get_travel_time_minutes(origin: dict, destination: dict) -> float:
    """
    Returns estimated travel time in minutes between two lat/lon points.

    Each point is a dict with keys "lat" and "lon" (floats).

    Sprint 3: Always returns 20.0 minutes (flat mock).
    Sprint 4: Calls osrm_client.get_duration() for real road-based estimates.

    Args:
        origin:      Starting point. E.g. {"lat": 30.0478, "lon": 31.2336}
        destination: End point.       E.g. {"lat": 29.9792, "lon": 31.1342}

    Returns:
        Estimated travel time in minutes as a float.
    """
    # Sprint 4: replace with →
    # from app.external.osrm_client import get_duration
    # return get_duration(origin["lat"], origin["lon"],
    #                     destination["lat"], destination["lon"])
    return 20.0


def order_stops_by_proximity(stops: List[dict]) -> List[dict]:
    """
    Reorders stops to minimize total travel time (nearest-neighbor).

    Each stop must have "lat" and "lon" keys.

    Sprint 3: Returns the input list unchanged (no-op).
    Sprint 4: Implements nearest-neighbor greedy ordering using
              get_travel_time_minutes() between consecutive stops.

    Args:
        stops: List of place dicts, each with at least "lat" and "lon".

    Returns:
        Reordered list of stops (Sprint 3: same order as input).
    """
    # Sprint 4: implement greedy nearest-neighbor here
    return stops