"""
Conversation subsystem — stateful multi-turn chat with Redis persistence.

Merges the old ``chat/`` and ``memory/`` directories, which were tightly coupled.

Exports:
    - handle_chat               → synchronous entry point
    - handle_chat_stream        → streaming entry point (WebSocket)
    - interpret_message         → single LLM call for intent + extraction
    - InterpretationResult      → structured output from interpret_message
    - SessionManager            → async Redis CRUD for ConversationState
    - get_session_manager       → singleton accessor
    - ConversationState         → the session state dataclass
    - ConversationPhase         → phase enum (GREETING, SLOT_FILLING, PLAN_GENERATION, etc.)
    - TripSlots                 → collected trip information
    - ChatMessage               → single message in history
"""

from ai_engine.conversation.orchestrator import handle_chat, handle_chat_stream
from ai_engine.conversation.message_interpreter import interpret_message, InterpretationResult
from ai_engine.conversation.redis_memory import SessionManager, get_session_manager
from ai_engine.conversation.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
    ChatMessage,
)

__all__ = [
    "handle_chat",
    "handle_chat_stream",
    "interpret_message",
    "InterpretationResult",
    "SessionManager",
    "get_session_manager",
    "ConversationPhase",
    "ConversationState",
    "TripSlots",
    "ChatMessage",
]
