"""
Unit tests for ChatService.save_state_snapshot() — ai_session_id + state_snapshot persistence.

Uses an in-memory SQLite async database to verify that:
  - ai_session_id is set correctly on the Conversation record.
  - state_snapshot dict is set correctly alongside ai_session_id.
  - The state's session_id is preserved (not modified by the save).
  - Returns False when the conversation doesn't exist.
  - Multiple snapshot calls update both fields correctly.
  - Different phases are preserved across snapshots.
"""

from __future__ import annotations

import uuid
import pytest

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.services.chat_service import ChatService
from app.models.chat import Conversation
from app.models.enums import ConversationStatus
from ai_engine.conversation.conversation_state import ConversationState, ConversationPhase


# ── Test Database Fixture ─────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Module-level listener: replaces PostgreSQL JSONB columns with generic JSON
# when creating tables on SQLite. Registered once at import time and
# idempotent (re-replacing JSON→JSON is a no-op), so accumulation is harmless.
@event.listens_for(Base.metadata, "before_create")
def _jsonb_to_json_for_sqlite(target, connection, **kw):
    if connection.engine.name == "sqlite":
        from sqlalchemy.dialects.postgresql import JSONB
        import sqlalchemy
        for table in target.tables.values():
            for col in table.columns:
                if isinstance(col.type, JSONB):
                    col.type = sqlalchemy.JSON()


@pytest.fixture
async def db_session():
    """Create a fresh in-memory SQLite async database for each test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
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


# ── Helpers ───────────────────────────────────────────────────────────────

@pytest.fixture
async def conv(db_session: AsyncSession) -> str:
    """Create and return a conversation_id for testing."""
    conv_id = str(uuid.uuid4())
    conversation = Conversation(
        conversation_id=conv_id,
        user_id="test_user",
        status=ConversationStatus.active,
    )
    db_session.add(conversation)
    await db_session.commit()
    return conv_id


async def load_conversation(
    db: AsyncSession, conversation_id: str,
) -> Conversation | None:
    """Load a conversation by ID for assertion."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.conversation_id == conversation_id,
        )
    )
    return result.scalar_one_or_none()


# ── Tests ─────────────────────────────────────────────────────────────────


