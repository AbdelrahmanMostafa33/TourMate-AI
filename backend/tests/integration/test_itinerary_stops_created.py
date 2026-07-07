# tests/integration/test_itinerary_stops_created.py

"""
Integration test: When a trip is created via ChatService.create_trip_from_ai_result()
with stop-level AI itinerary data, ItineraryStop records must be persisted.

Validates Phase 5 integration:
  - ItineraryService.create_stops_from_ai_days() is called inside
    ChatService.create_trip_from_ai_result()
  - Day + ItineraryStop records are created in the database
  - Data integrity (names, durations, costs, coordinates) is preserved

Uses a fresh in-memory SQLite async database for each test.
"""

import pytest
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day
from app.models.enums import TimeOfDay, TravelMode
from app.services.chat_service import ChatService


# ── Sample AI Itinerary Data ──────────────────────────────────────────────

SAMPLE_AI_RESULT = {
    "itinerary": {
        "destination": "Cairo",
        "destination_country": "Egypt",
        "start_date": "2026-07-01",
        "end_date": "2026-07-04",
        "duration_days": 4,
        "number_of_travelers": 2,
        "budget": 1500,
        "accommodation_suggestions": [
            {
                "name": "Marriott Mena House",
                "rating": 4.6,
                "lat": 29.9758,
                "lon": 31.1334,
                "address": "Pyramids Area, Giza",
                "why_recommended": "Luxury hotel with pyramid views",
                "accommodation_type": "luxury",
            },
        ],
        "days": [
            {
                "day_number": 1,
                "theme": "Pyramids & Ancient History",
                "stops": [
                    {
                        "name": "Pyramids of Giza",
                        "category": "attractions",
                        "sub_category": "historic",
                        "lat": 29.9792,
                        "lon": 31.1342,
                        "rating": 4.8,
                        "address": "Giza, Egypt",
                        "description": "The last remaining Wonder of the Ancient World",
                        "why_recommended": "Must-see ancient wonder",
                        "estimated_duration_minutes": 180,
                        "suggested_time_of_day": "morning",
                        "estimated_cost": 20.0,
                    },
                    {
                        "name": "Great Sphinx",
                        "category": "attractions",
                        "sub_category": "historic",
                        "lat": 29.9753,
                        "lon": 31.1376,
                        "rating": 4.7,
                        "why_recommended": "Iconic monument",
                        "estimated_duration_minutes": 60,
                        "suggested_time_of_day": "morning",
                        "estimated_cost": 10.0,
                    },
                    {
                        "name": "Abu Shukri Restaurant",
                        "category": "restaurant",
                        "sub_category": "local cuisine",
                        "lat": 30.0464,
                        "lon": 31.2325,
                        "rating": 4.5,
                        "why_recommended": "Best koshari in Cairo",
                        "estimated_duration_minutes": 60,
                        "suggested_time_of_day": "afternoon",
                        "estimated_cost": 8.0,
                    },
                ],
            },
            {
                "day_number": 2,
                "theme": "Museums & Markets",
                "stops": [
                    {
                        "name": "Egyptian Museum",
                        "category": "attractions",
                        "sub_category": "museum",
                        "lat": 30.0478,
                        "lon": 31.2336,
                        "rating": 4.7,
                        "why_recommended": "World-class artifacts including Tutankhamun",
                        "estimated_duration_minutes": 150,
                        "suggested_time_of_day": "morning",
                        "estimated_cost": 15.0,
                    },
                    {
                        "name": "Khan El Khalili Bazaar",
                        "category": "attractions",
                        "sub_category": "market",
                        "lat": 30.0478,
                        "lon": 31.2336,
                        "rating": 4.5,
                        "why_recommended": "Great for souvenirs and local crafts",
                        "estimated_duration_minutes": 120,
                        "suggested_time_of_day": "afternoon",
                        "estimated_cost": 0,
                    },
                ],
            },
        ],
    }
}


SAMPLE_AI_RESULT_NO_STOPS = {
    "itinerary": {
        "destination": "Cairo",
        "destination_country": "Egypt",
        "start_date": "2026-07-01",
        "end_date": "2026-07-04",
        "duration_days": 4,
        "number_of_travelers": 2,
        "budget": 1500,
        "days": [
            {"day_number": 1, "theme": "Day 1"},
            {"day_number": 2, "theme": "Day 2"},
            {"day_number": 3, "theme": "Day 3"},
        ],
    }
}


