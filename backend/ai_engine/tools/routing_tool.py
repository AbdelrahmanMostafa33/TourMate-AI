from typing import List
from app.external.osrm_client import get_duration


async def get_travel_time_minutes(origin: dict, destination: dict) -> float:
    """
    Returns estimated travel time in minutes between two lat/lon points.
    """
    return await get_duration(origin["lat"], origin["lon"], destination["lat"], destination["lon"])


def order_stops_by_proximity(stops: List[dict]) -> List[dict]:
    """
    Reorders stops to minimize total travel time using a greedy nearest-neighbor approach.
    """
    if not stops:
        return []

    unvisited = stops[:]
    ordered = [unvisited.pop(0)]

    while unvisited:
        current = ordered[-1]
        # Simple Euclidean distance for greedy ordering (good enough for proximity)
        next_stop = min(unvisited, key=lambda x: (x["lat"] - current["lat"]) ** 2 + (x["lon"] - current["lon"]) ** 2)
        ordered.append(next_stop)
        unvisited.remove(next_stop)

    return ordered
