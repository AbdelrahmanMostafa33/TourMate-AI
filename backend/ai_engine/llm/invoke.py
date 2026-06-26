"""
invoke_with_fallback — automatic retry across API keys with backoff.

Provides a single function ``invoke_with_fallback()`` that:
1. Gets the next available API key from ``KeyManager``
2. Builds the appropriate LLM instance
3. Calls the LLM with optional structured output
4. On rate-limit (429): tries the next key immediately
5. On transient error (503): applies exponential backoff, then retries
6. On request-too-large (413): raises immediately (cycling keys won't help)
7. On schema validation error (400): retries up to 2 times (LLM non-determinism often resolves it)
8. On any other error: raises immediately
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Type

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


# Maximum exponential backoff wall-clock delay for transient errors (503 etc.)
_MAX_TRANSIENT_BACKOFF = 5.0  # seconds
# Base backoff before exponential growth
_BASE_TRANSIENT_BACKOFF = 1.0  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# Error classification helpers
# ══════════════════════════════════════════════════════════════════════════════


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check whether an exception is a rate-limit (429) error.

    Also catches Google Gemini's 403 PERMISSION_DENIED errors which
    are returned instead of 429 when the project exceeds its quota.
    """
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "429", "rate limit", "ratelimit", "requests per",
            "tokens per", "quota", "too many requests",
            "403", "permission_denied", "denied access",
        )
    )


def _is_transient_error(exc: Exception) -> bool:
    """Check whether an exception is a transient server error (503, unavailable)."""
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "503", "unavailable", "service unavailable",
            "high demand", "temporarily unavailable",
            "server error", "internal server error",
            "overloaded", "try again later",
        )
    )


def _is_request_too_large_error(exc: Exception) -> bool:
    """Check whether an exception is a 413 Request Entity Too Large error.

    This happens when the prompt exceeds the provider's per-request token
    limit.  Cycling keys will NOT fix this — we raise immediately so the
    caller can retry with a downsized payload.
    """
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "413", "request too large", "payload too large",
            "entity too large", "reduce your message size",
        )
    )


def _is_schema_validation_error(exc: Exception) -> bool:
    """Check whether an exception is a 400 schema/tool call validation error.

    This happens when the LLM returns structured output that doesn't match
    the Pydantic schema (e.g. expected string but got array). Retrying
    the same prompt often resolves this due to LLM non-determinism.
    """
    msg = str(exc).lower()
    return any(
        kw in msg
        for kw in (
            "tool call validation failed",
            "did not match schema",
            "tool_use_failed",
            "invalid_request_error",
        )
    )


# Maximum schema validation retries before giving up
_MAX_SCHEMA_RETRIES = 2


# ══════════════════════════════════════════════════════════════════════════════
# invoke_with_fallback
# ══════════════════════════════════════════════════════════════════════════════


async def invoke_with_fallback(
    agent_role: str,
    messages: list[BaseMessage],
    max_retries: int | None = None,
    structured_output: type | None = None,
    on_retry: Callable[[int, int, str], Awaitable[None]] | None = None,
) -> Any:
    """Invoke the LLM for *agent_role* with automatic key rotation and retry.

    Args:
        agent_role:       Role name from ``AGENT_LLM_REGISTRY``.
        messages:         LangChain message list.
        max_retries:      Maximum number of attempts.  Defaults to ``total_keys * 2``.
        structured_output: Optional Pydantic model class for structured output.
        on_retry:         Optional async callback ``(attempt, max_retries, reason)``.

    Returns:
        The LLM response object (same as ``BaseChatModel.ainvoke``).

    Raises:
        The last error if all retries are exhausted.
    """
    from ai_engine.llm.config import AGENT_LLM_REGISTRY, _PROVIDER_BUILDERS, get_config_for_agent
    from ai_engine.llm.key_manager import key_manager
    from ai_engine.llm.token_tracker import _TokenTrackingCallback

    config = AGENT_LLM_REGISTRY.get(agent_role)
    if config is None:
        available = ", ".join(sorted(AGENT_LLM_REGISTRY))
        raise ValueError(
            f"Unknown agent role '{agent_role}'. "
            f"Available roles: {available}"
        )

    provider = config.provider
    total_keys = key_manager.get_total_count(provider)

    # Default: one full pass through all keys (minimum 4 attempts)
    if max_retries is None:
        max_retries = max(total_keys, 4)

    last_error: Exception | None = None
    tried_keys: set[str] = set()
    transient_error_count = 0
    schema_retry_count = 0

    for attempt in range(max_retries):
        api_key = key_manager.get_key(provider)
        if api_key is None:
            logger.warning(
                "[Fallback] No available keys for %s on role '%s' — stopping",
                provider.value, agent_role,
            )
            break

        if api_key in tried_keys:
            if len(tried_keys) >= total_keys:
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
                    tried_keys.clear()
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

            # 413 Request Too Large — prompt exceeds token limit
            if _is_request_too_large_error(exc):
                logger.error(
                    "[Fallback] Key …%s request too large on '%s' — "
                    "prompt exceeds token limit. Raising immediately.",
                    api_key[-4:], agent_role,
                )
                raise

            # 429 Rate Limit — try next key
            if _is_rate_limit_error(exc):
                tried_keys.add(api_key)
                logger.warning(
                    "[Fallback] Key …%s rate-limited on '%s' (attempt %d/%d, trying next key)",
                    api_key[-4:], agent_role, attempt + 1, max_retries,
                )
                if on_retry:
                    await on_retry(attempt + 1, max_retries, "Switching to next API key")
                continue

            # 503 / Transient — try next key with backoff
            if _is_transient_error(exc):
                tried_keys.add(api_key)
                transient_error_count += 1
                # Apply backoff before retrying
                backoff = min(
                    _BASE_TRANSIENT_BACKOFF * (2 ** (transient_error_count - 1)),
                    _MAX_TRANSIENT_BACKOFF,
                )
                logger.warning(
                    "[Fallback] Key …%s transient-error on '%s' (attempt %d/%d, waiting %.1fs before retry)",
                    api_key[-4:], agent_role, attempt + 1, max_retries, backoff,
                )
                if on_retry:
                    await on_retry(attempt + 1, max_retries, f"Server busy, waiting {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                continue

            # 400 Schema/Tool Call Validation Error — retry with same key
            # LLM non-determinism often resolves this on the next attempt
            if _is_schema_validation_error(exc):
                schema_retry_count += 1
                if schema_retry_count <= _MAX_SCHEMA_RETRIES:
                    logger.warning(
                        "[Fallback] Key …%s schema validation error on '%s' "
                        "(schema_retry %d/%d, retrying with same key)",
                        api_key[-4:], agent_role,
                        schema_retry_count, _MAX_SCHEMA_RETRIES,
                    )
                    if on_retry:
                        await on_retry(
                            schema_retry_count, _MAX_SCHEMA_RETRIES,
                            f"Schema validation error, retrying (attempt {schema_retry_count}/{_MAX_SCHEMA_RETRIES})..."
                        )
                    continue
                logger.error(
                    "[Fallback] Key …%s schema validation error on '%s' — "
                    "exhausted %d retries. Raising.",
                    api_key[-4:], agent_role, _MAX_SCHEMA_RETRIES,
                )
                raise

            # Non-retryable error — raise immediately
            raise

    raise last_error or RuntimeError(
        f"All API keys exhausted for {provider.value} (role: {agent_role})"
    )
