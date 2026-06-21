"""Repository for Itinerary, Day, and ItineraryStop operations."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.enums import ItineraryStatus, StopStatus
from app.repositories.base_repo import BaseRepository


class ItineraryRepo(BaseRepository):
    """Repository for Itinerary, Day, and ItineraryStop CRUD."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    # ── Itinerary ─────────────────────────────────────────────────────────

    async def create_itinerary(self, trip_id: str) -> Itinerary:
        """Create a new itinerary for a trip."""
        itinerary = Itinerary(
            itinerary_id=str(uuid.uuid4()),
            trip_id=trip_id,
            status=ItineraryStatus.draft,
        )
        self.session.add(itinerary)
        return itinerary

    async def get_by_trip_id(self, trip_id: str) -> Optional[Itinerary]:
        """Get the first itinerary for a trip."""
        result = await self.session.execute(
            select(Itinerary)
            .options(
                selectinload(Itinerary.days).selectinload(Day.stops),
            )
            .where(Itinerary.trip_id == trip_id)
            .order_by(Itinerary.created_at.desc())
        )
        return result.scalars().first()

    # ── Day ───────────────────────────────────────────────────────────────

    async def create_day(
        self,
        itinerary_id: str,
        day_number: int,
        date=None,
        theme: Optional[str] = None,
    ) -> Day:
        """Create a day within an itinerary."""
        day = Day(
            day_id=str(uuid.uuid4()),
            itinerary_id=itinerary_id,
            day_number=day_number,
            date=date,
            theme=theme,
        )
        self.session.add(day)
        return day

    # ── ItineraryStop ─────────────────────────────────────────────────────

    async def create_stop(
        self,
        day_id: str,
        place_id: Optional[str] = None,
        place_snapshot: Optional[dict] = None,
        scheduled_time=None,
        duration_minutes: Optional[int] = None,
        order_in_day: int = 0,
        time_of_day=None,
        minutes_from_prev_stop: Optional[int] = None,
        travel_mode=None,
        estimated_cost: Optional[float] = None,
        ai_notes: Optional[str] = None,
    ) -> ItineraryStop:
        """Create an itinerary stop."""
        stop = ItineraryStop(
            stop_id=str(uuid.uuid4()),
            day_id=day_id,
            place_id=place_id,
            place_snapshot=place_snapshot,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            order_in_day=order_in_day,
            time_of_day=time_of_day,
            minutes_from_prev_stop=minutes_from_prev_stop,
            travel_mode=travel_mode,
            estimated_cost=estimated_cost,
            ai_notes=ai_notes,
            status=StopStatus.planned,
        )
        self.session.add(stop)
        return stop
