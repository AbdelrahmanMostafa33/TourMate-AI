# ai_engine/llm_config.py

"""
Shared LLM configuration registry with API key rotation and rate-limit fallback.

Centralizes all LLM provider assignments in one place so that swapping
a provider for any agent is a single-line change.  Agents should call
``get_llm_for_agent(role)`` instead of hard-coding provider-specific
LLM constructors.

Key rotation:
    Set comma-separated API keys in your .env to enable automatic fallback:
        GOOGLE_API_KEY=key1,key2,key3
        GROQ_API_KEY=key1,key2,key3
    When a key hits a 429 rate limit, the next available key is tried.

Usage::

    from ai_engine.llm_config import get_llm_for_agent, invoke_with_fallback

    llm = get_llm_for_agent("planner")      # → Gemini 2.5 Flash
    llm = get_llm_for_agent("router")        # → Groq Llama 3.3 70B

    # Automatic fallback on rate limits:
    response = await invoke_with_fallback("planner", messages)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Token Tracker — tracks token usage across all LLM calls
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TokenUsage:
    """Token counts for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TokenTracker:
    """Tracks cumulative token usage across all LLM calls in a session.

    Usage::

        from ai_engine.llm_config import token_tracker

        # After each LLM call, pass the response:
        token_tracker.record("router", response)

        # Print summary:
        token_tracker.print_summary()
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []  # per-call log
        self._by_role: dict[str, TokenUsage] = {}  # aggregated by role
        self._total = TokenUsage()  # grand total

    def record_from_llm_output(self, role: str, llm_output: dict) -> None:
        """Extract token usage from LLMResult.llm_output and record it.

        This works even with .with_structured_output() because it reads from
        the LLM's raw output, not the parsed response.
        """
        usage_dict = (llm_output or {}).get("token_usage") or {}
        if not usage_dict:
            return

        # Groq format: prompt_tokens, completion_tokens, total_tokens
        # Gemini format: prompt_token_count, candidates_token_count, total_token_count
        prompt = usage_dict.get("prompt_tokens") if "prompt_tokens" in usage_dict else usage_dict.get("prompt_token_count", 0)
        completion = usage_dict.get("completion_tokens") if "completion_tokens" in usage_dict else usage_dict.get("candidates_token_count", 0)
        total = usage_dict.get("total_tokens") if "total_tokens" in usage_dict else usage_dict.get("total_token_count", 0)

        if prompt == 0 and completion == 0:
            return

        usage = TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)
        self._record_usage(role, usage)

    def _record_usage(self, role: str, usage: TokenUsage) -> None:
        """Internal: append usage to tracking data."""
        self._calls.append({
            "role": role,
            "prompt": usage.prompt_tokens,
            "completion": usage.completion_tokens,
            "total": usage.total_tokens,
        })

        agg = self._by_role.setdefault(role, TokenUsage())
        agg.prompt_tokens += usage.prompt_tokens
        agg.completion_tokens += usage.completion_tokens
        agg.total_tokens += usage.total_tokens

        self._total.prompt_tokens += usage.prompt_tokens
        self._total.completion_tokens += usage.completion_tokens
        self._total.total_tokens += usage.total_tokens

        logger.info(
            "[Tokens] %s → prompt=%d  completion=%d  total=%d",
            role, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
        )

    @property
    def total(self) -> TokenUsage:
        """Grand total token usage across all calls."""
        return self._total

    @property
    def call_count(self) -> int:
        """Total number of LLM calls tracked."""
        return len(self._calls)

    def print_summary(self) -> None:
        """Print a formatted summary of all token usage."""
        if not self._calls:
            print("\n[Tokens] No LLM calls recorded.")
            return

        print(f"\n{'='*55}")
        print(f"  Token Usage Summary ({len(self._calls)} LLM calls)")
        print(f"{'='*55}")

        # Per-role breakdown
        print(f"  {'Role':<16} {'Prompt':>8} {'Complete':>8} {'Total':>8}")
        print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*8}")
        for role, usage in sorted(self._by_role.items()):
            print(
                f"  {role:<16} {usage.prompt_tokens:>8,} "
                f"{usage.completion_tokens:>8,} {usage.total_tokens:>8,}"
            )

        # Grand total
        t = self._total
        print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*8}")
        print(
            f"  {'TOTAL':<16} {t.prompt_tokens:>8,} "
            f"{t.completion_tokens:>8,} {t.total_tokens:>8,}"
        )
        print(f"{'='*55}\n")

    def reset(self) -> None:
        """Clear all recorded data."""
        self._calls.clear()
        self._by_role.clear()
        self._total = TokenUsage()


# Singleton token tracker
token_tracker = TokenTracker()


class _TokenTrackingCallback(BaseCallbackHandler):
    """LangChain callback that records token usage after every LLM call.

    Works with both plain and .with_structured_output() calls because it
    reads from LLMResult.llm_output, which is always populated.
    """

    def __init__(self, role: str) -> None:
        self.role = role

    def on_llm_end(self, response, **kwargs) -> None:
        llm_output = getattr(response, "llm_output", None) or {}
        token_tracker.record_from_llm_output(self.role, llm_output)


# ══════════════════════════════════════════════════════════════════════════════
# Provider enum
# ══════════════════════════════════════════════════════════════════════════════

class Provider(str, Enum):
    """Supported LLM providers."""
    GEMINI = "gemini"
    GROQ   = "groq"


# ══════════════════════════════════════════════════════════════════════════════
# LLM config dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class LLMConfig:
    """Immutable configuration for a single LLM endpoint."""
    provider:    Provider
    model:       str
    temperature: float = 0.7
    max_tokens:  int   = 8192


# ══════════════════════════════════════════════════════════════════════════════
# Key Manager — multi-key rotation with rate-limit awareness
# ══════════════════════════════════════════════════════════════════════════════

class KeyManager:
    """
    Manages multiple API keys per provider with round-robin rotation.

    Keys are never marked globally exhausted — callers track failed keys
    locally per retry sequence. ``get_key()`` returns the next available
    key via round-robin, providing ``None`` only when no keys are
    registered for the provider.
    """

    def __init__(self) -> None:
        # provider → ordered list of raw key strings
        self._keys: Dict[Provider, List[str]] = {}
        # Per-provider round-robin index
        self._rr_index: Dict[Provider, int] = {}

    # ── Registration ─────────────────────────────────────────────────────────

    def register_keys(self, provider: Provider, raw: str) -> None:
        """
        Parse a comma-separated key string and register the keys.

        Call this once at startup for each provider.
        """
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        self._keys[provider] = keys
        self._rr_index[provider] = 0
        if keys:
            logger.info(
                "[KeyManager] Registered %d key(s) for %s",
                len(keys), provider.value,
            )

    def get_key(self, provider: Provider) -> Optional[str]:
        """
        Return the next available key for *provider* via round-robin.

        Keys are never marked exhausted — callers handle their own retry
        tracking. Returns ``None`` only if no keys are registered.
        """
        keys = self._keys.get(provider, [])
        if not keys:
            return None

        idx = self._rr_index.get(provider, 0)
        key = keys[idx]
        self._rr_index[provider] = (idx + 1) % len(keys)
        return key

    def get_available_count(self, provider: Provider) -> int:
        """Number of registered keys for *provider*."""
        return len(self._keys.get(provider, []))

    def get_total_count(self, provider: Provider) -> int:
        """Total registered keys for *provider*."""
        return len(self._keys.get(provider, []))


# ── Singleton key manager (populated at import time from settings) ────────────

key_manager = KeyManager()


def _init_key_manager() -> None:
    """Parse env vars and register keys for all providers."""
    from app.core.config import settings

    key_manager.register_keys(Provider.GEMINI, settings.google_api_key)
    key_manager.register_keys(Provider.GROQ, settings.groq_api_key)


# Run once on import
_init_key_manager()


# ══════════════════════════════════════════════════════════════════════════════
# Agent → LLM registry
#
#   Edit this mapping to change which provider / model an agent uses.
#   Keys are agent role names used by get_llm_for_agent().
# ══════════════════════════════════════════════════════════════════════════════

AGENT_LLM_REGISTRY: Dict[str, LLMConfig] = {
    # ── Groq — classification, extraction, validation (massive RPD headroom) ──
    "router":         LLMConfig(Provider.GROQ, "llama-3.3-70b-versatile", temperature=0.7, max_tokens=2048),
    "preference_reranker": LLMConfig(Provider.GROQ, "llama-3.1-8b-instant",  temperature=0.2, max_tokens=2048),
    "validator":      LLMConfig(Provider.GROQ, "llama-3.3-70b-versatile", temperature=0.2, max_tokens=2048),
    "review_qa":      LLMConfig(Provider.GROQ, "llama-3.3-70b-versatile", temperature=0.7, max_tokens=8192),
    "modifier":       LLMConfig(Provider.GROQ, "llama-3.3-70b-versatile", temperature=0.3, max_tokens=8192),

    # ── Gemini — planning (reasoning) and vision (multimodal) — 20 RPD ───────
    "planner":        LLMConfig(Provider.GEMINI, "gemini-2.5-flash", temperature=0.7, max_tokens=8192),
    "vision":         LLMConfig(Provider.GEMINI, "gemini-2.5-flash", temperature=0.7, max_tokens=8192),
}


# ══════════════════════════════════════════════════════════════════════════════
# Factory — returns the right LLM instance for a given agent role
# ══════════════════════════════════════════════════════════════════════════════

def _build_gemini_llm(config: LLMConfig, api_key: str | None = None) -> BaseChatModel:
    """Create a ChatGoogleGenerativeAI instance from config."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    if api_key is None:
        api_key = key_manager.get_key(Provider.GEMINI) or ""

    return ChatGoogleGenerativeAI(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        google_api_key=api_key,
    )


