"""
LLM Configuration — Provider enum, LLMConfig dataclass, registry, and builder factories.

This is the single source of truth for which LLM (provider + model) each agent
role uses.  Agents should call ``get_llm_for_agent(role)`` instead of hard-coding
provider-specific LLM constructors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Provider enum
# ══════════════════════════════════════════════════════════════════════════════


class Provider(str, Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    GROQ = "groq"


# ══════════════════════════════════════════════════════════════════════════════
# LLM config dataclass
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class LLMConfig:
    """Immutable configuration for a single LLM endpoint."""
    provider: Provider
    model: str
    temperature: float = 0.7
    max_tokens: int = 8192


# ══════════════════════════════════════════════════════════════════════════════
# Agent → LLM registry
#
#   Edit this mapping to change which provider / model an agent uses.
#   Keys are agent role names used by get_llm_for_agent().
# ══════════════════════════════════════════════════════════════════════════════

AGENT_LLM_REGISTRY: Dict[str, LLMConfig] = {
    # ── Groq — classification, extraction, validation, persona updates (massive RPD headroom) ──
    "extractor":           LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile", temperature=0.1, max_tokens=512),
    "router":              LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile",  temperature=0.2, max_tokens=2048),
    "preference_reranker": LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile", temperature=0.2, max_tokens=2048),
    "validator":           LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile",  temperature=0.2, max_tokens=2048),
    "review_qa":           LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile",  temperature=0.7, max_tokens=8192),
    "persona_updater":     LLMConfig(Provider.GROQ,   "llama-3.3-70b-versatile",  temperature=0.3, max_tokens=512),

    # ── Gemini — planning (reasoning), vision (multimodal), modification — 20 RPD ──
    "modifier":            LLMConfig(Provider.GEMINI, "gemini-2.5-flash",  temperature=0.0, max_tokens=8192),
    "planner":             LLMConfig(Provider.GEMINI, "gemini-2.5-flash",  temperature=0.7, max_tokens=8192),
    "vision":              LLMConfig(Provider.GEMINI, "gemini-2.5-flash",  temperature=0.7, max_tokens=8192),
    
    # ── Groq — hotel selection (massive RPD headroom) ──
    "hotel_selector":      LLMConfig(Provider.GROQ, "llama-3.3-70b-versatile", temperature=0.3, max_tokens=8192),
}


# ══════════════════════════════════════════════════════════════════════════════
# Builder factories
# ══════════════════════════════════════════════════════════════════════════════


def _build_gemini_llm(config: LLMConfig, api_key: str | None = None) -> BaseChatModel:
    """Create a ChatGoogleGenerativeAI instance from config."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if api_key is None:
        from ai_engine.llm.key_manager import key_manager
        api_key = key_manager.get_key(Provider.GEMINI) or ""

    return ChatGoogleGenerativeAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        google_api_key=api_key,
        max_retries=0,  # invoke_with_fallback handles retry externally
    )


def _build_groq_llm(config: LLMConfig, api_key: str | None = None) -> BaseChatModel:
    """Create a ChatGroq instance from config."""
    from langchain_groq import ChatGroq

    if api_key is None:
        from ai_engine.llm.key_manager import key_manager
        api_key = key_manager.get_key(Provider.GROQ) or ""

    return ChatGroq(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        groq_api_key=api_key,
        max_retries=0,  # invoke_with_fallback handles retry externally
    )


_PROVIDER_BUILDERS = {
    Provider.GEMINI: _build_gemini_llm,
    Provider.GROQ:   _build_groq_llm,
}


# ══════════════════════════════════════════════════════════════════════════════
# Factory — returns the right LLM instance for a given agent role
# ══════════════════════════════════════════════════════════════════════════════


def get_llm_for_agent(agent_role: str) -> BaseChatModel:
    """
    Return the configured LLM instance for *agent_role*.

    Uses the next available key from ``key_manager``.
    Raises ``ValueError`` if the role is unknown or all keys are exhausted.
    """
    config = AGENT_LLM_REGISTRY.get(agent_role)
    if config is None:
        available = ", ".join(sorted(AGENT_LLM_REGISTRY))
        raise ValueError(
            f"Unknown agent role '{agent_role}'. "
            f"Available roles: {available}"
        )

    from ai_engine.llm.key_manager import key_manager

    api_key = key_manager.get_key(config.provider)
    if api_key is None:
        total = key_manager.get_total_count(config.provider)
        if total == 0:
            raise RuntimeError(
                f"No API keys configured for {config.provider.value}. "
                f"Set {config.provider.value.upper()}_API_KEY in your .env file."
            )
        raise RuntimeError(
            f"All {total} API key(s) for {config.provider.value} are exhausted "
            f"(role: {agent_role}). Wait for rate-limit reset or add more keys."
        )

    builder = _PROVIDER_BUILDERS[config.provider]
    return builder(config, api_key=api_key)


def get_config_for_agent(agent_role: str) -> LLMConfig:
    """Return the raw LLMConfig for an agent role (useful for logging / debugging)."""
    config = AGENT_LLM_REGISTRY.get(agent_role)
    if config is None:
        available = ", ".join(sorted(AGENT_LLM_REGISTRY))
        raise ValueError(
            f"Unknown agent role '{agent_role}'. "
            f"Available roles: {available}"
        )
    return config
