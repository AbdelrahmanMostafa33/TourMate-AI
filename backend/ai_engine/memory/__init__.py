# ai_engine/memory/__init__.py

"""
Memory subsystem: Redis-backed session management and conversation history.

Exports:
    - SessionManager          → async Redis CRUD for ConversationState
    - get_session_manager     → singleton accessor
    - ConversationState       → the session state dataclass
    - ConversationPhase       → phase enum
    - TripSlots               → collected trip information
    - ChatMessage             → single message in history
    - build_messages_for_phase → LLM message builder from session state
"""

from ai_engine.memory.redis_memory import SessionManager, get_session_manager
from ai_engine.memory.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
    ChatMessage,
)
from ai_engine.memory.conversation_history import build_messages_for_phase

__all__ = [
    "SessionManager",
    "get_session_manager",
    "ConversationPhase",
    "ConversationState",
    "TripSlots",
    "ChatMessage",
    "build_messages_for_phase",
]