# ═════════════════════════════════════════════════════════════════════════════
# 1. Happy Path — ItineraryStop Records Created
# ═════════════════════════════════════════════════════════════════════════════


class TestItineraryStopCreation:
    """ItineraryStop records are created from AI itinerary data."""

    @pytest.mark.asyncio
    async def test_stops_created_with_stop_data(self, db_session):
        """AI result with days + stops → ItineraryStop records in DB."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_001",
            ai_result=SAMPLE_AI_RESULT,
        )
        await db_session.commit()

        # ── Verify high-level creation ────────────────────────────────────
        assert result["trip_id"] is not None
        assert result["conversation_id"] is not None
        assert result["itinerary"] is not None
        assert result["stops_created"] > 0, "No ItineraryStop records created!"

        # ── Reload with eager loading ─────────────────────────────────────
        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded is not None, "Itinerary not found in DB"

        # ── Verify days ───────────────────────────────────────────────────
        assert len(loaded.days) == 2, f"Expected 2 days, got {len(loaded.days)}"

        day1, day2 = loaded.days
        assert day1.day_number == 1
        assert day1.theme == "Pyramids & Ancient History"
        assert day1.date == date(2026, 7, 1)

        assert day2.day_number == 2
        assert day2.theme == "Museums & Markets"
        assert day2.date == date(2026, 7, 2)

        # ── Verify stops per day ─────────────────────────────────────────
        day1_stops = sorted(day1.stops, key=lambda s: s.order_in_day)
        day2_stops = sorted(day2.stops, key=lambda s: s.order_in_day)

        # Day 1: 3 activity stops + 1 hotel (accommodation appended to last day)
        assert len(day1_stops) == 3, f"Day 1 should have 3 stops, got {len(day1_stops)}"
        # Day 2: 2 activity stops (hotels are now handled in HOTEL_SELECTION phase)
        assert len(day2_stops) == 2, f"Day 2 should have 2 stops, got {len(day2_stops)}"

        # ── Verify stop data integrity ────────────────────────────────────
        # Stop 1: Pyramids of Giza
        s0 = day1_stops[0]
        assert s0.place_snapshot["name"] == "Pyramids of Giza"
        assert s0.place_snapshot["category"] == "attractions"
        assert s0.place_snapshot["sub_category"] == "historic"
        assert s0.place_snapshot["lat"] == 29.9792
        assert s0.place_snapshot["lon"] == 31.1342
        assert s0.duration_minutes == 180
        assert s0.order_in_day == 1
        assert s0.time_of_day == TimeOfDay.MORNING
        assert s0.estimated_cost == 20.0
        assert s0.ai_notes == "Must-see ancient wonder"

        # Stop 2: Great Sphinx
        s1 = day1_stops[1]
        assert s1.place_snapshot["name"] == "Great Sphinx"
        assert s1.duration_minutes == 60
        assert s1.order_in_day == 2
        assert s1.time_of_day == TimeOfDay.MORNING

        # Stop 3: Abu Shukri
        s2 = day1_stops[2]
        assert s2.place_snapshot["name"] == "Abu Shukri Restaurant"
        assert s2.place_snapshot["category"] == "restaurant"
        assert s2.duration_minutes == 60
        assert s2.order_in_day == 3
        assert s2.time_of_day == TimeOfDay.AFTERNOON
        assert s2.estimated_cost == 8.0

        # Stop 4 (Day 2 Stop 1): Egyptian Museum
        s3 = day2_stops[0]
        assert s3.place_snapshot["name"] == "Egyptian Museum"
        assert s3.duration_minutes == 150
        assert s3.order_in_day == 1
        assert s3.time_of_day == TimeOfDay.MORNING

        # Stop 5 (Day 2 Stop 2): Khan El Khalili
        s4 = day2_stops[1]
        assert s4.place_snapshot["name"] == "Khan El Khalili Bazaar"
        assert s4.duration_minutes == 120
        assert s4.order_in_day == 2
        assert s4.time_of_day == TimeOfDay.AFTERNOON

        # NOTE: Hotels are handled in the post-approval HOTEL_SELECTION phase
        # (like flights), so they are no longer stored as itinerary stops.

    @pytest.mark.asyncio
    async def test_stops_count_returns_correct_value(self, db_session):
        """stops_created field reflects the correct count."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_002",
            ai_result=SAMPLE_AI_RESULT,
        )
        await db_session.commit()

        # 3 stops on day 1 + 2 stops on day 2 (hotels now handled in HOTEL_SELECTION phase)
        expected_stops = 3 + 2
        assert (
            result["stops_created"] == expected_stops
        ), f"Expected {expected_stops} stops, got {result['stops_created']}"

    @pytest.mark.asyncio
    async def test_skeleton_days_created_when_no_stops(self, db_session):
        """AI result with days but no stops → skeleton Day records only."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_003",
            ai_result=SAMPLE_AI_RESULT_NO_STOPS,
        )
        await db_session.commit()

        assert result["stops_created"] == 0, "Expected 0 stops for skeleton-only data"

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()

        assert len(loaded.days) == 3, "Expected 3 skeleton days"
        assert loaded.days[0].day_number == 1
        assert loaded.days[1].day_number == 2
        assert loaded.days[2].day_number == 3

        # No stops on any day
        for day in loaded.days:
            assert len(day.stops) == 0, "Skeleton days should have no stops"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Edge Cases
# ═════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases for the ItineraryStop creation flow."""

    @pytest.mark.asyncio
    async def test_empty_days_list_creates_skeleton_from_duration(self, db_session):
        """No days in AI result → skeleton days created from duration."""
        ai_result = {
            "itinerary": {
                "destination": "Cairo",
                "start_date": "2026-07-01",
                "end_date": "2026-07-05",
                "duration_days": 5,
                "number_of_travelers": 1,
            }
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_004", ai_result)
        await db_session.commit()

        assert result["stops_created"] == 0

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert len(loaded.days) == 5, "Expected 5 skeleton days from duration"

    @pytest.mark.asyncio
    async def test_no_itinerary_in_ai_result(self, db_session):
        """Missing itinerary key → no crash, stops_created = 0."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_005",
            ai_result={"response_type": "error"},
        )
        await db_session.commit()

        assert result["trip_id"] is not None  # Still creates trip
        assert result["stops_created"] == 0

    @pytest.mark.asyncio
    async def test_days_with_mixed_empty_and_full_stops(self, db_session):
        """Some days with stops, some without → both days created, day 2 has 0 stops."""
        ai_result = {
            "itinerary": {
                "destination": "Cairo",
                "start_date": "2026-08-01",
                "end_date": "2026-08-03",
                "days": [
                    {
                        "day_number": 1,
                        "theme": "Full day",
                        "stops": [
                            {
                                "name": "Cairo Tower",
                                "category": "attractions",
                                "lat": 30.0458,
                                "lon": 31.2247,
                                "estimated_duration_minutes": 90,
                                "suggested_time_of_day": "afternoon",
                            }
                        ],
                    },
                    {
                        "day_number": 2,
                        "theme": "No stops day",
                        "stops": [],
                    },
                ],
            }
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_006", ai_result)
        await db_session.commit()

        # Day 1 has 1 stop + no hotel accommodation (none in data)
        assert result["stops_created"] == 1

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()

        # Both days are always created by create_stops_from_ai_days()
        assert len(loaded.days) == 2, "All days from days_data are created, even empty ones"

        day1, day2 = loaded.days
        assert len(day1.stops) == 1
        assert day1.stops[0].place_snapshot["name"] == "Cairo Tower"
        assert len(day2.stops) == 0, "Day 2 has stops=[], so 0 stops created"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Conversation + Trip Integrity
# ═════════════════════════════════════════════════════════════════════════════


class TestTripConversationIntegrity:
    """Trip, Conversation, and Itinerary linkage is preserved."""

    @pytest.mark.asyncio
    async def test_trip_linked_to_conversation_and_itinerary(self, db_session):
        """Trip → Conversation FK + Itinerary FK chains are correct."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_010", SAMPLE_AI_RESULT)
        await db_session.commit()

        # Reload trip with relationships
        query = (
            select(Trip)
            .options(
                selectinload(Trip.conversation),
                selectinload(Trip.itineraries).selectinload(Itinerary.days),
            )
            .where(Trip.trip_id == result["trip_id"])
        )
        trip = (await db_session.execute(query)).scalars().first()
        assert trip is not None

        # Trip → Conversation
        assert trip.conversation is not None
        assert trip.conversation.conversation_id == result["conversation_id"]

        # Trip → Itinerary
        assert len(trip.itineraries) == 1
        assert trip.itineraries[0].itinerary_id == result["itinerary"].itinerary_id

    @pytest.mark.asyncio
    async def test_multiple_calls_create_separate_trips(self, db_session):
        """Two calls to create_trip_from_ai_result produce separate records."""
        svc = ChatService(db_session)
        r1 = await svc.create_trip_from_ai_result("user_020", SAMPLE_AI_RESULT)
        r2 = await svc.create_trip_from_ai_result("user_020", SAMPLE_AI_RESULT)
        await db_session.commit()

        assert r1["trip_id"] != r2["trip_id"], "Trip IDs must be unique"
        assert r1["conversation_id"] != r2["conversation_id"], "Conversation IDs must be unique"


