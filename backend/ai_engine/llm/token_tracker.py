"""
Token Tracker — tracks token usage across all LLM calls.

Provides a singleton ``token_tracker`` that records every LLM call's
token consumption, broken down by agent role.  Used by ``invoke_with_fallback``
via a LangChain callback handler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Token Usage
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class TokenUsage:
    """Token counts for a single LLM call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# Token Tracker
# ══════════════════════════════════════════════════════════════════════════════


class TokenTracker:
    """Tracks cumulative token usage across all LLM calls in a session.

    Usage::

        from ai_engine.llm import token_tracker

        # After each LLM call, pass the response:
        token_tracker.record("router", response)

        # Print summary:
        token_tracker.print_summary()
    """

    def __init__(self) -> None:
        self._calls: list[dict] = []
        self._by_role: dict[str, TokenUsage] = {}
        self._total = TokenUsage()

    def record_from_llm_output(self, role: str, llm_output: dict) -> None:
        """Extract token usage from LLMResult.llm_output and record it."""
        usage_dict = (llm_output or {}).get("token_usage") or {}
        if not usage_dict:
            return

        # Groq format: prompt_tokens, completion_tokens, total_tokens
        # Gemini format: prompt_token_count, candidates_token_count, total_token_count
        prompt = (
            usage_dict.get("prompt_tokens")
            if "prompt_tokens" in usage_dict
            else usage_dict.get("prompt_token_count", 0)
        )
        completion = (
            usage_dict.get("completion_tokens")
            if "completion_tokens" in usage_dict
            else usage_dict.get("candidates_token_count", 0)
        )
        total = (
            usage_dict.get("total_tokens")
            if "total_tokens" in usage_dict
            else usage_dict.get("total_token_count", 0)
        )

        if prompt == 0 and completion == 0:
            return

        usage = TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)
        self._record_usage(role, usage)

    def _record_usage(self, role: str, usage: TokenUsage) -> None:
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
        return self._total

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def print_summary(self) -> None:
        """Print a formatted summary of all token usage."""
        if not self._calls:
            print("\n[Tokens] No LLM calls recorded.")
            return

        print(f"\n{'='*55}")
        print(f"  Token Usage Summary ({len(self._calls)} LLM calls)")
        print(f"{'='*55}")
        print(f"  {'Role':<16} {'Prompt':>8} {'Complete':>8} {'Total':>8}")
        print(f"  {'-'*16} {'-'*8} {'-'*8} {'-'*8}")
        for role, usage in sorted(self._by_role.items()):
            print(
                f"  {role:<16} {usage.prompt_tokens:>8,} "
                f"{usage.completion_tokens:>8,} {usage.total_tokens:>8,}"
            )
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


# ══════════════════════════════════════════════════════════════════════════════
# LangChain callback that records token usage after every LLM call
# ══════════════════════════════════════════════════════════════════════════════


class _TokenTrackingCallback(BaseCallbackHandler):
    """LangChain callback that records token usage after every LLM call."""

    def __init__(self, role: str) -> None:
        self.role = role

    def on_llm_end(self, response, **kwargs) -> None:
        # Log response structure for debugging
        logger.debug(
            "[TokenTracker] Response type: %s, attributes: %s",
            type(response).__name__,
            [attr for attr in dir(response) if not attr.startswith('_')]
        )
        
        # Try multiple paths to find token usage data
        llm_output = getattr(response, "llm_output", None) or {}
        logger.debug("[TokenTracker] llm_output: %s", llm_output)
        
        # If llm_output is empty, try response metadata
        if not llm_output or not llm_output.get("token_usage"):
            response_metadata = getattr(response, "response_metadata", {}) or {}
            logger.debug("[TokenTracker] response_metadata: %s", response_metadata)
            if response_metadata.get("token_usage"):
                llm_output = response_metadata
        
        # Also try direct token_usage attribute on response
        if not llm_output or not llm_output.get("token_usage"):
            direct_usage = getattr(response, "token_usage", None)
            logger.debug("[TokenTracker] direct token_usage: %s", direct_usage)
            if direct_usage:
                llm_output = {"token_usage": direct_usage}
        
        # Try to get usage from generations (LangChain v0.1+ format)
        if not llm_output or not llm_output.get("token_usage"):
            generations = getattr(response, "generations", None)
            logger.debug("[TokenTracker] generations: %s", generations)
            if generations and generations:
                # Check first generation's generation_info
                gen_info = getattr(generations[0][0], "generation_info", None) if generations[0] else None
                logger.debug("[TokenTracker] generation_info: %s", gen_info)
                if gen_info and gen_info.get("token_usage"):
                    llm_output = {"token_usage": gen_info["token_usage"]}
        
        # Try usage_metadata (newer LangChain versions)
        if not llm_output or not llm_output.get("token_usage"):
            usage_metadata = getattr(response, "usage_metadata", None)
            logger.debug("[TokenTracker] usage_metadata: %s", usage_metadata)
            if usage_metadata:
                llm_output = {"token_usage": usage_metadata}
        
        # Try response_metadata['token_usage'] directly
        if not llm_output or not llm_output.get("token_usage"):
            resp_meta = getattr(response, "response_metadata", None)
            if resp_meta:
                logger.debug("[TokenTracker] response_metadata full: %s", resp_meta)
        
        # Debug logging if still no token usage found
        if not llm_output or not llm_output.get("token_usage"):
            logger.warning(
                "[TokenTracker] No token_usage found in response for role=%s. "
                "Checked: llm_output, response_metadata, token_usage, generations, usage_metadata",
                self.role
            )
        
        token_tracker.record_from_llm_output(self.role, llm_output)


# ── Singleton token tracker ──────────────────────────────────────────────────

token_tracker = TokenTracker()
