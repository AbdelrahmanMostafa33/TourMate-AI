"""Haversine distance utility for geographic proximity calculations."""

import math

# Earth's radius in kilometers
EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.

    Args:
        lat1, lon1: Latitude and longitude of point 1 (in degrees)
        lat2, lon2: Latitude and longitude of point 2 (in degrees)

    Returns:
        Distance in kilometers
    """
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return EARTH_RADIUS_KM * c
