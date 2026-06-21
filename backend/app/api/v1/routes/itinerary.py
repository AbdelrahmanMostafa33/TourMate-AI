"""
Itinerary routes — dedicated endpoints for itinerary data.

Provides a focused endpoint for the Flutter client to fetch the full
itinerary with nested days and stops, without the overhead of the
entire TripResponse object.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day  # Day needed by selectinload chain: Itinerary.days → Day.stops
from app.schemas.trip import ItineraryResponse

router = APIRouter()


@router.get("/{trip_id}", response_model=ItineraryResponse)
async def get_trip_itinerary(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the full itinerary for a trip, including days and stops.

    Returns a focused ``ItineraryResponse`` with nested ``DayResponse``
    objects (each containing ``StopResponse`` objects).  Stops are ordered
    by ``order_in_day`` within each day.  Days are ordered by ``day_number``.

    Args:
        trip_id: The trip to fetch the itinerary for.

    Returns:
        ItineraryResponse with days and stops, or 404 if the trip has
        no itinerary or doesn't belong to the current user.
    """
    # ── Verify trip belongs to user, load itineraries with days+stops ─────
    trip_result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops),
        )
        .where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = trip_result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if not trip.itineraries:
        raise HTTPException(status_code=404, detail="No itinerary found for this trip")

    # Return the most recent itinerary version
    itinerary = sorted(
        trip.itineraries,
        key=lambda i: (i.created_at or datetime.min, i.updated_at or datetime.min),
        reverse=True,
    )[0]

    return itinerary
