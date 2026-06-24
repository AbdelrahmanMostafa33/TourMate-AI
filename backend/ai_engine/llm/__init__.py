"""
LLM Configuration Package.

Replaces the monolithic ``llm_config.py`` with a proper package:

    ai_engine/llm/
    ├── __init__.py        — Re-exports the public API
    ├── config.py          — Provider, LLMConfig, AGENT_LLM_REGISTRY, builder functions
    ├── key_manager.py     — KeyManager with multi-key round-robin rotation
    ├── token_tracker.py   — TokenUsage, TokenTracker, _TokenTrackingCallback
    └── invoke.py          — invoke_with_fallback with automatic retry + key rotation

Usage::

    from ai_engine.llm import get_llm_for_agent, invoke_with_fallback, token_tracker

    llm = get_llm_for_agent("planner")      # → Gemini 2.5 Flash
    response = await invoke_with_fallback("router", messages)
    token_tracker.print_summary()
"""

from ai_engine.llm.config import (
    Provider,
    LLMConfig,
    AGENT_LLM_REGISTRY,
    get_llm_for_agent,
    get_config_for_agent,
)
from ai_engine.llm.key_manager import KeyManager, key_manager
from ai_engine.llm.token_tracker import TokenUsage, TokenTracker, token_tracker
from ai_engine.llm.invoke import invoke_with_fallback

__all__ = [
    "Provider",
    "LLMConfig",
    "AGENT_LLM_REGISTRY",
    "get_llm_for_agent",
    "get_config_for_agent",
    "KeyManager",
    "key_manager",
    "TokenUsage",
    "TokenTracker",
    "token_tracker",
    "invoke_with_fallback",
]
