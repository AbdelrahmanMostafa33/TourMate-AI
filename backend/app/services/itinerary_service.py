# backend/app/services/itinerary_service.py

"""
Itinerary Service — creates full Itinerary / Day / ItineraryStop records
from the AI pipeline's ``optimized_itinerary`` output.

The AI pipeline (LangGraph) produces a structured itinerary dict with days,
stops, and accommodation suggestions.  This service translates that dict
into persistent DB records using ItineraryRepo.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.repositories.itinerary_repo import ItineraryRepo
from app.models.enums import TimeOfDay, TravelMode
from app.models.itinerary import Day as DayModel, ItineraryStop as StopModel, Itinerary

logger = logging.getLogger(__name__)

# ── Mapping Helpers ──────────────────────────────────────────────────────────

_TIME_OF_DAY_MAP = {
    "morning":   TimeOfDay.MORNING,
    "afternoon": TimeOfDay.AFTERNOON,
    "evening":   TimeOfDay.EVENING,
    "night":     TimeOfDay.NIGHT,
}

_TRAVEL_MODE_MAP = {
    "walking":  TravelMode.walking,
    "driving":  TravelMode.driving,
    "transit":  TravelMode.transit,
    "cycling":  TravelMode.cycling,
}


def _map_time_of_day(raw: Optional[str]) -> Optional[TimeOfDay]:
    if not raw:
        return None
    return _TIME_OF_DAY_MAP.get(raw.strip().lower())


def _map_travel_mode(raw: Optional[str]) -> Optional[TravelMode]:
    if not raw:
        return None
    return _TRAVEL_MODE_MAP.get(raw.strip().lower())


def _build_place_snapshot(stop: dict) -> dict:
    return {
        "name": stop.get("name", ""),
        "category": stop.get("category", ""),
        "sub_category": stop.get("sub_category", ""),
        "lat": stop.get("lat"),
        "lon": stop.get("lon"),
        "rating": stop.get("rating"),
        "address": stop.get("address", ""),
        "description": stop.get("description", ""),
        "phone": stop.get("phone", ""),
        "website": stop.get("website", ""),
        "photo": (stop.get("photos") or [None])[0],
        "maps_link": stop.get("maps_link", ""),
    }


class ItineraryService:
    """Service for creating and managing itinerary records from AI outputs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ItineraryRepo(db)

    async def create_stops_from_ai_days(
        self,
        itinerary_id: str,
        days_data: list[dict],
        accommodation_suggestions: Optional[list[dict]] = None,
        start_date: Optional[date] = None,
    ) -> int:
        total_stops = 0

        for day_data in days_data:
            day_number = day_data.get("day_number", 1)
            theme = day_data.get("theme", "")
            stops = day_data.get("stops", [])
            day_date = None
            if start_date:
                day_date = start_date + timedelta(days=day_number - 1)

            # ── Get or Create Day ──────────────────────────────────────────
            result = await self.db.execute(
                select(DayModel)
                .where(DayModel.itinerary_id == itinerary_id)
                .where(DayModel.day_number == day_number)
            )
            day = result.scalar_one_or_none()

            if day:
                # اليوم موجود — عدّل الـ theme بس
                day.theme = theme
                await self.db.flush()
            else:
                # اليوم مش موجود — أنشئ جديد
                day = await self.repo.create_day(
                    itinerary_id=itinerary_id,
                    day_number=day_number,
                    date=day_date,
                    theme=theme,
                )

            # ── امسح الـ stops القديمة للـ day ده ─────────────────────────
            await self.db.execute(
                delete(StopModel).where(StopModel.day_id == day.day_id)
            )
            await self.db.flush()

            # ── أضف الـ stops الجديدة ──────────────────────────────────────
            for order, stop_data in enumerate(stops):
                time_of_day = _map_time_of_day(stop_data.get("suggested_time_of_day"))
                travel_mode = _map_travel_mode(stop_data.get("transport_mode"))

                await self.repo.create_stop(
                    day_id=day.day_id,
                    place_id=stop_data.get("id"),
                    place_snapshot=_build_place_snapshot(stop_data),
                    duration_minutes=stop_data.get("estimated_duration_minutes"),
                    order_in_day=order + 1,
                    time_of_day=time_of_day,
                    minutes_from_prev_stop=stop_data.get("travel_time_to_next_minutes"),
                    travel_mode=travel_mode,
                    estimated_cost=stop_data.get("estimated_cost"),
                    ai_notes=stop_data.get("why_recommended"),
                )
                total_stops += 1

        if accommodation_suggestions and days_data:
            last_day_number = days_data[-1].get("day_number", 1)
            result = await self.db.execute(
                select(DayModel)
                .where(DayModel.itinerary_id == itinerary_id)
                .where(DayModel.day_number == last_day_number)
            )
            last_day = result.scalar_one_or_none()

            if last_day:
                max_order_result = await self.db.execute(
                    select(func.coalesce(func.max(StopModel.order_in_day), 0))
                    .where(StopModel.day_id == last_day.day_id)
                )
                next_order = (max_order_result.scalar() or 0) + 1

                for hotel in accommodation_suggestions:
                    await self.repo.create_stop(
                        day_id=last_day.day_id,
                        place_id=hotel.get("id"),
                        place_snapshot={
                            "name": hotel.get("name", ""),
                            "category": "hotel",
                            "sub_category": hotel.get("accommodation_type", "hotel"),
                            "rating": hotel.get("rating"),
                            "lat": hotel.get("lat"),
                            "lon": hotel.get("lon"),
                            "address": hotel.get("address", ""),
                        },
                        duration_minutes=None,
                        order_in_day=next_order,
                        time_of_day=TimeOfDay.NIGHT,
                        ai_notes=hotel.get("why_recommended"),
                    )
                    total_stops += 1
                    next_order += 1

        if total_stops > 0:
            logger.info(
                "[ItineraryService] Created %d stops across %d days for itinerary %s",
                total_stops, len(days_data), itinerary_id,
            )

        return total_stops

    async def save_candidate_pool(
        self,
        itinerary_id: str,
        pool_state: dict,
    ) -> None:
        """Persist the candidate pool snapshot for later edits."""
        if not pool_state:
            return

        result = await self.db.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary_id)
        )
        itinerary = result.scalar_one_or_none()
        if itinerary:
            itinerary.candidate_pool_json = pool_state
            await self.db.flush()
            logger.info(
                "[ItineraryService] Saved candidate pool for itinerary %s "
                "(filtered=%d, candidates=%d)",
                itinerary_id,
                len(pool_state.get("filtered_places") or []),
                len(pool_state.get("candidate_places") or []),
            )

    async def get_candidate_pool_by_trip_id(self, trip_id: str) -> dict | None:
        """Load the stored candidate pool for a trip's latest itinerary."""
        itinerary = await self.repo.get_by_trip_id(trip_id)
        if itinerary and itinerary.candidate_pool_json:
            return itinerary.candidate_pool_json
        return None

    async def create_full_from_ai_result(
        self,
        trip_id: str,
        ai_result: dict,
    ) -> dict:
        itinerary_data = ai_result.get("itinerary", {})
        if not itinerary_data:
            logger.warning(
                "[ItineraryService] create_full_from_ai_result called without itinerary data"
            )
            return {"itinerary_id": None, "stops_created": 0}

        days_data = itinerary_data.get("days", [])
        accommodations = itinerary_data.get("accommodation_suggestions")

        if not days_data:
            logger.info(
                "[ItineraryService] No days data in AI result for trip %s", trip_id,
            )
            return {"itinerary_id": None, "stops_created": 0}

        existing = await self.repo.get_by_trip_id(trip_id)
        if existing:
            itinerary = existing
            # Increment version when updating an existing itinerary
            itinerary.version_number = (itinerary.version_number or 1) + 1
            itinerary.updated_at = func.now()

            # Touch TripProfile updated_at when itinerary changes
            from app.models.profile import TripProfile
            profile_result = await self.db.execute(
                select(TripProfile).where(TripProfile.trip_id == trip_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                profile.updated_at = func.now()
        else:
            itinerary = await self.repo.create_itinerary(trip_id)

        stops_created = await self.create_stops_from_ai_days(
            itinerary_id=itinerary.itinerary_id,
            days_data=days_data,
            accommodation_suggestions=accommodations,
        )

        return {
            "itinerary_id": itinerary.itinerary_id,
            "stops_created": stops_created,
        }