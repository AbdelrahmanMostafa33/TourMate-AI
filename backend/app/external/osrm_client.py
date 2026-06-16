import httpx
from typing import Optional

OSRM_BASE_URL = "https://router.project-osrm.org"

# Fallback duration (minutes) when the API is unreachable.
_DEFAULT_DURATION_MIN = 30.0


async def get_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calls OSRM route API to get driving duration between two points in minutes.

    Kept for backward compatibility — prefer get_travel_time_matrix() for
    batch computation.
    """
    url = f"{OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok" and data.get("routes"):
                duration_seconds = data["routes"][0]["duration"]
                return duration_seconds / 60.0
        except Exception as e:
            print(f"OSRM route API error: {e}")

    return _DEFAULT_DURATION_MIN


async def get_travel_time_matrix(
    stops: list[dict],
    profile: str = "driving",
) -> list[list[float]]:
    """
    Call the OSRM Table API to compute the full NxN travel-time matrix
    for a list of stops in a single HTTP request.

    Args:
        stops:   List of dicts with 'lat' and 'lon' keys.
        profile: OSRM profile — 'driving', 'walking', or 'cycling'.

    Returns:
        NxN matrix where matrix[i][j] is the duration in minutes
        from stop i to stop j. Diagonal is 0. On failure, returns an
        NxN matrix filled with _DEFAULT_DURATION_MIN.
    """
    n = len(stops)
    if n <= 1:
        return [[0.0]]

    # Build the coordinate string: lon1,lat1;lon2,lat2;...
    coords = ";".join(
        f"{s['lon']},{s['lat']}" for s in stops
    )
    url = (
        f"{OSRM_BASE_URL}/table/v1/{profile}/{coords}"
        f"?annotations=duration"
    )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok":
                # durations is NxN in seconds — convert to minutes.
                durations = data["durations"]
                return [
                    [round(d / 60.0, 1) if d is not None else _DEFAULT_DURATION_MIN
                     for d in row]
                    for row in durations
                ]
        except Exception as e:
            print(f"OSRM table API ({profile}) error: {e}")

    # Fallback: fill matrix with default duration.
    return [[0.0 if i == j else _DEFAULT_DURATION_MIN for j in range(n)] for i in range(n)]
