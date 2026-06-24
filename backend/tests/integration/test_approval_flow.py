"""
Integration tests: Full approval flow — trip/itin status, approved_at,
version_number, and updated_at timestamps.

Tests simulate exactly what ``process_message_stream()`` does when it
receives approval or itinerary-modification events from the AI stream.

Uses a fresh in-memory SQLite async database per test.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.profile import TripProfile
from app.models.enums import TripStatus, ItineraryStatus
from app.services.chat_service import ChatService
from app.services.itinerary_service import ItineraryService


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


async def _create_trip_with_itinerary_and_profile(
    db_session,
    user_id: str = "approval_test_user",
) -> dict:
    """Create a trip + itinerary + trip_profile in the DB for testing.

    Returns a dict with the ORM objects so the test can inspect them.
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
            "pace": "balanced",
            "interests": ["history", "art"],
            "food_preferences": ["local cuisine"],
            "accommodation_preferences": ["boutique hotel"],
        },
    }

    created = await svc.create_trip_from_ai_result(user_id, ai_result)
    await db_session.commit()

    # Reload with all relationships
    result = await db_session.execute(
        select(Trip)
        .options(
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops),
            selectinload(Trip.trip_profiles),
        )
        .where(Trip.trip_id == created["trip"].trip_id)
    )
    trip = result.scalar_one()

    return {
        "trip": trip,
        "itinerary": trip.itineraries[0] if trip.itineraries else None,
        "profile": trip.trip_profiles[0] if trip.trip_profiles else None,
    }


def _utc_ts(dt: datetime) -> float:
    """Return UTC timestamp, handling both naive and aware datetimes.

    SQLite stores naive datetimes, so strip tzinfo before converting.
    """
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None).timestamp()
    return dt.timestamp()


def _simulate_approval(trip: Trip, now: datetime) -> None:
    """Simulate the exact DB updates done by process_message_stream on approval."""
    trip.status = TripStatus.active
    trip.approved_at = now
    trip.updated_at = now
    if trip.itineraries:
        for itin in trip.itineraries:
            itin.status = ItineraryStatus.active
            itin.updated_at = now
    if trip.trip_profiles:
        for prof in trip.trip_profiles:
            prof.updated_at = now


def _simulate_itinerary_update(trip: Trip, itinerary: Itinerary, now: datetime) -> None:
    """Simulate the DB updates done by process_message_stream on itinerary change."""
    itinerary.version_number = (itinerary.version_number or 1) + 1
    itinerary.updated_at = now
    trip.updated_at = now
    if trip.trip_profiles:
        for prof in trip.trip_profiles:
            prof.updated_at = now


# ═════════════════════════════════════════════════════════════════════════════
# 1. Approval Flow: Trip + Itinerary Status
# ═════════════════════════════════════════════════════════════════════════════


class TestApprovalStatusUpdates:
    """Verify that approval correctly sets trip/itin status and approved_at."""

    @pytest.mark.asyncio
    async def test_approve_sets_trip_status_active(self, db_session):
        """Trip.status changes from planning → active on approval."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip = data["trip"]

        assert trip.status == TripStatus.planning

        now = datetime.now(timezone.utc)
        _simulate_approval(trip, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Trip).where(Trip.trip_id == trip.trip_id)
        )).scalar_one()
        assert reloaded.status == TripStatus.active

    @pytest.mark.asyncio
    async def test_approve_sets_itinerary_status_active(self, db_session):
        """Itinerary.status changes from draft → active on approval."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        itinerary = data["itinerary"]

        assert itinerary.status == ItineraryStatus.draft

        now = datetime.now(timezone.utc)
        _simulate_approval(data["trip"], now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
        )).scalar_one()
        assert reloaded.status == ItineraryStatus.active

    @pytest.mark.asyncio
    async def test_approve_sets_approved_at(self, db_session):
        """Trip.approved_at is set to current timestamp on approval."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip = data["trip"]

        assert trip.approved_at is None

        now = datetime.now(timezone.utc)
        _simulate_approval(trip, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Trip).where(Trip.trip_id == trip.trip_id)
        )).scalar_one()
        assert reloaded.approved_at is not None

        # SQLite stores naive datetimes — normalize for comparison
        approved_at_ts = _utc_ts(reloaded.approved_at)
        now_ts = _utc_ts(now)
        assert abs(approved_at_ts - now_ts) < 2.0

    @pytest.mark.asyncio
    async def test_approve_updates_trip_updated_at(self, db_session):
        """Trip.updated_at advances beyond created_at on approval."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip = data["trip"]

        import asyncio
        await asyncio.sleep(0.01)

        now = datetime.now(timezone.utc)
        _simulate_approval(trip, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Trip).where(Trip.trip_id == trip.trip_id)
        )).scalar_one()
        assert _utc_ts(reloaded.updated_at) > _utc_ts(reloaded.created_at)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Version Number Increment
