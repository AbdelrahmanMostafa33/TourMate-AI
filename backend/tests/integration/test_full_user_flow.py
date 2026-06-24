"""
End-to-end integration test: Full user flow via process_message_stream.

Simulates the complete lifecycle:
  1. Trip created in DB (simulating AI itinerary generation)
  2. User chats → AI returns itinerary update (CREATE_TRIP action)
  3. User approves → AI returns approval event
  4. Verify all DB state changes and WebSocket notifications

Uses a fresh in-memory SQLite async database per test.
Mocks handle_chat_stream() to yield controlled AI responses.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.profile import TripProfile
from app.models.chat import Conversation
from app.models.enums import TripStatus, ItineraryStatus, ConversationStatus
from app.services.chat_service import ChatService


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


async def _create_trip_in_db(db_session, user_id: str = "full_flow_user") -> dict:
    """Create a trip + itinerary + profile + conversation in the DB.

    Returns ORM objects so tests can inspect initial state.
    """
    svc = ChatService(db_session)

    ai_result = {
        "itinerary": {
            "destination": "Cairo",
            "destination_country": "Egypt",
            "start_date": "2026-07-01",
            "end_date": "2026-07-03",
            "duration_days": 3,
            "number_of_travelers": 2,
            "days": [
                {
                    "day_number": 1,
                    "theme": "History Day",
                    "stops": [
                        {
                            "name": "Pyramids of Giza",
                            "category": "attractions",
                            "sub_category": "historic",
                            "lat": 29.9792,
                            "lon": 31.1342,
                            "rating": 4.8,
                            "estimated_duration_minutes": 180,
                            "suggested_time_of_day": "morning",
                            "why_recommended": "Must-see ancient wonder",
                        },
                    ],
                },
            ],
            "accommodation_suggestions": [],
        },
        "profile": {
            "budget_level": "moderate",
            "travel_style": "cultural",
            "pace": "moderate",
            "interests": ["history", "art"],
            "food_preferences": ["local cuisine"],
            "accommodation_preferences": ["boutique hotel"],
        },
    }

    created = await svc.create_trip_from_ai_result(user_id, ai_result)
    await db_session.commit()

    # Reload with relationships
    result = await db_session.execute(
        select(Trip)
        .options(
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops),
            selectinload(Trip.trip_profiles),
            selectinload(Trip.conversation),
        )
        .where(Trip.trip_id == created["trip"].trip_id)
    )
    trip = result.scalar_one()

    return {
        "trip": trip,
        "itinerary": trip.itineraries[0] if trip.itineraries else None,
        "profile": trip.trip_profiles[0] if trip.trip_profiles else None,
        "conversation": trip.conversation,
    }


def _utc_ts(dt: datetime) -> float:
    """Return UTC timestamp, handling both naive and aware datetimes."""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None).timestamp()
    return dt.timestamp()


# ═════════════════════════════════════════════════════════════════════════════
# Full User Flow Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestFullUserFlow:
    """Complete user flow: message → create/modify itinerary → approve → verify."""

    # ── Phase 1: Trip Itinerary Update via process_message_stream ────────

    @pytest.mark.asyncio
    async def test_phase1_create_trip_via_stream(self, db_session):
        """process_message_stream handles CREATE_TRIP result → version bumps + TripProfile touch."""
        data = await _create_trip_in_db(db_session, "phase1_user")
        trip = data["trip"]
        itinerary = data["itinerary"]
        profile = data["profile"]

        assert itinerary.version_number == 1
        generated_ts = _utc_ts(profile.generated_at)

        # Build mock stream that yields a CREATE_TRIP result
        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_phase1"}}
            yield {"type": "phase", "data": {"phase": "itinerary_review"}}
            yield {"type": "text", "content": "Here's your updated plan! "}
            yield {
                "type": "result",
                "data": {
                    "action": "create_trip",
                    "message": "Here's your 3-day Cairo itinerary!",
                    "itinerary": {
                        "destination": "Cairo",
                        "days": [
                            {
                                "day_number": 1,
                                "theme": "Updated History Day",
                                "stops": [
                                    {
                                        "name": "Egyptian Museum",
                                        "category": "attractions",
                                        "sub_category": "museum",
                                        "lat": 30.0478,
                                        "lon": 31.2336,
                                        "rating": 4.7,
                                        "estimated_duration_minutes": 150,
                                        "suggested_time_of_day": "morning",
                                        "why_recommended": "Updated stop",
                                    },
                                ],
                            },
                        ],
                        "accommodation_suggestions": [],
                    },
                    "phase": "itinerary_review",
                },
            }
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_phase1"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                returned_session_id = await process_message_stream(
                    user_text="Update my itinerary",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="phase1_user",
                    token="mock_token",
                )

                # ── Verify session_id is returned ────────────────────────────
                assert returned_session_id == "sess_phase1"

                # ── Verify version incremented ───────────────────────────────
                itin_r = (
                    await db_session.execute(
                        select(Itinerary).where(
                            Itinerary.itinerary_id == itinerary.itinerary_id
                        )
                    )
                ).scalar_one()
                assert itin_r.version_number == 2

                # ── Verify TripProfile updated_at advanced ────────────────────
                prof_r = (
                    await db_session.execute(
                        select(TripProfile).where(
                            TripProfile.profile_id == profile.profile_id
                        )
                    )
                ).scalar_one()
                assert _utc_ts(prof_r.updated_at) > generated_ts, (
                    "TripProfile.updated_at should advance"
                )

                # ── Verify updated_at >= created_at for itinerary ───────────
                # (SQLite func.now() has second-level precision, so >= not >)
                assert _utc_ts(itin_r.updated_at) >= _utc_ts(itin_r.created_at)

            finally:
                manager.disconnect(ws_key)

        print("  ✅ Phase 1: Trip creation via stream — version, timestamps verified")

    # ── Phase 2: Approval via process_message_stream ─────────────────────

    @pytest.mark.asyncio
    async def test_phase2_approve_via_stream(self, db_session):
        """process_message_stream handles approval → trip/itin status, approved_at, trip_approved event."""
        data = await _create_trip_in_db(db_session, "phase2_user")
        trip = data["trip"]
        itinerary = data["itinerary"]

        # Initial state checks
        assert trip.status == TripStatus.planning
        assert itinerary.status == ItineraryStatus.draft
        assert trip.approved_at is None
        assert itinerary.version_number == 1

        created_ts_trip = _utc_ts(trip.created_at)
        created_ts_itin = _utc_ts(itinerary.created_at)
        generated_ts_prof = (
            _utc_ts(data["profile"].generated_at) if data["profile"] else 0
        )

        # Build mock stream that yields approval events
        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_phase2"}}
            yield {"type": "phase", "data": {"phase": "completed"}}
            yield {"type": "text", "content": "Your trip is approved! 🎉 "}
            yield {
                "type": "result",
                "data": {
                    "action": "approve_itinerary",
                    "message": "Your trip to Cairo is approved! 🎉",
                    "itinerary": {"destination": "Cairo", "days": []},
                    "phase": "completed",
                },
            }
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_phase2"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                returned_session_id = await process_message_stream(
                    user_text="I approve this trip",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="phase2_user",
                    token="mock_token",
                )

                # ── Verify session_id returned ───────────────────────────────
                assert returned_session_id == "sess_phase2"

                # ── Verify trip_approved WebSocket event ─────────────────────
                # manager.send calls ws.send_json(data)
                sent_calls = mock_ws.send_json.call_args_list
                sent_types = [call[0][0].get("type") for call in sent_calls]
                assert "trip_approved" in sent_types, (
                    f"Expected 'trip_approved' event, got: {sent_types}"
                )

                # ── Verify DB: trip status → active ───────────────────────────
                result = await db_session.execute(
                    select(Trip)
                    .options(
                        selectinload(Trip.itineraries),
                        selectinload(Trip.trip_profiles),
                    )
                    .where(Trip.trip_id == trip.trip_id)
                )
                trip_r = result.scalar_one()

                assert trip_r.status == TripStatus.active

                # ── Verify DB: approved_at set ────────────────────────────────
                assert trip_r.approved_at is not None
                assert _utc_ts(trip_r.approved_at) >= created_ts_trip

                # ── Verify DB: itinerary status → active ──────────────────────
                itin_r = trip_r.itineraries[0]
                assert itin_r.status == ItineraryStatus.active

                # ── Verify DB: updated_at >= created_at for itinerary ──────────
                # (SQLite func.now() has second-level precision, so >= not >)
                assert _utc_ts(itin_r.updated_at) >= created_ts_itin

                # ── Verify DB: version NOT incremented on approval ────────────
                assert itin_r.version_number == 1

                # ── Verify DB: TripProfile updated_at advanced ──────────────────
                if trip_r.trip_profiles:
                    prof_r = trip_r.trip_profiles[0]
                    assert _utc_ts(prof_r.updated_at) > generated_ts_prof

            finally:
                manager.disconnect(ws_key)

        print("  ✅ Phase 2: Approval via stream — status, approved_at, timestamps, notification verified")

    # ── Phase 3: Full Create → Modify → Approve Lifecycle ────────────────

    @pytest.mark.asyncio
    async def test_phase3_full_lifecycle(self, db_session):
        """Complete lifecycle: create → modify → approve, all DB state correct."""
        import asyncio

        user_id = "lifecycle_user"
        data = await _create_trip_in_db(db_session, user_id)
        trip = data["trip"]
        itinerary = data["itinerary"]

        # ── State before any action ─────────────────────────────────────
        assert trip.status == TripStatus.planning
        assert itinerary.status == ItineraryStatus.draft
        assert itinerary.version_number == 1
        assert trip.approved_at is None

        # Track timestamps
        created_ts_trip = _utc_ts(trip.created_at)
        created_ts_itin = _utc_ts(itinerary.created_at)

        # ── Step 1: Modify itinerary (simulate AI re-plan) ──────────────

        async def mock_modify_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_mod_001"}}
            yield {"type": "phase", "data": {"phase": "itinerary_review"}}
            yield {"type": "text", "content": "Updated plan! "}
            yield {
                "type": "result",
                "data": {
                    "action": "create_trip",
                    "message": "Here is your updated itinerary!",
                    "itinerary": {
                        "destination": "Cairo",
                        "days": [
                            {
                                "day_number": 1,
                                "theme": "Updated Day",
                                "stops": [
                                    {
                                        "name": "Khan El Khalili",
                                        "category": "attractions",
                                        "sub_category": "market",
                                        "lat": 30.0478,
                                        "lon": 31.2625,
                                        "rating": 4.5,
                                        "estimated_duration_minutes": 120,
                                        "suggested_time_of_day": "afternoon",
                                        "why_recommended": "Updated stop",
                                    },
                                ],
                            },
                        ],
                        "accommodation_suggestions": [],
                    },
                    "phase": "itinerary_review",
                },
            }
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_modify_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_lifecycle_mod"
            mock_mod_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_mod_ws)

            try:
                sid_mod = await process_message_stream(
                    user_text="Update my plan",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id=user_id,
                    token="mock_token",
                )
                assert sid_mod == "sess_mod_001"
            finally:
                manager.disconnect(ws_key)

        await asyncio.sleep(0.01)

        # Verify state after modify
        itin_after_mod = (
            await db_session.execute(
                select(Itinerary).where(
                    Itinerary.itinerary_id == itinerary.itinerary_id
                )
            )
        ).scalar_one()
        assert itin_after_mod.version_number == 2
        assert itin_after_mod.status == ItineraryStatus.draft  # unchanged

        # ── Step 2: Approve itinerary ──────────────────────────────────

        async def mock_approve_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_app_001"}}
            yield {"type": "phase", "data": {"phase": "completed"}}
            yield {"type": "text", "content": "Approved! 🎉 "}
            yield {
                "type": "result",
                "data": {
                    "action": "approve_itinerary",
                    "message": "Your trip is approved! 🎉",
                    "itinerary": {"destination": "Cairo", "days": []},
                    "phase": "completed",
                },
            }
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_approve_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_lifecycle_app"
            mock_app_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_app_ws)

            try:
                # Pass the session_id from the modify step for state continuity
                sid_app = await process_message_stream(
                    user_text="I approve",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id=user_id,
                    token="mock_token",
                    session_id="sess_mod_001",
                )
                assert sid_app == "sess_app_001"

                # Verify trip_approved notification
                sent_calls = mock_app_ws.send_json.call_args_list
                sent_types = [call[0][0].get("type") for call in sent_calls]
                assert "trip_approved" in sent_types, (
                    f"Expected trip_approved, got {sent_types}"
                )
            finally:
                manager.disconnect(ws_key)

        # ── Verify final state in DB ────────────────────────────────────
        result = await db_session.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries),
                selectinload(Trip.trip_profiles),
            )
            .where(Trip.trip_id == trip.trip_id)
        )
        trip_final = result.scalar_one()
        itin_final = trip_final.itineraries[0]
        prof_final = trip_final.trip_profiles[0] if trip_final.trip_profiles else None

        # Trip
        assert trip_final.status == TripStatus.active
        assert trip_final.approved_at is not None
        # (SQLite func.now() has second-level precision — timestamps may match)
        assert _utc_ts(trip_final.updated_at) >= created_ts_trip

        # Itinerary
        assert itin_final.status == ItineraryStatus.active
        assert itin_final.version_number == 2  # unchanged by approval
        assert _utc_ts(itin_final.updated_at) >= created_ts_itin

        # TripProfile
        if prof_final:
            assert _utc_ts(prof_final.updated_at) > _utc_ts(prof_final.generated_at)

        print("  ✅ Phase 3: Full lifecycle — create → modify → approve → all DB state verified")

    # ── Phase 4: session_id Propagation ──────────────────────────────────

    @pytest.mark.asyncio
    async def test_phase4_session_id_propagation(self, db_session):
        """session_id is returned and passed between successive process_message_stream calls."""
        data = await _create_trip_in_db(db_session, "session_id_user")
        trip = data["trip"]

        session_ids_seen = []
        call_count = 0

        async def mock_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            passed_session_id = kwargs.get("session_id")
            session_ids_seen.append(passed_session_id)
            # Return a different session_id on each call so we can verify propagation
            sid = f"sess_prop_00{call_count}"
            yield {"type": "session", "data": {"session_id": sid}}
            yield {"type": "phase", "data": {"phase": "itinerary_review"}}
            yield {"type": "text", "content": "Hello! "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_session_prop"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                # First call: no session_id passed (initial state)
                sid1 = await process_message_stream(
                    user_text="Hello",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="session_id_user",
                    token="mock_token",
                )
                assert sid1 == "sess_prop_001"

                # Second call: pass the session_id from the first call
                sid2 = await process_message_stream(
                    user_text="Show me the plan",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="session_id_user",
                    token="mock_token",
                    session_id=sid1,
                )
                assert sid2 == "sess_prop_002"

                # Third call: pass session_id from second call
                sid3 = await process_message_stream(
                    user_text="Looks good!",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="session_id_user",
                    token="mock_token",
                    session_id=sid2,
                )
                assert sid3 == "sess_prop_003"

                # Verify session_ids were passed to handle_chat_stream
                assert session_ids_seen[0] is None, "First call gets None session_id"
                assert session_ids_seen[1] == "sess_prop_001", (
                    f"Second call gets first session_id, got {session_ids_seen[1]}"
                )
                assert session_ids_seen[2] == "sess_prop_002", (
                    f"Third call gets second session_id, got {session_ids_seen[2]}"
                )

            finally:
                manager.disconnect(ws_key)

        print("  ✅ Phase 4: session_id propagation — chained across 3 calls verified")


# ═════════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═════════════════════════════════════════════════════════════════════════════


class TestFullUserFlowEdgeCases:
    """Edge cases around the full user flow."""

    @pytest.mark.asyncio
    async def test_approval_without_prior_modify(self, db_session):
        """Approval works directly on a freshly created trip (no prior modify)."""
        data = await _create_trip_in_db(db_session, "edge_user")
        trip = data["trip"]

        assert trip.status == TripStatus.planning
        assert trip.approved_at is None

        async def mock_approve_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_edge"}}
            yield {"type": "phase", "data": {"phase": "completed"}}
            yield {"type": "text", "content": "Approved! "}
            yield {
                "type": "result",
                "data": {
                    "action": "approve_itinerary",
                    "message": "Approved!",
                    "itinerary": {"destination": "Cairo", "days": []},
                    "phase": "completed",
                },
            }
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_approve_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "test_edge_approve"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                await process_message_stream(
                    user_text="I approve",
                    trip=trip,
                    conversation=data["conversation"],
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="edge_user",
                    token="mock_token",
                )
            finally:
                manager.disconnect(ws_key)

        # Verify approval happened
        trip_r = (
            await db_session.execute(
                select(Trip).where(Trip.trip_id == trip.trip_id)
            )
        ).scalar_one()
        assert trip_r.status == TripStatus.active
        assert trip_r.approved_at is not None

        # Verify version NOT incremented
        itin_r = (
            await db_session.execute(
                select(Itinerary).where(Itinerary.trip_id == trip.trip_id)
            )
        ).scalar_one()
        assert itin_r.version_number == 1, "Approval must not increment version"

        print("  ✅ Edge case: Direct approval (no modify) — version unchanged, status active")
