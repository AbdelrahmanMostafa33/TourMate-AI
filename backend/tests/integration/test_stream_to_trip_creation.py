# tests/integration/test_stream_to_trip_creation.py

"""
End-to-end test: Mock handle_chat_stream() async generator →
extract itinerary from 'result' event → create_trip_from_ai_result() →
verify ItineraryStop records are persisted in the database.

Mirrors the exact production flow in websocket_new_chat():
  async for chunk in handle_chat_stream(...):
      if chunk.get("type") == "result":
          result = chunk.get("data", {})
          if result.get("itinerary"):
              actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
  ...
  svc.create_trip_from_ai_result(user_id, {"itinerary": action["data"]})

Uses a fresh in-memory SQLite async database per test.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.itinerary import Itinerary, Day
from app.models.enums import TimeOfDay
from app.services.chat_service import ChatService


# ═════════════════════════════════════════════════════════════════════════════
# 1. Full Stream Result → DB (Happy Path)
# ═════════════════════════════════════════════════════════════════════════════


class TestStreamToTripCreation:
    """Simulate the production flow: stream result → trip → stops in DB."""

    @pytest.mark.asyncio
    async def test_full_stream_result_creates_stops_in_db(self, db_session):
        """
        Mock handle_chat_stream() as an async generator → extract the result
        event itinerary (as websocket_new_chat() does) → call
        create_trip_from_ai_result() → verify ItineraryStop records in DB.
        """
        # ── 1. Build the itinerary data that the stream would yield ──────
        itinerary_data = {
            "destination": "Cairo",
            "destination_country": "Egypt",
            "start_date": "2026-07-01",
            "end_date": "2026-07-03",
            "duration_days": 3,
            "number_of_travelers": 2,
            "budget": 2000,
            "accommodation_suggestions": [
                {
                    "name": "Steigenberger Tahrir",
                    "rating": 4.3,
                    "lat": 30.0429,
                    "lon": 31.2347,
                    "why_recommended": "Centrally located in downtown Cairo",
                },
            ],
            "days": [
                {
                    "day_number": 1,
                    "theme": "Pyramids Day",
                    "stops": [
                        {
                            "name": "Pyramids of Giza",
                            "category": "attractions",
                            "lat": 29.9792,
                            "lon": 31.1342,
                            "rating": 4.8,
                            "estimated_duration_minutes": 180,
                            "suggested_time_of_day": "morning",
                            "why_recommended": "Must see wonder",
                        },
                    ],
                },
                {
                    "day_number": 2,
                    "theme": "City Tour",
                    "stops": [
                        {
                            "name": "Egyptian Museum",
                            "category": "attractions",
                            "lat": 30.0478,
                            "lon": 31.2336,
                            "rating": 4.7,
                            "estimated_duration_minutes": 150,
                            "suggested_time_of_day": "morning",
                            "why_recommended": "Egyptian antiquities",
                        },
                    ],
                },
            ],
        }

        # ── 2. Build the mock stream generator — simulates handle_chat_stream ─
        async def mock_stream(user_id, user_message, token=None):
            yield {"type": "session", "data": {"session_id": "session_001"}}
            yield {"type": "text", "content": "Here is your itinerary! "}
            yield {"type": "text", "content": "Day 1: Pyramids... "}
            yield {"type": "result", "data": {
                "message": "Here is your 2-day Cairo itinerary!",
                "itinerary": itinerary_data,
                "phase": "itinerary_review",
            }}
            yield {"type": "done"}

        # ── 3. Iterate over chunks EXACTLY like websocket_new_chat() ─────
        #     This is the production event extraction logic from routes/chat.py
        extracted_actions = []
        async for chunk in mock_stream(
            user_id="stream_test_user",
            user_message="Plan me a trip to Cairo",
        ):
            event_type = chunk.get("type")

            if event_type == "result":
                result_data = chunk.get("data", {})
                if result_data.get("itinerary"):
                    extracted_actions.append({
                        "type": "CREATE_TRIP",
                        "data": result_data["itinerary"],
                    })
            # text/session/done events are forwarded to WebSocket —
            # we skip them here since we care about the result extraction

        # ── 4. Verify extraction worked ───────────────────────────────────
        assert len(extracted_actions) == 1, "Should have extracted 1 CREATE_TRIP action"
        action_data = extracted_actions[0]["data"]
        assert action_data["destination"] == "Cairo"
        assert len(action_data["days"]) == 2

        # ── 5. Call create_trip_from_ai_result with the extracted data ────
        svc = ChatService(db_session)
        created = await svc.create_trip_from_ai_result(
            user_id="stream_test_user",
            ai_result={"itinerary": action_data},
        )
        await db_session.commit()

        # ── 6. Verify trip and stops ──────────────────────────────────────
        assert created["trip_id"] is not None
        assert created["conversation_id"] is not None

        # 2 activity stops (hotels are now handled in HOTEL_SELECTION phase)
        expected_stops = 2
        assert created["stops_created"] == expected_stops, (
            f"Expected {expected_stops} stops, got {created['stops_created']}"
        )

        # Reload from DB with eager loading
        itinerary_id = created["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded is not None

        # 2 days created
        assert len(loaded.days) == 2

        days = sorted(loaded.days, key=lambda d: d.day_number)

        # Day 1: 1 activity stop
        day1 = days[0]
        assert day1.day_number == 1
        assert day1.theme == "Pyramids Day"
        assert day1.date == date(2026, 7, 1)
        assert len(day1.stops) == 1
        s1 = day1.stops[0]
        assert s1.place_snapshot["name"] == "Pyramids of Giza"
        assert s1.duration_minutes == 180
        assert s1.time_of_day == TimeOfDay.MORNING

        # Day 2: 1 activity stop (hotels are now handled in HOTEL_SELECTION phase)
        day2 = days[1]
        assert day2.day_number == 2
        assert day2.theme == "City Tour"
        assert day2.date == date(2026, 7, 2)

        day2_stops = sorted(day2.stops, key=lambda s: s.order_in_day)
        assert len(day2_stops) == 1
        assert day2_stops[0].place_snapshot["name"] == "Egyptian Museum"

    @pytest.mark.asyncio
    async def test_no_itinerary_in_stream_result(self, db_session):
        """When stream result has no 'itinerary' key → no crash, 0 stops."""
        stream_result = {
            "session_id": "session_002",
            "message": "I am not sure about that.",
            "response_type": "general_chat",
        }

        result_itinerary = stream_result.get("itinerary")
        assert result_itinerary is None

        svc = ChatService(db_session)
        created = await svc.create_trip_from_ai_result(
            user_id="stream_test_user2",
            ai_result={"response_type": "general_chat"},
        )
        await db_session.commit()

        assert created["trip_id"] is not None
        assert created["stops_created"] == 0

    @pytest.mark.asyncio
    async def test_websocket_new_chat_action_route(self, db_session):
        """
        Verify the exact action construction from websocket_new_chat():

            actions = [{"type": "CREATE_TRIP", "data": result["itinerary"]}]
            svc.create_trip_from_ai_result(user_id, {"itinerary": action["data"]})
        """
        result = {
            "session_id": "session_003",
            "message": "Your trip to Cairo!",
            "itinerary": {
                "destination": "Cairo",
                "duration_days": 1,
                "start_date": "2026-08-15",
                "days": [
                    {
                        "day_number": 1,
                        "theme": "Explore",
                        "stops": [
                            {
                                "name": "Al-Azhar Park",
                                "category": "attractions",
                                "lat": 30.0436,
                                "lon": 31.2496,
                                "rating": 4.4,
                                "estimated_duration_minutes": 120,
                                "suggested_time_of_day": "afternoon",
                                "why_recommended": "Peaceful escape",
                            },
                        ],
                    }
                ],
                "accommodation_suggestions": [],
            },
        }

        # This is exactly what websocket_new_chat() does:
        itinerary_data = result.get("itinerary")
        actions = [{"type": "CREATE_TRIP", "data": itinerary_data}]
        action_data = actions[0]["data"]

        svc = ChatService(db_session)
        created = await svc.create_trip_from_ai_result(
            user_id="route_test_user",
            ai_result={"itinerary": action_data},
        )
        await db_session.commit()

        # 1 activity stop, no hotel accommodation
        assert created["stops_created"] == 1

        # Verify the single stop
        itinerary_id = created["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert len(loaded.days) == 1
        assert loaded.days[0].stops[0].place_snapshot["name"] == "Al-Azhar Park"