# ═════════════════════════════════════════════════════════════════════════════


class TestVersionNumberIncrement:
    """Verify version_number increments when itinerary is updated."""

    @pytest.mark.asyncio
    async def test_version_starts_at_1(self, db_session):
        """New itinerary starts with version_number=1."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        assert data["itinerary"].version_number == 1

    @pytest.mark.asyncio
    async def test_version_increments_on_update(self, db_session):
        """Version increments from 1 to 2 on first update."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        itinerary, trip = data["itinerary"], data["trip"]

        now = datetime.now(timezone.utc)
        _simulate_itinerary_update(trip, itinerary, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
        )).scalar_one()
        assert reloaded.version_number == 2

    @pytest.mark.asyncio
    async def test_version_increments_multiple_times(self, db_session):
        """Version increments consistently on multiple updates."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        itinerary, trip = data["itinerary"], data["trip"]

        for expected_version in [2, 3, 4]:
            now = datetime.now(timezone.utc)
            _simulate_itinerary_update(trip, itinerary, now)
            await db_session.commit()

            reloaded = (await db_session.execute(
                select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
            )).scalar_one()
            assert reloaded.version_number == expected_version

    @pytest.mark.asyncio
    async def test_version_not_incremented_on_approval(self, db_session):
        """Approval does NOT change version_number."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        itinerary, trip = data["itinerary"], data["trip"]

        assert itinerary.version_number == 1
        now = datetime.now(timezone.utc)
        _simulate_approval(trip, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
        )).scalar_one()
        assert reloaded.version_number == 1


# ═════════════════════════════════════════════════════════════════════════════
# 3. updated_at Timestamps
# ═════════════════════════════════════════════════════════════════════════════