# ═════════════════════════════════════════════════════════════════════════════
# 4. TimeOfDay and TravelMode Enum Mapping
# ═════════════════════════════════════════════════════════════════════════════


class TestEnumMapping:
    """TimeOfDay and TravelMode enum values are correctly mapped from AI output."""

    @pytest.mark.asyncio
    async def test_all_time_of_day_variants(self, db_session):
        """All four TimeOfDay variants are correctly mapped."""
        ai_result = {
            "itinerary": {
                "destination": "Cairo",
                "days": [
                    {
                        "day_number": 1,
                        "stops": [
                            {
                                "name": "Morning Stop",
                                "suggested_time_of_day": "morning",
                                "lat": 30.0,
                                "lon": 31.0,
                            },
                            {
                                "name": "Afternoon Stop",
                                "suggested_time_of_day": "afternoon",
                                "lat": 30.0,
                                "lon": 31.0,
                            },
                            {
                                "name": "Evening Stop",
                                "suggested_time_of_day": "evening",
                                "lat": 30.0,
                                "lon": 31.0,
                            },
                            {
                                "name": "Night Stop",
                                "suggested_time_of_day": "night",
                                "lat": 30.0,
                                "lon": 31.0,
                            },
                        ],
                    }
                ],
            }
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_030", ai_result)
        await db_session.commit()

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        stops = sorted(loaded.days[0].stops, key=lambda s: s.order_in_day)

        assert stops[0].time_of_day == TimeOfDay.MORNING
        assert stops[1].time_of_day == TimeOfDay.AFTERNOON
        assert stops[2].time_of_day == TimeOfDay.EVENING
        assert stops[3].time_of_day == TimeOfDay.NIGHT

    @pytest.mark.asyncio
    async def test_travel_mode_mapping(self, db_session):
        """TravelMode and minutes_from_prev_stop are correctly mapped."""
        ai_result = {
            "itinerary": {
                "destination": "Cairo",
                "days": [
                    {
                        "day_number": 1,
                        "stops": [
                            {
                                "name": "Stop A",
                                "lat": 30.0,
                                "lon": 31.0,
                                "transport_mode": "walking",
                                "travel_time_to_next_minutes": 15,
                            },
                            {
                                "name": "Stop B",
                                "lat": 30.05,
                                "lon": 31.05,
                                "transport_mode": "driving",
                                "travel_time_to_next_minutes": 25,
                            },
                            {
                                "name": "Stop C",
                                "lat": 30.1,
                                "lon": 31.1,
                                "transport_mode": "transit",
                            },
                            {
                                "name": "Stop D",
                                "lat": 30.15,
                                "lon": 31.15,
                                # No transport_mode → None
                            },
                        ],
                    }
                ],
            }
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_031", ai_result)
        await db_session.commit()

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        stops = sorted(loaded.days[0].stops, key=lambda s: s.order_in_day)

        # Stop A: walking + 15 min travel to next
        assert stops[0].travel_mode == TravelMode.walking
        assert stops[0].minutes_from_prev_stop == 15
        assert stops[0].order_in_day == 1

        # Stop B: driving + 25 min travel to next
        assert stops[1].travel_mode == TravelMode.driving
        assert stops[1].minutes_from_prev_stop == 25
        assert stops[1].order_in_day == 2

        # Stop C: transit, no travel_time_to_next_minutes → None
        assert stops[2].travel_mode == TravelMode.transit
        assert stops[2].minutes_from_prev_stop is None
        assert stops[2].order_in_day == 3

        # Stop D: no transport_mode → None
        assert stops[3].travel_mode is None
        assert stops[3].order_in_day == 4

    @pytest.mark.asyncio
    async def test_null_time_of_day_is_none(self, db_session):
        """Missing suggested_time_of_day → time_of_day is None."""
        ai_result = {
            "itinerary": {
                "destination": "Cairo",
                "days": [{
                    "day_number": 1,
                    "stops": [{
                        "name": "No Time stop",
                        "lat": 30.0,
                        "lon": 31.0,
                    }],
                }],
            }
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result("user_032", ai_result)
        await db_session.commit()

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded.days[0].stops[0].time_of_day is None

