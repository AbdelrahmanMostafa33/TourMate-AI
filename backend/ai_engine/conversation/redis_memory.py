# ai_engine/conversation/redis_memory.py

"""
Redis-backed session manager for ConversationState persistence.

Provides async CRUD operations for storing and retrieving conversation
sessions.  Each session is stored as a JSON blob in Redis with a configurable
TTL (time-to-live) for automatic expiry of stale sessions.

Storage layout:
    Key:   session:{session_id}          → full ConversationState JSON
    Key:   user_sessions:{user_id}       → sorted set of session_ids (by timestamp)
    Key:   user_active_session:{user_id} → session_id of the currently active session

Usage:
    manager = SessionManager()
    await manager.connect()

    state = ConversationState(user_id="abc123")
    await manager.save(state)

    loaded = await manager.load(state.session_id)
    assert loaded.user_id == "abc123"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

import redis.asyncio as aioredis
from redis.exceptions import WatchError

from ai_engine.conversation.conversation_state import ConversationState
from ai_engine.constants import (
    SESSION_TTL_SECONDS,
    REDIS_SESSION_PREFIX,
    REDIS_USER_SESSIONS_PREFIX,
    REDIS_ACTIVE_SESSION_PREFIX,
)

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Async Redis-backed manager for ConversationState objects.

    Responsibilities:
        - Save / load / delete session state to/from Redis
        - Track which session is "active" for each user
        - Maintain a per-user list of session IDs for history lookup
        - Auto-expire stale sessions via Redis TTL

    All operations are idempotent and handle Redis connection failures
    gracefully (log warning, return None / empty list).
    """

    def __init__(self, redis_url: Optional[str] = None):
        if redis_url is None:
            from app.core.config import settings
            redis_url = settings.REDIS_URL

        self._redis_url = redis_url
        self._redis: Optional[aioredis.Redis] = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Establish the Redis connection pool."""
        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                max_connections=10,
                protocol=2,
            )
            await self._redis.ping()
            logger.info("SessionManager connected to Redis at %s", self._redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            self._redis = None

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    # ── Core CRUD ────────────────────────────────────────────────────────────

    async def save(self, state: ConversationState) -> bool:
        if not self._redis:
            logger.warning("Redis not connected — cannot save session %s", state.session_id)
            return False

        key = f"{REDIS_SESSION_PREFIX}{state.session_id}"
        user_key = f"{REDIS_USER_SESSIONS_PREFIX}{state.user_id}"
        active_key = f"{REDIS_ACTIVE_SESSION_PREFIX}{state.user_id}"
        timestamp = datetime.now(timezone.utc).timestamp()

        # ── Optimistic concurrency: WATCH the session key ────────────────
        #    If another concurrent request modifies the key between our WATCH
        #    and EXEC, the transaction aborts (EXEC returns None / WatchError).
        #    This prevents lost-update races in the load→modify→save cycle.
        try:
            await self._redis.watch(key)
            state.version += 1
            data = json.dumps(state.to_dict())

            pipe = self._redis.pipeline()
            pipe.multi()
            pipe.set(key, data, ex=SESSION_TTL_SECONDS)
            pipe.zadd(user_key, {state.session_id: timestamp})
            pipe.set(active_key, state.session_id, ex=SESSION_TTL_SECONDS)
            await pipe.execute()

            logger.debug(
                "Saved session %s (v%d) for user %s",
                state.session_id, state.version, state.user_id,
            )
            return True
        except WatchError:
            logger.warning(
                "[OptimisticLock] Concurrent modification detected for session %s "
                "(v%d) — save aborted. Caller should reload and retry.",
                state.session_id, state.version,
            )
            # Decrement version since the save didn't go through
            state.version -= 1
            return False
        except Exception as e:
            logger.error("Failed to save session %s: %s", state.session_id, e)
            return False

    async def load(self, session_id: str) -> Optional[ConversationState]:
        if not self._redis:
            logger.warning("Redis not connected — cannot load session %s", session_id)
            return None

        try:
            key = f"{REDIS_SESSION_PREFIX}{session_id}"
            data = await self._redis.get(key)
            if data is None:
                logger.debug("Session %s not found in Redis", session_id)
                return None
            return ConversationState.from_dict(json.loads(data))
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None

    async def delete(self, session_id: str) -> bool:
        if not self._redis:
            return False

        try:
            key = f"{REDIS_SESSION_PREFIX}{session_id}"
            state = await self.load(session_id)
            if state:
                user_key = f"{REDIS_USER_SESSIONS_PREFIX}{state.user_id}"
                pipe = self._redis.pipeline()
                pipe.delete(key)
                pipe.zrem(user_key, session_id)
                await pipe.execute()
            else:
                await self._redis.delete(key)
            logger.debug("Deleted session %s", session_id)
            return True
        except Exception as e:
            logger.error("Failed to delete session %s: %s", session_id, e)
            return False

    # ── User-level queries ───────────────────────────────────────────────────

    async def get_active_session(self, user_id: str) -> Optional[ConversationState]:
        if not self._redis:
            return None

        try:
            active_key = f"{REDIS_ACTIVE_SESSION_PREFIX}{user_id}"
            session_id = await self._redis.get(active_key)
            if session_id is None:
                return None
            return await self.load(session_id)
        except Exception as e:
            logger.error("Failed to get active session for user %s: %s", user_id, e)
            return None

    async def get_user_sessions(self, user_id: str, limit: int = 10) -> List[ConversationState]:
        if not self._redis:
            return []

        try:
            user_key = f"{REDIS_USER_SESSIONS_PREFIX}{user_id}"
            session_ids = await self._redis.zrevrange(user_key, 0, limit - 1)
            states: List[ConversationState] = []
            for sid in session_ids:
                state = await self.load(sid)
                if state:
                    states.append(state)
            return states
        except Exception as e:
            logger.error("Failed to get sessions for user %s: %s", user_id, e)
            return []

    async def has_active_session(self, user_id: str) -> bool:
        if not self._redis:
            return False
        active_key = f"{REDIS_ACTIVE_SESSION_PREFIX}{user_id}"
        return bool(await self._redis.exists(active_key))

    # ── Phase-aware helpers ──────────────────────────────────────────────────

    async def resume_or_create(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        recovery_state: Optional[dict] = None,
    ) -> ConversationState:
        # ── Explicit session resume ──────────────────────────────────────
        # When the caller provides a session_id (e.g. reconnecting to an
        # existing chat after a WebSocket drop), try to resume that exact
        # session.  If the session expired from Redis, try recovery_state
        # from the DB state_snapshot, then active session, then fresh.
        logger.info(
            "[DIAG][resume_or_create] Entry: user_id=%s session_id=%s recovery_state_has=%s",
            user_id, session_id, (recovery_state is not None),
        )

        if session_id:
            state = await self.load(session_id)
            if state and state.user_id == user_id:
                logger.info(
                    "[DIAG][resume_or_create] PATH=redis_hit session=%s user=%s phase=%s dest=%s",
                    session_id, user_id, state.phase.value,
                    state.slots.destination_city,
                )
                return state

            # ── Attempt recovery from DB state_snapshot ────────────────
            # When Redis data is lost (session expired / Redis restarted),
            # the caller can provide a recovery_state dict from the
            # Conversation.state_snapshot column.  This allows reconstructing
            # the session's phase, slots, and turn_count from PostgreSQL.
            if recovery_state:
                logger.info(
                    "[DIAG][resume_or_create] PATH=redis_miss_recovery session=%s user=%s recovery_phase=%s",
                    session_id, user_id, recovery_state.get("phase"),
                )
                recovery_state["user_id"] = user_id
                recovered = ConversationState.from_dict(recovery_state)
                await self.save(recovered)
                return recovered

            # session_id provided but not found — try active session as
            # fallback, then create fresh.
            state = await self.get_active_session(user_id)
            if state:
                logger.info(
                    "[DIAG][resume_or_create] PATH=active_session session=%s user=%s active=%s phase=%s",
                    session_id, user_id, state.session_id, state.phase.value,
                )
                return state

            logger.info(
                "[DIAG][resume_or_create] PATH=fresh_with_session session=%s user=%s — no active session",
                session_id, user_id,
            )
            new_state = ConversationState(user_id=user_id)
            await self.save(new_state)
            return new_state

        # ── No session_id — use recovery_state if available, else fresh ────
        # When the caller does NOT provide a session_id but DOES provide a
        # recovery_state (e.g. reconnecting to an existing chat from history),
        # we reconstruct the ConversationState from the DB state_snapshot.
        #
        # This handles the critical reconnection scenario: the user opens
        # a chat from history, the Flutter app reconnects to /ws/chat/{trip_id},
        # but ai_session_id is None (in-memory, lost on disconnect).  Without
        # this path, the AI engine would start with a fresh GREETING state,
        # losing all previously collected phase, slots, and context.
        #
        # Previously we fell back to get_active_session(), which leaked stale
        # session data (destination, interests, etc.) from an OLD trip-planning
        # conversation into a brand-new chat — causing "hello" to immediately
        # trigger the full planning pipeline.
        if recovery_state:
            recovered = ConversationState.from_dict(recovery_state)
            logger.info(
                "[DIAG][resume_or_create] PATH=recovery_no_session user=%s "
                "recovery_phase=%s dest=%s turn_count=%s -> restored_session=%s",
                user_id, recovery_state.get("phase"),
                recovery_state.get("slots", {}).get("destination_city"),
                recovery_state.get("turn_count"),
                recovered.session_id,
            )
            recovery_state["user_id"] = user_id
            recovered = ConversationState.from_dict(recovery_state)
            await self.save(recovered)
            return recovered

        logger.info(
            "[DIAG][resume_or_create] PATH=fresh_no_session user=%s — no recovery_state",
            user_id,
        )
        new_state = ConversationState(user_id=user_id)
        await self.save(new_state)
        return new_state

    async def save_and_update_active(self, state: ConversationState) -> bool:
        return await self.save(state)

    # ── TTL management ───────────────────────────────────────────────────────

    async def extend_ttl(self, session_id: str) -> bool:
        if not self._redis:
            return False

        try:
            key = f"{REDIS_SESSION_PREFIX}{session_id}"
            await self._redis.expire(key, SESSION_TTL_SECONDS)
            return True
        except Exception as e:
            logger.error("Failed to extend TTL for session %s: %s", session_id, e)
            return False

    async def cleanup_expired(self) -> int:
        if not self._redis:
            return 0

        removed = 0
        try:
            async for user_key in self._redis.scan_iter(match=f"{REDIS_USER_SESSIONS_PREFIX}*"):
                session_ids = await self._redis.zrange(user_key, 0, -1)
                for sid in session_ids:
                    key = f"{REDIS_SESSION_PREFIX}{sid}"
                    exists = await self._redis.exists(key)
                    if not exists:
                        await self._redis.zrem(user_key, sid)
                        removed += 1
            return removed
        except Exception as e:
            logger.error("Failed to cleanup expired sessions: %s", e)
            return removed


# ── Singleton ─────────────────────────────────────────────────────────────────

_session_manager: Optional[SessionManager] = None


async def get_session_manager() -> SessionManager:
    """Get or create the singleton SessionManager instance."""
    global _session_manager

    if _session_manager is None:
        _session_manager = SessionManager()
        await _session_manager.connect()
    elif not _session_manager.is_connected:
        await _session_manager.connect()

    return _session_manager