class TestUpdatedAtTimestamps:
    """Verify updated_at > created_at on all relevant tables."""

    @pytest.mark.asyncio
    async def test_trip_updated_at_gt_created_after_update(self, db_session):
        """Trip.updated_at advances beyond created_at when itinerary changes."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip, itinerary = data["trip"], data["itinerary"]

        import asyncio
        await asyncio.sleep(0.01)

        now = datetime.now(timezone.utc)
        _simulate_itinerary_update(trip, itinerary, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Trip).where(Trip.trip_id == trip.trip_id)
        )).scalar_one()
        assert _utc_ts(reloaded.updated_at) > _utc_ts(reloaded.created_at)

    @pytest.mark.asyncio
    async def test_itinerary_updated_at_gt_created_after_update(self, db_session):
        """Itinerary.updated_at advances beyond created_at when stops change."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip, itinerary = data["trip"], data["itinerary"]

        import asyncio
        await asyncio.sleep(0.01)

        now = datetime.now(timezone.utc)
        _simulate_itinerary_update(trip, itinerary, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
        )).scalar_one()
        assert _utc_ts(reloaded.updated_at) > _utc_ts(reloaded.created_at)

    @pytest.mark.asyncio
    async def test_trip_profile_updated_at_gt_generated_on_update(self, db_session):
        """TripProfile.updated_at advances beyond generated_at when itinerary changes."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        profile, trip, itinerary = data["profile"], data["trip"], data["itinerary"]

        # Initially generated_at ≈ updated_at (profile not updated yet)
        assert abs(_utc_ts(profile.updated_at) - _utc_ts(profile.generated_at)) < 0.1

        import asyncio
        await asyncio.sleep(0.01)

        now = datetime.now(timezone.utc)
        _simulate_itinerary_update(trip, itinerary, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(TripProfile).where(TripProfile.profile_id == profile.profile_id)
        )).scalar_one()
        assert _utc_ts(reloaded.updated_at) > _utc_ts(reloaded.generated_at)

    @pytest.mark.asyncio
    async def test_trip_profile_updated_at_on_approval(self, db_session):
        """TripProfile.updated_at advances beyond generated_at on approval."""
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip, profile = data["trip"], data["profile"]

        import asyncio
        await asyncio.sleep(0.01)

        now = datetime.now(timezone.utc)
        _simulate_approval(trip, now)
        await db_session.commit()

        reloaded = (await db_session.execute(
            select(TripProfile).where(TripProfile.profile_id == profile.profile_id)
        )).scalar_one()
        assert _utc_ts(reloaded.updated_at) > _utc_ts(reloaded.generated_at)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Full Lifecycle: Create → Modify → Approve
# ═════════════════════════════════════════════════════════════════════════════


class TestFullApprovalLifecycle:
    """End-to-end lifecycle: trip created → itinerary modified → approved."""

    @pytest.mark.asyncio
    async def test_full_create_modify_approve_cycle(self, db_session):
        """Complete lifecycle with correct state at each step."""
        import asyncio

        # ── Phase 1: Create ─────────────────────────────────────────────
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip, itinerary, profile = data["trip"], data["itinerary"], data["profile"]

        assert trip.status == TripStatus.planning
        assert itinerary.status == ItineraryStatus.draft
        assert itinerary.version_number == 1
        assert trip.approved_at is None

        created_ts_trip = _utc_ts(trip.created_at)
        created_ts_itin = _utc_ts(itinerary.created_at)
        generated_ts_prof = _utc_ts(profile.generated_at)

        await asyncio.sleep(0.01)

        # ── Phase 2: Modify Itinerary ────────────────────────────────────
        now1 = datetime.now(timezone.utc)
        _simulate_itinerary_update(trip, itinerary, now1)
        await db_session.commit()

        reloaded_itin = (await db_session.execute(
            select(Itinerary).where(Itinerary.itinerary_id == itinerary.itinerary_id)
        )).scalar_one()
        assert reloaded_itin.version_number == 2
        assert _utc_ts(reloaded_itin.updated_at) > created_ts_itin

        await asyncio.sleep(0.01)

        # ── Phase 3: Approve ────────────────────────────────────────────
        now2 = datetime.now(timezone.utc)
        _simulate_approval(trip, now2)
        await db_session.commit()

        result = await db_session.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries),
                selectinload(Trip.trip_profiles),
            )
            .where(Trip.trip_id == trip.trip_id)
        )
        trip_r = result.scalar_one()
        itin_r = trip_r.itineraries[0]
        prof_r = trip_r.trip_profiles[0]

        assert trip_r.status == TripStatus.active
        assert trip_r.approved_at is not None
        assert _utc_ts(trip_r.updated_at) > created_ts_trip
        assert abs(_utc_ts(trip_r.approved_at) - _utc_ts(now2)) < 2.0

        assert itin_r.status == ItineraryStatus.active
        assert itin_r.version_number == 2   # unchanged by approval
        assert _utc_ts(itin_r.updated_at) > created_ts_itin

        assert _utc_ts(prof_r.updated_at) > generated_ts_prof


# ═════════════════════════════════════════════════════════════════════════════
# 5. process_message_stream Integration (mocked stream)
# ═════════════════════════════════════════════════════════════════════════════


class TestProcessMessageStreamApproval:
    """Test approval handling inside process_message_stream with mocked stream."""

    @pytest.mark.asyncio
    async def test_stream_approval_updates_db(self, db_session):
        """Approval result event → DB updates via process_message_stream."""
        # ── 1. Create trip in DB ──────────────────────────────────────────
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip = data["trip"]

        from app.models.chat import Conversation
        from app.models.enums import ConversationStatus

        conv = Conversation(
            conversation_id="test_conv_approve_001",
            user_id="approval_test_user",
            status=ConversationStatus.active,
        )
        db_session.add(conv)
        trip.conversation_id = conv.conversation_id
        await db_session.commit()

        # ── 2. Build mock stream that yields approval result event ───────
        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_approve_001"}}
            yield {"type": "phase", "data": {"phase": "completed"}}
            yield {"type": "text", "content": "Your trip is approved! 🎉 "}
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

        # ── 3. Patch handle_chat_stream and call process_message_stream ──
        with patch(
            "ai_engine.chat.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = trip.trip_id
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                await process_message_stream(
                    user_text="I approve this trip",
                    trip=trip,
                    conversation=conv,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="approval_test_user",
                    token="mock_token",
                )

                # ── 4. Verify DB updates ────────────────────────────────────
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
                assert trip_r.approved_at is not None
                assert _utc_ts(trip_r.updated_at) > _utc_ts(trip_r.created_at)

                itin_r = trip_r.itineraries[0]
                assert itin_r.status == ItineraryStatus.active
                assert _utc_ts(itin_r.updated_at) > _utc_ts(itin_r.created_at)

                if trip_r.trip_profiles:
                    prof = trip_r.trip_profiles[0]
                    assert _utc_ts(prof.updated_at) > _utc_ts(prof.generated_at)
            finally:
                manager.disconnect(ws_key)

    @pytest.mark.asyncio
    async def test_stream_itinerary_update_increments_version(self, db_session):
        """CREATE_TRIP result → version_number increments via process_message_stream."""
        # ── 1. Create trip with itinerary ────────────────────────────────
        data = await _create_trip_with_itinerary_and_profile(db_session)
        trip = data["trip"]
        itinerary = data["itinerary"]

        from app.models.chat import Conversation
        from app.models.enums import ConversationStatus

        conv = Conversation(
            conversation_id="test_conv_update_001",
            user_id="approval_test_user",
            status=ConversationStatus.active,
        )
        db_session.add(conv)
        trip.conversation_id = conv.conversation_id
        await db_session.commit()

        original_version = itinerary.version_number

        # ── 2. Build mock stream that yields CREATE_TRIP result ──────────
        async def mock_stream(*args, **kwargs):
            yield {"type": "session", "data": {"session_id": "sess_update_001"}}
            yield {"type": "phase", "data": {"phase": "itinerary_review"}}
            yield {"type": "text", "content": "Updated itinerary! "}
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

        # ── 3. Patch handle_chat_stream and call process_message_stream ──
        with patch(
            "ai_engine.chat.orchestrator.handle_chat_stream",
            side_effect=mock_stream,
        ):
            from app.api.v1.routes.chat import process_message_stream
            from app.ws.manager import manager

            ws_key = trip.trip_id + "_update"
            mock_ws = AsyncMock()
            await manager.connect_existing(ws_key, mock_ws)

            try:
                await process_message_stream(
                    user_text="Update my itinerary",
                    trip=trip,
                    conversation=conv,
                    profile_data={},
                    ws_key=ws_key,
                    db=db_session,
                    user_id="approval_test_user",
                    token="mock_token",
                )

                # ── 4. Verify version incremented ─────────────────────────────
                result = await db_session.execute(
                    select(Trip)
                    .options(
                        selectinload(Trip.itineraries)
                        .selectinload(Itinerary.days)
                        .selectinload(Day.stops),
                        selectinload(Trip.trip_profiles),
                    )
                    .where(Trip.trip_id == trip.trip_id)
                )
                trip_r = result.scalar_one()
                itin_r = trip_r.itineraries[0]

                assert itin_r.version_number == original_version + 1, (
                    f"Expected version={original_version + 1}, got {itin_r.version_number}"
                )

                # Verify TripProfile updated_at moved forward
                if trip_r.trip_profiles:
                    prof = trip_r.trip_profiles[0]
                    assert _utc_ts(prof.updated_at) > _utc_ts(prof.generated_at), (
                        "TripProfile.updated_at should advance after itinerary update"
                    )
            finally:
                manager.disconnect(ws_key)