def _build_groq_llm(config: LLMConfig, api_key: str | None = None) -> BaseChatModel:
    """Create a ChatGroq instance from config."""
    from langchain_groq import ChatGroq

    if api_key is None:
        api_key = key_manager.get_key(Provider.GROQ) or ""

    return ChatGroq(
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        groq_api_key=api_key,
    )


_PROVIDER_BUILDERS = {
    Provider.GEMINI: _build_gemini_llm,
    Provider.GROQ:   _build_groq_llm,
}


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


# ══════════════════════════════════════════════════════════════════════════════
# invoke_with_fallback — automatic retry across keys with backoff
# ══════════════════════════════════════════════════════════════════════════════

# Maximum exponential backoff wall-clock delay for transient errors (503 etc.)
# Reduced from 30s to 5s so the pipeline doesn't stall when all keys
# are under temporary load — keys cycle through faster.
_MAX_TRANSIENT_BACKOFF = 5.0  # seconds
# Base backoff before exponential growth
_BASE_TRANSIENT_BACKOFF = 1.0  # seconds


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check whether an exception is a rate-limit (429) error."""
    msg = str(exc).lower()
    # Common 429 indicators across providers
    return any(
        kw in msg
        for kw in (
            "429", "rate limit", "ratelimit", "requests per",
            "tokens per", "quota", "too many requests",
        )
    )


def _is_transient_error(exc: Exception) -> bool:
    """Check whether an exception is a transient server error (503, unavailable).

    Unlike 429 rate limits (key-specific), transient errors affect all keys
    on a provider and are likely to resolve with a short wait.
    """
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "503",
            "unavailable",
            "service unavailable",
            "high demand",
            "temporarily unavailable",
            "server error",
            "internal server error",
            "overloaded",
            "try again later",
        )
    )



async def invoke_with_fallback(
    agent_role: str,
    messages: list[BaseMessage],
    max_retries: int | None = None,
    structured_output: type | None = None,
) -> Any:
    """
    Invoke the LLM for *agent_role* with automatic key rotation and retry.

    Algorithm:
        1. Get next available key from KeyManager.
        2. Build LLM instance with that key.
        3. Call ``llm.ainvoke(messages)``.
        4. On success → return response.
        5. On rate-limit error (429) → mark key exhausted, try next key.
        6. On transient error (503/unavailable) → apply exponential backoff,
           then cycle through all available keys again.
        7. On any other error → raise immediately.
        8. If all retries exhausted → raise the last error.

    Args:
        agent_role:   Role name from ``AGENT_LLM_REGISTRY``.
        messages:     LangChain message list.
        max_retries:  Maximum number of attempts.  Defaults to ``total_keys * 2``
                      so transient errors get at least two full passes.
        structured_output: Optional Pydantic model class for structured output.
                           When provided, the LLM is bound with
                           .with_structured_output(schema) for guaranteed valid JSON.

    Returns:
        The LLM response object (same as ``BaseChatModel.ainvoke``).

    Raises:
        The last error if all retries are exhausted.
    """
    config = AGENT_LLM_REGISTRY.get(agent_role)
    if config is None:
        available = ", ".join(sorted(AGENT_LLM_REGISTRY))
        raise ValueError(
            f"Unknown agent role '{agent_role}'. "
            f"Available roles: {available}"
        )

    provider = config.provider
    total_keys = key_manager.get_total_count(provider)

    # Default: one full pass through all keys (minimum 4 attempts) —
    # avoids wasting time on excessive retry cycles when all keys are
    # rate-limited.  Each attempt immediately tries the next key on 429.
    if max_retries is None:
        max_retries = max(total_keys, 4)

    last_error: Exception | None = None
    # Local set of keys already tried in THIS pass.
    # Keys are NOT marked globally exhausted — they remain available for
    # subsequent calls.
    tried_keys: set[str] = set()

    # Track consecutive transient errors for backoff calculation
    transient_error_count = 0

    for attempt in range(max_retries):
        api_key = key_manager.get_key(provider)
        if api_key is None:
            logger.warning(
                "[Fallback] No available keys for %s on role '%s' — stopping",
                provider.value, agent_role,
            )
            break

        # Skip keys already tried in this retry sequence
        if api_key in tried_keys:
            # All keys exhausted in this pass
            if len(tried_keys) >= total_keys:
                # If the last error was a transient error (503), reset and retry
                # with exponential backoff instead of giving up.
                if last_error is not None and _is_transient_error(last_error):
                    transient_error_count += 1
                    backoff = min(
                        _BASE_TRANSIENT_BACKOFF * (2 ** (transient_error_count - 1)),
                        _MAX_TRANSIENT_BACKOFF,
                    )
                    logger.warning(
                        "[Fallback] All %d key(s) on %s for role '%s' returned transient "
                        "errors — waiting %.1fs before retry cycle (transient #%d)",
                        total_keys, provider.value, agent_role,
                        backoff, transient_error_count,
                    )
                    await asyncio.sleep(backoff)
                    tried_keys.clear()  # Allow another pass through all keys
                    continue
                else:
                    logger.warning(
                        "[Fallback] All %d key(s) tried on %s for role '%s' — stopping",
                        total_keys, provider.value, agent_role,
                    )
                    break
            continue

        try:
            builder = _PROVIDER_BUILDERS[provider]
            llm = builder(config, api_key=api_key)
            if structured_output is not None:
                llm = llm.with_structured_output(structured_output)
            response = await llm.ainvoke(
                messages, config={"callbacks": [_TokenTrackingCallback(agent_role)]}
            )
            return response

        except Exception as exc:
            last_error = exc
            if _is_rate_limit_error(exc):
                tried_keys.add(api_key)
                logger.warning(
                    "[Fallback] Key …%s rate-limited on '%s' (attempt %d/%d, trying next key)",
                    api_key[-4:], agent_role, attempt + 1, max_retries,
                )
                continue

            if _is_transient_error(exc):
                tried_keys.add(api_key)
                transient_error_count += 1
                logger.warning(
                    "[Fallback] Key …%s transient-error on '%s' (attempt %d/%d, trying next key)",
                    api_key[-4:], agent_role, attempt + 1, max_retries,
                )
                continue

            # Non-retryable error — raise immediately
            raise

    # All retries exhausted
    raise last_error or RuntimeError(
        f"All API keys exhausted for {provider.value} (role: {agent_role})"
    )