class TestSaveStateSnapshot:

    # ── Happy Path: ai_session_id ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_ai_session_id_is_persisted(
        self, db_session: AsyncSession, conv: str,
    ):
        """save_state_snapshot should persist the state.session_id as conversation.ai_session_id."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        state.transition_to(ConversationPhase.SLOT_FILLING)
        state.slots.destination_city = "Paris"

        result = await svc.save_state_snapshot(conv, state)

        assert result is True, "save_state_snapshot should return True on success"

        # Reload conversation and verify ai_session_id
        conversation = await load_conversation(db_session, conv)
        assert conversation is not None
        assert conversation.ai_session_id == state.session_id, (
            f"Expected ai_session_id={state.session_id}, got {conversation.ai_session_id}"
        )

    @pytest.mark.asyncio
    async def test_ai_session_id_differs_per_state(
        self, db_session: AsyncSession, conv: str,
    ):
        """Different ConversationState objects should result in different ai_session_id values."""
        svc = ChatService(db_session)

        state1 = ConversationState(user_id="user_a")
        state2 = ConversationState(user_id="user_b")

        # First snapshot
        result1 = await svc.save_state_snapshot(conv, state1)
        assert result1 is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None
        assert conversation.ai_session_id == state1.session_id

        # Second snapshot with different state
        result2 = await svc.save_state_snapshot(conv, state2)
        assert result2 is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None
        assert conversation.ai_session_id == state2.session_id
        # Verify it changed
        assert conversation.ai_session_id != state1.session_id

    # ── Happy Path: state_snapshot ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_state_snapshot_contains_expected_fields(
        self, db_session: AsyncSession, conv: str,
    ):
        """The state_snapshot dict should contain the key fields for recovery."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        state.transition_to(ConversationPhase.SLOT_FILLING)
        state.slots.destination_city = "Rome"
        state.slots.duration_days = 5
        state.turn_count = 3
        state.trip_id = "trip_abc"
        state.last_question_field = "interests"

        result = await svc.save_state_snapshot(conv, state)
        assert result is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None

        snapshot = conversation.state_snapshot
        assert snapshot is not None
        assert snapshot["phase"] == "slot_filling"
        assert snapshot["turn_count"] == 3
        assert snapshot["trip_id"] == "trip_abc"
        assert snapshot["last_question_field"] == "interests"
        assert snapshot["slots"]["destination_city"] == "Rome"
        assert snapshot["slots"]["duration_days"] == 5

    @pytest.mark.asyncio
    async def test_snapshot_does_not_include_history(
        self, db_session: AsyncSession, conv: str,
    ):
        """The state_snapshot should be lightweight — no history, no pool data."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        state.add_user_message("Hello")
        state.add_assistant_message("Hi there!")
        state.add_user_message("Plan a trip")

        result = await svc.save_state_snapshot(conv, state)
        assert result is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None

        snapshot = conversation.state_snapshot
        assert snapshot is not None
        # The snapshot should NOT include history
        assert "history" not in snapshot, "Snapshot should not include message history"
        # It SHOULD include turn_count
        # Note: add_assistant_message does NOT increment turn_count
        # (only add_user_message does — turn_count counts user initiations)
        assert snapshot["turn_count"] == 2

    # ── State session_id is not modified by save ─────────────────────────

    @pytest.mark.asyncio
    async def test_state_session_id_is_preserved(
        self, db_session: AsyncSession, conv: str,
    ):
        """Calling save_state_snapshot should NOT modify the original state object's session_id."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        original_session_id = state.session_id

        result = await svc.save_state_snapshot(conv, state)
        assert result is True

        # Original state should be unchanged
        assert state.session_id == original_session_id, (
            "save_state_snapshot mutated the state's session_id"
        )

    # ── Conversation not found ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_returns_false_when_conversation_not_found(
        self, db_session: AsyncSession,
    ):
        """Non-existent conversation_id should return False."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        nonexistent_id = str(uuid.uuid4())

        result = await svc.save_state_snapshot(nonexistent_id, state)
        assert result is False, (
            "Should return False when conversation doesn't exist"
        )

    # ── Multiple snapshot updates ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_multiple_snapshots_update_fields(
        self, db_session: AsyncSession, conv: str,
    ):
        """Calling snapshot twice should update both ai_session_id and state_snapshot."""
        svc = ChatService(db_session)

        # First snapshot: FLIGHT_SELECTION phase
        state1 = ConversationState(user_id="test_user")
        state1.transition_to(ConversationPhase.FLIGHT_SELECTION)
        state1.slots.destination_city = "London"
        state1.slots.origin_city = "Dubai"

        result1 = await svc.save_state_snapshot(conv, state1)
        assert result1 is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None
        assert conversation.ai_session_id == state1.session_id
        assert conversation.state_snapshot["phase"] == "flight_selection"
        assert conversation.state_snapshot["slots"]["destination_city"] == "London"

        # Second snapshot: COMPLETED phase (simulate progress)
        state2 = ConversationState(user_id="test_user")
        state2.transition_to(ConversationPhase.COMPLETED)
        state2.slots.destination_city = "London"
        state2.slots.origin_city = "Dubai"

        result2 = await svc.save_state_snapshot(conv, state2)
        assert result2 is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None
        assert conversation.ai_session_id == state2.session_id
        assert conversation.state_snapshot["phase"] == "completed"
        # Non-phase fields should still be preserved
        assert conversation.state_snapshot["slots"]["destination_city"] == "London"

    # ── All phases are preserved ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_all_phases_are_preserved(
        self, db_session: AsyncSession, conv: str,
    ):
        """Each ConversationPhase value should survive a round-trip through save_state_snapshot."""
        svc = ChatService(db_session)

        for phase in ConversationPhase:
            state = ConversationState(user_id="test_user")
            state.transition_to(phase)

            result = await svc.save_state_snapshot(conv, state)
            assert result is True

            conversation = await load_conversation(db_session, conv)
            assert conversation is not None
            assert conversation.state_snapshot["phase"] == phase.value, (
                f"Phase {phase.value} was not preserved in snapshot"
            )

    # ── Complex slot data is preserved ───────────────────────────────────

    @pytest.mark.asyncio
    async def test_complex_slot_data_preserved(
        self, db_session: AsyncSession, conv: str,
    ):
        """Settings like lists, booleans, and nested data should survive in both fields."""
        svc = ChatService(db_session)

        state = ConversationState(user_id="test_user")
        state.transition_to(ConversationPhase.ITINERARY_REVIEW)
        state.slots.destination_city = "Tokyo"
        state.slots.duration_days = 7
        state.slots.interests = ["temples", "food", "anime"]
        state.slots.food_preferences = ["ramen", "sushi"]
        state.slots.accommodation_preferences = ["hotel", "ryokan"]
        state.slots.is_round_trip = True
        state.slots.group_size = 2
        state.turn_count = 10
        state.trip_id = "trip_xyz"
        state.last_question_field = None

        result = await svc.save_state_snapshot(conv, state)
        assert result is True

        conversation = await load_conversation(db_session, conv)
        assert conversation is not None

        # Verify ai_session_id
        assert conversation.ai_session_id == state.session_id

        # Verify snapshot
        snapshot = conversation.state_snapshot
        assert snapshot is not None
        assert snapshot["phase"] == "itinerary_review"
        assert snapshot["turn_count"] == 10
        assert snapshot["trip_id"] == "trip_xyz"
        assert snapshot["last_question_field"] is None

        slots = snapshot["slots"]
        assert slots["destination_city"] == "Tokyo"
        assert slots["duration_days"] == 7
        assert slots["interests"] == ["temples", "food", "anime"]
        assert slots["food_preferences"] == ["ramen", "sushi"]
        assert slots["accommodation_preferences"] == ["hotel", "ryokan"]
        assert slots["is_round_trip"] is True
        assert slots["group_size"] == 2
