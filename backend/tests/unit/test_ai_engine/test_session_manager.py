# backend/tests/unit/test_ai_engine/test_session_manager.py

"""
Unit tests for the Redis-backed SessionManager.

Uses unittest.mock to avoid requiring a live Redis instance.
Tests cover:
    - save / load / delete CRUD operations
    - resume_or_create logic
    - get_active_session
    - Graceful handling when Redis is unavailable
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ai_engine.memory.conversation_state import ConversationPhase, ConversationState
from ai_engine.memory.redis_memory import SessionManager


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Create a mock Redis client with async methods."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=False)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zrevrange = AsyncMock(return_value=[])
    redis.expire = AsyncMock(return_value=True)

    # Pipeline mock
    pipe = AsyncMock()
    pipe.set = MagicMock(return_value=pipe)
    pipe.zadd = MagicMock(return_value=pipe)
    pipe.zrem = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[True, True, True])
    redis.pipeline = MagicMock(return_value=pipe)

    return redis


@pytest.fixture
def manager(mock_redis):
    """Create a SessionManager with mocked Redis."""
    mgr = SessionManager(redis_url="redis://localhost:6379/0")
    mgr._redis = mock_redis
    return mgr


# ── Connection Tests ──────────────────────────────────────────────────────────

class TestConnection:

    def test_initially_not_connected(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        assert mgr.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_sets_redis(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        with patch("ai_engine.memory.redis_memory.aioredis") as mock_aioredis:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_aioredis.from_url.return_value = mock_redis
            await mgr.connect()
            assert mgr.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_sets_none(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        with patch("ai_engine.memory.redis_memory.aioredis") as mock_aioredis:
            mock_aioredis.from_url.side_effect = Exception("Connection refused")
            await mgr.connect()
            assert mgr.is_connected is False

    @pytest.mark.asyncio
    async def test_close(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        mgr._redis = AsyncMock()
        await mgr.close()
        assert mgr.is_connected is False


# ── Save / Load Tests ─────────────────────────────────────────────────────────

class TestSaveLoad:

    @pytest.mark.asyncio
    async def test_save_returns_true(self, manager, mock_redis):
        state = ConversationState(user_id="user123")
        result = await manager.save(state)
        assert result is True
        mock_redis.pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_when_disconnected_returns_false(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        state = ConversationState(user_id="user123")
        result = await mgr.save(state)
        assert result is False

    @pytest.mark.asyncio
    async def test_load_returns_state(self, manager, mock_redis):
        state = ConversationState(user_id="user123")
        state_dict = state.to_dict()
        mock_redis.get = AsyncMock(return_value=json.dumps(state_dict))

        loaded = await manager.load(state.session_id)
        assert loaded is not None
        assert loaded.user_id == "user123"

    @pytest.mark.asyncio
    async def test_load_not_found_returns_none(self, manager, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        loaded = await manager.load("nonexistent_id")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_when_disconnected_returns_none(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        loaded = await mgr.load("any_id")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete_calls_redis(self, manager, mock_redis):
        # Mock load to return a state for cleanup
        state = ConversationState(user_id="user123")
        mock_redis.get = AsyncMock(return_value=json.dumps(state.to_dict()))

        result = await manager.delete(state.session_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_when_disconnected_returns_false(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        result = await mgr.delete("any_id")
        assert result is False


# ── User-level Query Tests ────────────────────────────────────────────────────

class TestUserQueries:

    @pytest.mark.asyncio
    async def test_get_active_session_returns_none_when_no_session(self, manager, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await manager.get_active_session("user123")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_session_loads_state(self, manager, mock_redis):
        state = ConversationState(user_id="user123")
        # First call: get active session ID, Second call: load session data
        mock_redis.get = AsyncMock(side_effect=[
            state.session_id,  # get active session ID
            json.dumps(state.to_dict()),  # load session data
        ])

        result = await manager.get_active_session("user123")
        assert result is not None
        assert result.user_id == "user123"

    @pytest.mark.asyncio
    async def test_has_active_session(self, manager, mock_redis):
        mock_redis.exists = AsyncMock(return_value=True)
        result = await manager.has_active_session("user123")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_no_active_session(self, manager, mock_redis):
        mock_redis.exists = AsyncMock(return_value=False)
        result = await manager.has_active_session("user123")
        assert result is False


# ── resume_or_create Tests ────────────────────────────────────────────────────

class TestResumeOrCreate:

    @pytest.mark.asyncio
    async def test_creates_new_when_nothing_exists(self, manager, mock_redis):
        state = await manager.resume_or_create("user123")
        assert state.user_id == "user123"
        assert state.phase == ConversationPhase.GREETING
        # save should have been called (to persist the new session)
        assert mock_redis.pipeline.called

    @pytest.mark.asyncio
    async def test_resumes_specific_session(self, manager, mock_redis):
        state = ConversationState(user_id="user123")
        state.transition_to(ConversationPhase.SLOT_FILLING)
        mock_redis.get = AsyncMock(return_value=json.dumps(state.to_dict()))

        resumed = await manager.resume_or_create("user123", session_id=state.session_id)
        assert resumed.phase == ConversationPhase.SLOT_FILLING
        assert resumed.user_id == "user123"

    @pytest.mark.asyncio
    async def test_rejects_wrong_user_session(self, manager, mock_redis):
        """If session belongs to a different user, should create new one."""
        state = ConversationState(user_id="other_user")
        # load() returns the other user's state, but active session lookup returns None
        mock_redis.get = AsyncMock(side_effect=[
            json.dumps(state.to_dict()),  # load() for specific session_id
            None,                          # get_active_session() active key
        ])
        mock_redis.exists = AsyncMock(return_value=False)

        result = await manager.resume_or_create("user123", session_id=state.session_id)
        # Should create a new session since user_id doesn't match
        assert result.user_id == "user123"
        assert result.session_id != state.session_id


# ── TTL Tests ─────────────────────────────────────────────────────────────────

class TestTTL:

    @pytest.mark.asyncio
    async def test_extend_ttl(self, manager, mock_redis):
        result = await manager.extend_ttl("session_abc")
        assert result is True
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_extend_ttl_when_disconnected(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        result = await mgr.extend_ttl("session_abc")
        assert result is False
