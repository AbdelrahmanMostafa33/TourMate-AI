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
from ai_engine.conversation.conversation_state import ConversationPhase, ConversationState
from ai_engine.conversation.redis_memory import SessionManager
from redis.exceptions import WatchError


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
        with patch("ai_engine.conversation.redis_memory.aioredis") as mock_aioredis:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock(return_value=True)
            mock_aioredis.from_url.return_value = mock_redis
            await mgr.connect()
            assert mgr.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_sets_none(self):
        mgr = SessionManager(redis_url="redis://localhost:6379/0")
        with patch("ai_engine.conversation.redis_memory.aioredis") as mock_aioredis:
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


# ── Optimistic Locking Tests ──────────────────────────────────────────────────

class TestOptimisticLocking:
    """Tests for the optimistic concurrency control in SessionManager.save().

    The save() method uses Redis WATCH + MULTI + EXEC to detect concurrent
    modifications.  If the watched key is modified between WATCH and EXEC,
    redis-py raises WatchError, and save() must:
      - Return False
      - Decrement the version counter (since it was optimistically incremented)
    """

    @pytest.mark.asyncio
    async def test_save_watch_error_returns_false(self, manager, mock_redis):
        """When pipe.execute() raises WatchError, save() should return False."""
        state = ConversationState(user_id="user123")
        version_before = state.version  # Should be 0

        # Make pipe.execute raise WatchError (simulates concurrent modification)
        mock_redis.pipeline.return_value.execute = AsyncMock(side_effect=WatchError())

        result = await manager.save(state)

        assert result is False
        # Version should be decremented back to original
        assert state.version == version_before

    @pytest.mark.asyncio
    async def test_watch_error_version_rollback_after_mutations(self, manager, mock_redis):
        """Version should rollback correctly even if _touch() was called before save."""
        state = ConversationState(user_id="user123")
        state._touch()  # version → 1
        state._touch()  # version → 2
        assert state.version == 2

        # Make pipe.execute raise WatchError
        mock_redis.pipeline.return_value.execute = AsyncMock(side_effect=WatchError())

        result = await manager.save(state)

        assert result is False
        # Version should go: 2 → 3 (save increments) → 2 (WatchError decrements)
        assert state.version == 2
        # The _touch() increments (from 0 to 2) should be preserved

    @pytest.mark.asyncio
    async def test_concurrent_save_first_wins(self, manager, mock_redis):
        """First save succeeds, second concurrent save gets WatchError.

        Simulates two concurrent requests both trying to save the same session.
        The first one succeeds (pipe.execute returns normally), the second one
        gets WatchError because the key was modified by the first.
        """
        state = ConversationState(user_id="user123")

        # First save succeeds
        mock_redis.pipeline.return_value.execute = AsyncMock(return_value=[True, True, True])
        result1 = await manager.save(state)
        assert result1 is True
        version_after_first = state.version  # Should be 1

        # Now simulate a second concurrent save: the key was modified
        # so pipe.execute raises WatchError
        mock_redis.pipeline.return_value.execute = AsyncMock(side_effect=WatchError())
        result2 = await manager.save(state)
        assert result2 is False
        # Version should rollback to what it was after the first save
        assert state.version == version_after_first

    @pytest.mark.asyncio
    async def test_watch_error_still_returns_false_on_retry(self, manager, mock_redis):
        """Even on retry, if the conflict persists, save() still returns False.

        This tests that WatchError is caught each time, not just on the first attempt.
        """
        state = ConversationState(user_id="user123")
        version_before = state.version

        # Make execute raise WatchError every time it's called
        mock_redis.pipeline.return_value.execute = AsyncMock(side_effect=WatchError())

        # First attempt
        result1 = await manager.save(state)
        assert result1 is False
        assert state.version == version_before

        # Second attempt (after state was reloaded and modified again)
        state._touch()  # version → 1
        result2 = await manager.save(state)
        assert result2 is False
        # Version rolled back from 2 → 1 (save bumped to 2, WatchError bumped back to 1)
        assert state.version == 1

    @pytest.mark.asyncio
    async def test_normal_save_still_works(self, manager, mock_redis):
        """Normal saves (no conflict) should work as expected with version increment."""
        state = ConversationState(user_id="user123")
        assert state.version == 0

        result = await manager.save(state)
        assert result is True
        assert state.version == 1  # Incremented by save

        # Second save
        result2 = await manager.save(state)
        assert result2 is True
        assert state.version == 2  # Incremented again


