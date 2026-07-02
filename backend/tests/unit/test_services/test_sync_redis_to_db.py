"""
Unit tests for ChatService.sync_redis_to_db() — offset-based deduplication.

Uses an in-memory SQLite async database to verify that:
  - New Redis messages beyond the DB count are correctly inserted.
  - Messages already in the DB are not duplicated.
  - Edge cases (empty history, DB ahead of Redis, gap recovery) work.
  - Role mapping and content filtering behave correctly.
"""

from __future__ import annotations

import uuid
import pytest

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.database import Base
from app.services.chat_service import ChatService
from app.models.chat import Conversation, Message
from app.models.enums import ConversationStatus

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


# ── Helper ────────────────────────────────────────────────────────────────

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


async def insert_message(db: AsyncSession, conv_id: str, sender: str, content: str) -> None:
    """Insert a single message into the test DB."""
    msg = Message(
        message_id=str(uuid.uuid4()),
        conversation_id=conv_id,
        sender=sender,
        content=content,
    )
    db.add(msg)
    await db.commit()


# ── Tests ─────────────────────────────────────────────────────────────────


class TestSyncRedisToDb:

    # ── Happy Path ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_sync_all_new_messages(self, db_session: AsyncSession, conv: str):
        """No messages in DB, 3 in Redis → should insert all 3."""
        svc = ChatService(db_session)

        redis_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Plan a trip to Paris"},
        ]

        inserted = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted == 3

        # Verify messages were persisted
        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv
            ).order_by(Message.timestamp)
        )
        msgs = result.scalars().all()
        assert len(msgs) == 3
        assert msgs[0].content == "Hello"
        assert msgs[1].content == "Hi there!"
        assert msgs[2].content == "Plan a trip to Paris"

    @pytest.mark.asyncio
    async def test_sync_partial_new_messages(self, db_session: AsyncSession, conv: str):
        """2 messages in DB, 5 in Redis → only insert the 3 new ones (offset=2)."""
        # Pre-populate DB with first 2 messages
        await insert_message(db_session, conv, "user", "Hello")
        await insert_message(db_session, conv, "agent", "Hi!")

        svc = ChatService(db_session)

        redis_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "user", "content": "Plan Paris trip"},
            {"role": "assistant", "content": "Sure, here's a plan"},
            {"role": "user", "content": "Looks good"},
        ]

        inserted = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted == 3  # Only the 3 beyond offset=2

        # Verify total DB messages = 5 (2 original + 3 new)
        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv)
        )
        assert len(result.scalars().all()) == 5

    @pytest.mark.asyncio
    async def test_sync_all_already_synced(self, db_session: AsyncSession, conv: str):
        """3 messages in DB, 3 in Redis → return 0 (nothing to sync)."""
        await insert_message(db_session, conv, "user", "A")
        await insert_message(db_session, conv, "agent", "B")
        await insert_message(db_session, conv, "user", "C")

        svc = ChatService(db_session)

        redis_history = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ]

        inserted = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted == 0

    # ── Edge Cases ────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_redis_history(self, db_session: AsyncSession, conv: str):
        """Empty Redis history → return 0 immediately."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [])
        assert inserted == 0

    @pytest.mark.asyncio
    async def test_db_ahead_of_redis(self, db_session: AsyncSession, conv: str):
        """DB has 3 messages, Redis has only 2 → return 0 (nothing new in Redis)."""
        await insert_message(db_session, conv, "user", "A")
        await insert_message(db_session, conv, "agent", "B")
        await insert_message(db_session, conv, "user", "C")

        svc = ChatService(db_session)

        redis_history = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
        ]

        inserted = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted == 0  # db_count=3 > len(redis)=2

    @pytest.mark.asyncio
    async def test_gap_recovery(self, db_session: AsyncSession, conv: str):
        """Simulate a previous partial failure:
        DB has 2 messages, Redis has 5 — only 2 had been committed.
        Should sync the 3 gap messages (indices 2, 3, 4).
        """
        # Only 2 messages were committed before a crash
        await insert_message(db_session, conv, "user", "Hello")
        await insert_message(db_session, conv, "agent", "Hi")

        svc = ChatService(db_session)

        # Redis has all 5 messages
        redis_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
            {"role": "user", "content": "Plan Paris"},
            {"role": "assistant", "content": "Here's the plan"},
            {"role": "user", "content": "Looks good"},
        ]

        inserted = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted == 3  # Gaps filled

        result = await db_session.execute(
            select(Message).where(
                Message.conversation_id == conv
            ).order_by(Message.timestamp)
        )
        msgs = result.scalars().all()
        assert len(msgs) == 5
        assert msgs[2].content == "Plan Paris"
        assert msgs[3].content == "Here's the plan"
        assert msgs[4].content == "Looks good"

    @pytest.mark.asyncio
    async def test_multiple_sync_calls_no_duplicates(self, db_session: AsyncSession, conv: str):
        """Calling sync twice with the same Redis history should not duplicate."""
        svc = ChatService(db_session)

        redis_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]

        # First sync — 2 messages
        inserted1 = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted1 == 2

        # Second sync with same history — 0 new
        inserted2 = await svc.sync_redis_to_db(conv, redis_history)
        assert inserted2 == 0

        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv)
        )
        assert len(result.scalars().all()) == 2  # Still only 2

    # ── Role Mapping ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_role_mapping_user_to_user(self, db_session: AsyncSession, conv: str):
        """Redis 'user' role maps to DB sender 'user'."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [
            {"role": "user", "content": "hello"},
        ])
        assert inserted == 1

        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv)
        )
        msg = result.scalars().one()
        assert msg.sender == "user"

    @pytest.mark.asyncio
    async def test_role_mapping_assistant_to_agent(self, db_session: AsyncSession, conv: str):
        """Redis 'assistant' role maps to DB sender 'agent'."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [
            {"role": "assistant", "content": "hello"},
        ])
        assert inserted == 1

        result = await db_session.execute(
            __import__("sqlalchemy").select(Message).where(
                Message.conversation_id == conv
            )
        )
        msg = result.scalars().one()
        assert msg.sender == "agent"

    @pytest.mark.asyncio
    async def test_role_mapping_system_to_agent(self, db_session: AsyncSession, conv: str):
        """Redis 'system' role maps to DB sender 'agent'."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [
            {"role": "system", "content": "system message"},
        ])
        assert inserted == 1

        result = await db_session.execute(
            __import__("sqlalchemy").select(Message).where(
                Message.conversation_id == conv
            )
        )
        msg = result.scalars().one()
        assert msg.sender == "agent"

    @pytest.mark.asyncio
    async def test_unknown_role_skipped(self, db_session: AsyncSession, conv: str):
        """Redis messages with unknown roles should be skipped."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [
            {"role": "user", "content": "valid"},
            {"role": "unknown_role", "content": "should be skipped"},
            {"role": "assistant", "content": "response"},
        ])
        assert inserted == 2  # Only valid + assistant

        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv)
        )
        msgs = result.scalars().all()
        assert len(msgs) == 2
        assert msgs[0].content == "valid"
        assert msgs[1].content == "response"

    @pytest.mark.asyncio
    async def test_empty_content_skipped(self, db_session: AsyncSession, conv: str):
        """Redis messages with empty content should be skipped."""
        svc = ChatService(db_session)
        inserted = await svc.sync_redis_to_db(conv, [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "   "},
            {"role": "user", "content": "real message"},
        ])
        assert inserted == 1  # Only the non-empty one

        result = await db_session.execute(
            select(Message).where(Message.conversation_id == conv)
        )
        msgs = result.scalars().all()
        assert len(msgs) == 1
        assert msgs[0].content == "real message"
