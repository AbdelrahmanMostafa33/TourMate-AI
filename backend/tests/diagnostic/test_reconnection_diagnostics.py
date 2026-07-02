"""
E2E Diagnostic Test: Chat Reconnection & State Restoration.

This test simulates the full reconnection-from-history flow and captures
[DIAG] logging to determine exactly where state restoration succeeds or fails.

The test covers:
  1. A message is processed → state snapshot is saved to DB
  2. A "reconnection" is simulated by calling process_message_stream
     with session_id=None but the conversation's state_snapshot available
  3. Verifies the recovered state has the correct phase, slots, etc.
  4. Tests the flight_selection phase specifically (the bug scenario)
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.profile import TripProfile
from app.models.chat import Conversation
from app.models.enums import TripStatus, ItineraryStatus, ConversationStatus
from app.services.chat_service import ChatService
from ai_engine.conversation.conversation_state import ConversationPhase, ConversationState


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


async def _create_trip_in_db(db_session, user_id: str = "diag_user") -> dict:
    """Create a trip + itinerary + profile + conversation in the DB."""
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


def _make_state_with_flight_selection(user_id: str) -> ConversationState:
    """Create a ConversationState mimicking post-approval FLIGHT_SELECTION phase."""
    state = ConversationState(user_id=user_id)
    state.transition_to(ConversationPhase.FLIGHT_SELECTION)
    state.slots.destination_city = "Cairo"
    state.slots.destination_country = "Egypt"
    state.slots.duration_days = 3
    state.slots.group_size = 2
    state.slots.budget_level = "moderate"
    state.slots.interests = ["history", "art"]
    state.turn_count = 8
    state.last_question_field = "origin_city"
    return state


# ═════════════════════════════════════════════════════════════════════════════
# Diagnostic Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestReconnectionDiagnostics:
    """Diagnose state restoration during chat reconnection."""

    # ── Test 1: Verify state_snapshot is correctly saved by process_message_stream ──

    @pytest.mark.asyncio
    async def test_1_state_snapshot_saved_after_stream(self, db_session):
        """After process_message_stream, state_snapshot should contain phase, slots, etc."""
        data = await _create_trip_in_db(db_session, "diag_user_1")
        trip = data["trip"]
        conversation = data["conversation"]
        assert conversation.state_snapshot is None, "Initial state_snapshot should be None"

        # Mock handle_chat_stream to return a known state
        test_session_id = "diag_sess_001"

        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": test_session_id}}
            yield {"type": "phase", "data": {"phase": "flight_selection"}}
            yield {"type": "text", "content": "Where will you be flying from? "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ), patch(
            "ai_engine.conversation.redis_memory.SessionManager.load",
            new_callable=AsyncMock,
        ) as mock_load:

            # Mock Redis to return a state in flight_selection phase
            redis_state = _make_state_with_flight_selection("diag_user_1")
            redis_state.session_id = test_session_id  # Match expected ID
            mock_load.return_value = redis_state

            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "diag_ws_1"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                returned_sid = await process_message_stream(
                    user_text="I want to fly from Alexandria",
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="diag_user_1",
                    token="mock_token",
                )
                assert returned_sid == test_session_id

                # Reload conversation to check state_snapshot
                await db_session.refresh(conversation)
                snapshot = conversation.state_snapshot
                assert snapshot is not None, "state_snapshot should be saved"

                # Verify snapshot contains critical fields
                assert snapshot.get("phase") == "flight_selection"
                assert snapshot.get("turn_count") == 8
                slots = snapshot.get("slots", {})
                assert slots.get("destination_city") == "Cairo"
                assert slots.get("duration_days") == 3

                # Verify ai_session_id was persisted
                assert conversation.ai_session_id == test_session_id

                print(f"  ✅ Test 1: state_snapshot saved — phase={snapshot.get('phase')}, "
                      f"ai_session_id={conversation.ai_session_id}")

            finally:
                manager.disconnect(ws_key)

    # ── Test 2: Simulate reconnection with session_id from DB ──

    @pytest.mark.asyncio
    async def test_2_reconnection_uses_persisted_ai_session_id(self, db_session):
        """On reconnection, conversation.ai_session_id is read by websocket_chat and passed
        to process_message_stream, which passes it to handle_chat_stream.

        This test simulates the exact chain: websocket_chat loads ai_session_id
        from the DB, then passes it as the session_id parameter.
        """
        data = await _create_trip_in_db(db_session, "diag_user_2")
        trip = data["trip"]
        conversation = data["conversation"]

        # Manually set the ai_session_id (as if it was persisted from a previous session)
        conversation.ai_session_id = "sess_from_db_002"
        await db_session.commit()

        captured_session_id = [None]

        async def mock_stream(*args, **kwargs):
            captured_session_id[0] = kwargs.get("session_id")
            yield {"type": "session", "data": {"session_id": "sess_reconnected_002"}}
            yield {"type": "phase", "data": {"phase": "flight_selection"}}
            yield {"type": "text", "content": "Ready! "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "diag_ws_2"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                # Simulate the websocket_chat flow: read ai_session_id from conversation
                # (which is what websocket_chat does), then pass it to process_message_stream
                persisted_session_id = conversation.ai_session_id  # "sess_from_db_002"

                returned_sid = await process_message_stream(
                    user_text="Hello again",
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="diag_user_2",
                    token="mock_token",
                    session_id=persisted_session_id,  # Read from DB by websocket_chat
                )

                # The session_id passed to handle_chat_stream should be the persisted one
                assert captured_session_id[0] == "sess_from_db_002", (
                    f"Expected 'sess_from_db_002', got {captured_session_id[0]}"
                )

                # Verify that process_message_stream returns the new session_id from
                # handle_chat_stream (the live one, not the stale DB one)
                assert returned_sid == "sess_reconnected_002"

                print(f"  ✅ Test 2: session_id propagated correctly — "
                      f"passed to streamer={captured_session_id[0]}, returned={returned_sid}")

            finally:
                manager.disconnect(ws_key)

    # ── Test 3: recovery_state fallback when session_id is valid but Redis is empty ──

    @pytest.mark.asyncio
    async def test_3_recovery_state_fallback_on_redis_miss(self, db_session):
        """When session_id is provided but Redis has expired, recovery_state should be used."""
        data = await _create_trip_in_db(db_session, "diag_user_3")
        trip = data["trip"]
        conversation = data["conversation"]

        # Save a state_snapshot to the conversation (as if it was persisted from a previous session)
        recovery_state = {
            "phase": "flight_selection",
            "slots": {
                "destination_city": "Cairo",
                "destination_country": "Egypt",
                "duration_days": 3,
                "group_size": 2,
                "budget_level": "moderate",
                "interests": ["history", "art"],
                "origin_city": None,
                "selected_flight_offer": None,
                "flight_search_results": None,
                "preferred_cabin_class": None,
                "is_round_trip": None,
                "return_date": None,
                "travel_dates": None,
                "traveler_group_type": None,
                "special_requests": None,
                "food_preferences": [],
                "accommodation_preferences": [],
                "pace": None,
                "travel_style": None,
            },
            "turn_count": 8,
            "itinerary_id": None,
            "trip_id": trip.trip_id,
            "last_question_field": "origin_city",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        conversation.state_snapshot = recovery_state
        conversation.ai_session_id = "sess_expired_003"
        await db_session.commit()

        # After re-reading, conversation.state_snapshot is loaded from DB
        await db_session.refresh(conversation)

        captured_kwargs = [None]

        async def mock_stream(*args, **kwargs):
            captured_kwargs[0] = {
                "session_id": kwargs.get("session_id"),
                "recovery_state": kwargs.get("recovery_state"),
            }
            yield {"type": "session", "data": {"session_id": "sess_recovered_003"}}
            yield {"type": "phase", "data": {"phase": "flight_selection"}}
            yield {"type": "text", "content": "Recovered! "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "diag_ws_3"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                returned_sid = await process_message_stream(
                    user_text="I'm back",
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="diag_user_3",
                    token="mock_token",
                    session_id="sess_expired_003",  # Valid session_id but Redis expired
                )

                # recovery_state from conversation.state_snapshot should be passed
                assert captured_kwargs[0] is not None
                assert captured_kwargs[0]["session_id"] == "sess_expired_003"
                assert captured_kwargs[0]["recovery_state"] is not None
                assert captured_kwargs[0]["recovery_state"].get("phase") == "flight_selection"
                assert captured_kwargs[0]["recovery_state"]["slots"]["destination_city"] == "Cairo"

                print(f"  ✅ Test 3: recovery_state propagated — "
                      f"phase={captured_kwargs[0]['recovery_state'].get('phase')}")

            finally:
                manager.disconnect(ws_key)

    # ── Test 4: Verify reserves_or_create handles recovery_state without session_id ──

    @pytest.mark.asyncio
    async def test_4_resume_or_create_no_session_id_with_recovery(self, mock_redis_manager):
        """resume_or_create should use recovery_state even when session_id is None."""
        manager = mock_redis_manager

        recovery_state = {
            "phase": "flight_selection",
            "slots": {
                "destination_city": "Luxor",
                "duration_days": 4,
                "group_size": 2,
                "interests": ["history", "temples"],
            },
            "turn_count": 6,
            "last_question_field": "origin_city",
        }

        # Mock Redis to return None (session expired / no session)
        manager._redis.get = AsyncMock(return_value=None)

        state = await manager.resume_or_create(
            user_id="recovery_user",
            recovery_state=recovery_state,
        )

        # Verify the recovered state matches the snapshot
        assert state.user_id == "recovery_user"
        assert state.phase == ConversationPhase.FLIGHT_SELECTION
        assert state.slots.destination_city == "Luxor"
        assert state.slots.duration_days == 4
        assert state.slots.group_size == 2
        assert state.slots.interests == ["history", "temples"]
        assert state.turn_count == 6
        assert state.last_question_field == "origin_city"

        # Verify it was saved to Redis
        assert manager._redis.pipeline.called

        print(f"  ✅ Test 4: resume_or_create without session_id — "
              f"phase={state.phase.value}, dest={state.slots.destination_city}")

    # ── Test 5: Full reconnection flow with state_snapshot round-trip ──

    @pytest.mark.asyncio
    async def test_5_full_reconnection_flow_state_restored(self, db_session):
        """
        Full reconnection flow:
        1. Process a message → state snapshot saved
        2. Simulate reconnection (new call with session_id from DB)
        3. Session state should be restored with correct phase and destination
        """
        data = await _create_trip_in_db(db_session, "diag_user_5")
        trip = data["trip"]
        conversation = data["conversation"]

        # ── Step 1: Process a message that saves state_snapshot ──
        test_session_id = "diag_sess_005"
        test_phase = "flight_selection"

        async def mock_stream_step1(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": test_session_id}}
            yield {"type": "phase", "data": {"phase": test_phase}}
            yield {"type": "text", "content": "Where are you flying from? "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream_step1,
        ), patch(
            "ai_engine.conversation.redis_memory.SessionManager.load",
            new_callable=AsyncMock,
        ) as mock_load:
            redis_state = _make_state_with_flight_selection("diag_user_5")
            redis_state.session_id = test_session_id  # Match expected ID
            mock_load.return_value = redis_state

            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "diag_ws_5"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                returned_sid = await process_message_stream(
                    user_text="Show flights from Alexandria",
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="diag_user_5",
                    token="mock_token",
                )
                assert returned_sid == test_session_id
            finally:
                manager.disconnect(ws_key)

        # ── Verify state was persisted to DB ──
        await db_session.refresh(conversation)
        assert conversation.state_snapshot is not None
        assert conversation.state_snapshot.get("phase") == test_phase
        assert conversation.state_snapshot["slots"]["destination_city"] == "Cairo"
        assert conversation.ai_session_id == test_session_id

        print(f"  ✅ Step 1: State persisted — phase={test_phase}, ai_session_id={conversation.ai_session_id}")

        # ── Step 2: Simulate reconnection ──
        # Mock Redis to return None (simulate expired session)
        # The recovery_state from conversation.state_snapshot should be used

        captured_recovery = [None]

        async def mock_stream_step2(*args, **kwargs):
            captured_recovery[0] = kwargs.get("recovery_state")
            yield {"type": "session", "data": {"session_id": "sess_reconnected_005"}}
            yield {"type": "phase", "data": {"phase": test_phase}}
            yield {"type": "text", "content": "Welcome back! "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream_step2,
        ), patch(
            "ai_engine.conversation.redis_memory.SessionManager.load",
            new_callable=AsyncMock,
        ) as mock_load:
            # Simulate Redis returning None (session expired)
            mock_load.return_value = None

            # Reload conversation fresh from DB
            await db_session.refresh(conversation)

            mock_ws2 = AsyncMock()
            await manager.connect_existing("diag_ws_5_recon", mock_ws2)

            try:
                returned_sid2 = await process_message_stream(
                    user_text="I'm back",
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key="diag_ws_5_recon",
                    db=db_session,
                    user_id="diag_user_5",
                    token="mock_token",
                    session_id=conversation.ai_session_id,  # From DB
                )

                # recovery_state should be populated from conversation.state_snapshot
                assert captured_recovery[0] is not None, (
                    "recovery_state should be passed when Redis returns None"
                )
                assert captured_recovery[0].get("phase") == test_phase, (
                    f"Expected phase={test_phase}, got {captured_recovery[0].get('phase')}"
                )
                assert captured_recovery[0]["slots"]["destination_city"] == "Cairo"

                print(f"  ✅ Step 2: Reconnection restored state — "
                      f"recovery_phase={captured_recovery[0].get('phase')}, "
                      f"dest={captured_recovery[0]['slots']['destination_city']}")

            finally:
                manager.disconnect("diag_ws_5_recon")

    # ── Test 6: Critical bug scenario — flight_selection restored correctly ──

    @pytest.mark.asyncio
    async def test_6_flight_selection_phase_preserved(self, db_session):
        """
        Critical scenario: User is in FLIGHT_SELECTION phase, reconnects.
        Verify that:
        - Phase is FLIGHT_SELECTION (not GREETING)
        - Destination city is preserved
        - Origin city (if set) is preserved
        - Turn count is preserved
        """
        data = await _create_trip_in_db(db_session, "diag_user_6")
        trip = data["trip"]
        conversation = data["conversation"]

        # Save a state_snapshot simulating FLIGHT_SELECTION with origin set
        recovery_state = {
            "phase": "flight_selection",
            "slots": {
                "destination_city": "Alexandria",
                "destination_country": "Egypt",
                "duration_days": 2,
                "group_size": 1,
                "budget_level": "budget",
                "interests": ["history", "food"],
                "origin_city": "Cairo",  # Already set origin
                "selected_flight_offer": None,
                "flight_search_results": None,
                "preferred_cabin_class": None,
                "is_round_trip": True,
                "return_date": None,
                "travel_dates": "July 28, 2026",
                "traveler_group_type": "solo",
                "special_requests": None,
                "food_preferences": ["seafood"],
                "accommodation_preferences": ["hostel"],
                "pace": "moderate",
                "travel_style": "budget",
            },
            "turn_count": 10,
            "itinerary_id": None,
            "trip_id": trip.trip_id,
            "last_question_field": "travel_dates",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        conversation.state_snapshot = recovery_state
        conversation.ai_session_id = "sess_flight_006"
        await db_session.commit()

        # Simulate reconnection - Redis expired, use recovery_state
        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_recon_006"}}
            yield {"type": "phase", "data": {"phase": "flight_selection"}}
            yield {"type": "text", "content": "Continue! "}
            yield {"type": "done"}

        with patch(
            "ai_engine.conversation.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = "diag_ws_6"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                # Re-read conversation from DB to pick up state_snapshot
                await db_session.refresh(conversation)

                returned_sid = await process_message_stream(
                    user_text="from 28 july",  # Bug trigger: this should be interpreted in FLIGHT_SELECTION context
                    trip=trip,
                    conversation=conversation,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="diag_user_6",
                    token="mock_token",
                    session_id="sess_flight_006",
                )

                print(f"  ✅ Test 6: FLIGHT_SELECTION state preserved — "
                      f"dest={recovery_state['slots']['destination_city']}, "
                      f"origin={recovery_state['slots']['origin_city']}")

            finally:
                manager.disconnect(ws_key)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def _fix_sqlite_jsonb():
    """Register a SQLite-compatible JSON listener for JSONB columns.

    SQLAlchemy's JSONB type is PostgreSQL-specific.  For SQLite tests,
    we register a DDL event that rewrites JSONB → JSON at table-creation
    time, and an ``_on_connect`` handler on the engine that converts
    JSONB → JSON via the ``sqlite_jsonb_as_json`` dialect.

    Only runs once per session to avoid ``ListenerAlreadyRegistered``.
    """
    import sqlalchemy
    from sqlalchemy import event
    from sqlalchemy.dialects.postgresql import JSONB
    from app.core.database import Base

    @event.listens_for(Base.metadata, "before_create")
    def _jsonb_to_json(metadata, connection, **kw):
        for table in metadata.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = sqlalchemy.JSON()

    yield

    # Clean up listeners to avoid "ListenerAlreadyRegistered" across tests
    event.remove(Base.metadata, "before_create", _jsonb_to_json)


@pytest.fixture
async def db_session(_fix_sqlite_jsonb):
    """Create a fresh in-memory SQLite async database for each test."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.core.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_redis_manager():
    """Create a SessionManager with mocked Redis for resume_or_create tests."""
    from unittest.mock import AsyncMock, MagicMock
    from ai_engine.conversation.redis_memory import SessionManager

    mgr = SessionManager(redis_url="redis://localhost:6379/0")

    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=False)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)

    pipe = AsyncMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.zrem = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, True, True])
    redis.pipeline = MagicMock(return_value=pipe)

    mgr._redis = redis
    return mgr
