import httpx
from typing import Optional

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"


async def get_duration(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calls OSRM API to get driving duration between two points in minutes.
    """
    url = f"{OSRM_BASE_URL}/{lon1},{lat1};{lon2},{lat2}?overview=false"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok" and data.get("routes"):
                # duration is in seconds, convert to minutes
                duration_seconds = data["routes"][0]["duration"]
                return duration_seconds / 60.0
        except Exception as e:
            print(f"OSRM API error: {e}")

    # Fallback to a default if API fails
    return 30.0