# ── Recovery from DB state_snapshot Tests ─────────────────────────────────────

class TestRecoveryFromStateSnapshot:
    """Tests for the recovery path in resume_or_create().

    When Redis data is lost (session expired / Redis restarted), the caller
    can provide a ``recovery_state`` dict (from the DB state_snapshot column)
    so the session can be reconstructed from PostgreSQL alone.
    """

    @pytest.fixture
    def sample_recovery_state(self) -> dict:
        """A minimal state_snapshot dict matching what save_state_snapshot() produces."""
        return {
            "phase":               "slot_filling",
            "slots": {
                "destination_city":       "Paris",
                "destination_country":    "France",
                "duration_days":          5,
                "travel_dates":           None,
                "group_size":             2,
                "traveler_group_type":    "couple",
                "special_requests":       None,
                "origin_city":            None,
                "selected_flight_offer":  None,
                "flight_search_results":  None,
                "preferred_cabin_class":  None,
                "is_round_trip":          None,
                "return_date":            None,
                "budget_level":           "moderate",
                "travel_style":           "cultural",
                "pace":                   "moderate",
                "interests":              ["history", "food"],
                "food_preferences":       ["local cuisine"],
                "accommodation_preferences": ["hotel"],
            },
            "turn_count":          7,
            "itinerary_id":        None,
            "trip_id":             None,
            "last_question_field": "interests",
            "updated_at":          "2026-07-02T12:00:00",
        }

    @pytest.mark.asyncio
    async def test_recovery_reconstructs_state(self, manager, mock_redis, sample_recovery_state):
        """When Redis returns None, recovery_state should be used to reconstruct the session."""
        # Redis.load() returns None (session expired)
        mock_redis.get = AsyncMock(return_value=None)

        state = await manager.resume_or_create(
            user_id="user123",
            session_id="expired_session",
            recovery_state=sample_recovery_state,
        )

        # Verify the recovered state matches the snapshot
        assert state.user_id == "user123"  # Overridden by resume_or_create
        assert state.phase == ConversationPhase.SLOT_FILLING
        assert state.turn_count == 7
        assert state.slots.destination_city == "Paris"
        assert state.slots.destination_country == "France"
        assert state.slots.duration_days == 5
        assert state.slots.group_size == 2
        assert state.slots.budget_level == "moderate"
        assert state.slots.interests == ["history", "food"]
        assert state.last_question_field == "interests"

        # Verify the recovered state was saved to Redis
        assert mock_redis.pipeline.called

    @pytest.mark.asyncio
    async def test_recovery_ignored_when_session_exists(self, manager, mock_redis):
        """If Redis has the session, recovery_state should be ignored."""
        existing = ConversationState(user_id="user123")
        existing.transition_to(ConversationPhase.SLOT_FILLING)
        existing.slots.destination_city = "London"
        existing.turn_count = 3

        # Redis.load() returns an existing session
        mock_redis.get = AsyncMock(return_value=json.dumps(existing.to_dict()))

        # Provide a different recovery_state
        recovery = {
            "phase": "completed",
            "slots": {},
            "turn_count": 99,
        }

        state = await manager.resume_or_create(
            user_id="user123",
            session_id=existing.session_id,
            recovery_state=recovery,
        )

        # The Redis session should take precedence
        assert state.session_id == existing.session_id
        assert state.slots.destination_city == "London"
        assert state.turn_count == 3
        assert state.phase == ConversationPhase.SLOT_FILLING

    @pytest.mark.asyncio
    async def test_recovery_works_without_session_id(self, manager, mock_redis, sample_recovery_state):
        """Without a session_id but with recovery_state, the state should be reconstructed.

        This is the critical reconnection-from-history path: when the user opens
        a chat from history, ai_session_id is None (in-memory, lost on disconnect)
        but recovery_state is available from conversation.state_snapshot.
        """
        mock_redis.get = AsyncMock(return_value=None)

        state = await manager.resume_or_create(
            user_id="user123",
            recovery_state=sample_recovery_state,
        )

        # State should be recovered, not fresh
        assert state.user_id == "user123"
        assert state.phase == ConversationPhase.SLOT_FILLING
        assert state.turn_count == 7
        assert state.slots.destination_city == "Paris"
        assert state.slots.duration_days == 5
        assert state.slots.group_size == 2
        assert state.slots.budget_level == "moderate"
        assert state.slots.interests == ["history", "food"]
        assert state.last_question_field == "interests"

        # Verify the recovered state was saved to Redis
        assert mock_redis.pipeline.called

    @pytest.mark.asyncio
    async def test_recovery_user_id_override(self, manager, mock_redis):
        """recovery_state.user_id should be overridden with the caller's user_id."""
        mock_redis.get = AsyncMock(return_value=None)

        # Recovery state WITHOUT user_id (as save_state_snapshot would produce it)
        recovery = {
            "phase": "slot_filling",
            "slots": {"destination_city": "Rome"},
            "turn_count": 2,
        }

        state = await manager.resume_or_create(
            user_id="user456",
            session_id="lost_session",
            recovery_state=recovery,
        )

        assert state.user_id == "user456"
        assert state.slots.destination_city == "Rome"

    @pytest.mark.asyncio
    async def test_recovery_fallback_to_active_when_no_recovery(self, manager, mock_redis):
        """When session is not in Redis and no recovery_state, fall back to active session."""
        # Create an active session
        active = ConversationState(user_id="user123", session_id="active_sess")
        active.transition_to(ConversationPhase.ITINERARY_REVIEW)

        # First call to Redis.get returns None (expired session)
        # Second call returns the active session ID, third call returns its data
        mock_redis.get = AsyncMock(side_effect=[
            None,                              # load("given_sess") → None
            "active_sess",                     # get_active_session → session_id
            json.dumps(active.to_dict()),       # load("active_sess") → state
        ])
        mock_redis.exists = AsyncMock(return_value=True)

        state = await manager.resume_or_create(
            user_id="user123",
            session_id="given_sess",
        )

        assert state.session_id == "active_sess"
        assert state.phase == ConversationPhase.ITINERARY_REVIEW

    @pytest.mark.asyncio
    async def test_recovery_preserves_complex_slots(self, manager, mock_redis):
        """Verify that all slot fields, including lists and nested data, are preserved."""
        mock_redis.get = AsyncMock(return_value=None)

        recovery = {
            "phase": "itinerary_review",
            "slots": {
                "destination_city": "Tokyo",
                "destination_country": "Japan",
                "duration_days": 7,
                "travel_dates": "July 15-22, 2026",
                "group_size": 3,
                "traveler_group_type": "friends",
                "special_requests": ["vegetarian meals", "wheelchair accessible"],
                "origin_city": "New York",
                "selected_flight_offer": None,
                "flight_search_results": None,
                "preferred_cabin_class": None,
                "is_round_trip": True,
                "return_date": "2026-07-22",
                "budget_level": "luxury",
                "travel_style": "adventure",
                "pace": "packed",
                "interests": ["temples", "food", "anime", "shopping"],
                "food_preferences": ["ramen", "sushi", "street food"],
                "accommodation_preferences": ["hotel", "ryokan"],
            },
            "turn_count": 12,
            "itinerary_id": "itin_001",
            "trip_id": "trip_abc",
            "last_question_field": None,
            "updated_at": "2026-07-02T15:30:00",
        }

        state = await manager.resume_or_create(
            user_id="user789",
            session_id="tokyo_session",
            recovery_state=recovery,
        )

        # Phase and turn count
        assert state.phase == ConversationPhase.ITINERARY_REVIEW
        assert state.turn_count == 12

        # Scalar slots
        assert state.slots.destination_city == "Tokyo"
        assert state.slots.destination_country == "Japan"
        assert state.slots.duration_days == 7
        assert state.slots.travel_dates == "July 15-22, 2026"
        assert state.slots.group_size == 3
        assert state.slots.traveler_group_type == "friends"
        assert state.slots.origin_city == "New York"
        assert state.slots.is_round_trip is True
        assert state.slots.return_date == "2026-07-22"
        assert state.slots.budget_level == "luxury"
        assert state.slots.travel_style == "adventure"
        assert state.slots.pace == "packed"
        assert state.slots.preferred_cabin_class is None

        # List slots
        assert state.slots.special_requests == ["vegetarian meals", "wheelchair accessible"]
        assert state.slots.interests == ["temples", "food", "anime", "shopping"]
        assert state.slots.food_preferences == ["ramen", "sushi", "street food"]
        assert state.slots.accommodation_preferences == ["hotel", "ryokan"]
        assert state.slots.flight_search_results is None
        assert state.slots.selected_flight_offer is None

        # Non-slot fields
        assert state.itinerary_id == "itin_001"
        assert state.trip_id == "trip_abc"
        assert state.last_question_field is None
