"""
Agent Metrics — Performance tracking across AI agent pipeline calls.

Tracks operational metrics per agent:
    - **Calls**: number of invocations per agent role
    - **Latency**: min, max, avg, and p95/p99 response times
    - **Errors**: error count and error rate
    - **Token usage**: prompt + completion + total tokens for LLM-based agents

Token data is sourced from the existing ``ai_engine.llm.token_tracker``
singleton.  Latency, calls, and errors are tracked independently in this
module.

Usage::

    # Context manager (preferred for async functions):
    from ai_engine.evaluation.agent_metrics import agent_metrics

    async def my_node(state):
        with agent_metrics.track("planner"):
            return await run_planning_agent(state)

    # Decorator (synchronous + async):
    @agent_metrics.decorator("planner")
    async def my_node(state):
        ...

    # Report summary at end of pipeline:
    summary = agent_metrics.get_summary()
    # {
    #     "planner": {
    #         "calls": 2,
    #         "errors": 0,
    #         "error_rate": 0.0,
    #         "latency_ms": {"min": 320.5, "max": 410.2, "avg": 365.3, "p95": 410.2, "p99": 410.2},
    #         "tokens": {"prompt": 450, "completion": 120, "total": 570},
    #     },
    #     "validator": {...},
    #     "total": {
    #         "calls": 6,
    #         "errors": 0,
    #         "error_rate": 0.0,
    #         "tokens": {"prompt": 1500, "completion": 400, "total": 1900},
    #         "duration_ms": 1240.5,
    #     },
    # }
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Iterator, Optional

from ai_engine.llm.token_tracker import token_tracker as _token_tracker

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Data Structures
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class AgentCallRecord:
    """A single recorded call to an agent."""
    agent_role: str
    duration: float
    error: bool = False
    error_message: str = ""


@dataclass
class AgentMetricsSnapshot:
    """Aggregated metrics snapshot for a single agent role."""
    calls: int = 0
    errors: int = 0
    durations_ms: list[float] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.errors / self.calls if self.calls > 0 else 0.0

    @property
    def min_duration_ms(self) -> float:
        return min(self.durations_ms) if self.durations_ms else 0.0

    @property
    def max_duration_ms(self) -> float:
        return max(self.durations_ms) if self.durations_ms else 0.0

    @property
    def avg_duration_ms(self) -> float:
        return sum(self.durations_ms) / len(self.durations_ms) if self.durations_ms else 0.0

    @property
    def p95_duration_ms(self) -> float:
        return _percentile(self.durations_ms, 95) if self.durations_ms else 0.0

    @property
    def p99_duration_ms(self) -> float:
        return _percentile(self.durations_ms, 99) if self.durations_ms else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _percentile(sorted_values: list[float], percentile: int) -> float:
    """Compute the *percentile*th percentile from a sorted list."""
    if not sorted_values:
        return 0.0
    sorted_vals = sorted(sorted_values)
    k = (len(sorted_vals) - 1) * percentile / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


# ══════════════════════════════════════════════════════════════════════════════
# Agent Metrics Collector
# ══════════════════════════════════════════════════════════════════════════════


class AgentMetricsCollector:
    """
    Collects and aggregates operational metrics per agent role.

    This collector is designed to be used alongside the existing
    ``ai_engine.llm.token_tracker`` for token data and ``@traced``
    for trace hierarchy.  It provides a lightweight latency/error/call
    counter that can be queried at any point.

    Usage::

        collector = AgentMetricsCollector()

        with collector.track("planner"):
            await run_planning_agent(state)

        report = collector.get_summary()
    """

    def __init__(self) -> None:
        self._records: dict[str, AgentMetricsSnapshot] = {}

    # ── Recording ───────────────────────────────────────────────────────────

    def record_call(
        self,
        agent_role: str,
        duration: float,
        error: bool = False,
        error_message: str = "",
    ) -> None:
        """
        Record an agent call.

        Args:
            agent_role: The agent role name (e.g. ``"planner"``, ``"validator"``).
            duration:   Wall-clock duration in **seconds** (stored as ms).
            error:      Whether the call resulted in an error.
            error_message: Optional error description.
        """
        snap = self._records.setdefault(agent_role, AgentMetricsSnapshot())
        snap.calls += 1
        # Store as ms with microsecond precision (no rounding at storage time)
        snap.durations_ms.append(duration * 1000)
        if error:
            snap.errors += 1
            logger.warning(
                "[AgentMetrics] %s call #%d failed (%.2f ms): %s",
                agent_role, snap.calls, duration * 1000, error_message[:120],
            )

    # ── Context Manager ─────────────────────────────────────────────────────

    @contextlib.contextmanager
    def track(
        self,
        agent_role: str,
    ) -> Iterator[None]:
        """
        Context manager that times an agent call and records latency + errors.

        Usage::

            with agent_metrics.track("planner"):
                await run_planning_agent(state)
        """
        start = time.perf_counter()
        try:
            yield
        except BaseException as exc:
            duration = time.perf_counter() - start
            self.record_call(
                agent_role, duration,
                error=True,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            duration = time.perf_counter() - start
            self.record_call(agent_role, duration)

    # ── Async Context Manager ───────────────────────────────────────────────

    @contextlib.asynccontextmanager
    async def track_async(
        self,
        agent_role: str,
    ) -> AsyncIterator[None]:
        """
        Async context manager that times an agent call.

        Usage::

            async with agent_metrics.track_async("planner"):
                result = await run_planning_agent(state)
        """
        start = time.perf_counter()
        try:
            yield
        except BaseException as exc:
            duration = time.perf_counter() - start
            self.record_call(
                agent_role, duration,
                error=True,
                error_message=f"{type(exc).__name__}: {exc}",
            )
            raise
        else:
            duration = time.perf_counter() - start
            self.record_call(agent_role, duration)

    # ── Decorator (sync + async) ────────────────────────────────────────────

    def decorator(self, agent_role: str) -> Callable:
        """
        Decorator that wraps a function with agent timing.

        Works with both synchronous and asynchronous functions.

        Usage::

            @agent_metrics.decorator("planner")
            async def planning_node(state):
                ...

            @agent_metrics.decorator("profile_loader")
            def load_profile(state):
                ...
        """
        def _decorator(func: Callable) -> Callable:
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                    async with self.track_async(agent_role):
                        return await func(*args, **kwargs)
                return _async_wrapper
            else:

                @functools.wraps(func)
                def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                    with self.track(agent_role):
                        return func(*args, **kwargs)
                return _sync_wrapper

        return _decorator

    # ── Snapshot / Query ────────────────────────────────────────────────────

    def get_snapshot(self, agent_role: str) -> Optional[AgentMetricsSnapshot]:
        """Return the metrics snapshot for a single agent role, or None."""
        return self._records.get(agent_role)

    def get_all_snapshots(self) -> dict[str, AgentMetricsSnapshot]:
        """Return all per-agent snapshots (shallow copy)."""
        return dict(self._records)

    # ── Summary Report ──────────────────────────────────────────────────────

    def get_summary(self) -> dict[str, dict[str, Any]]:
        """
        Build a comprehensive summary of all agent metrics.

        Merges this collector's latency/error/call data with the
        ``TokenTracker``'s per-role token data.

        Returns:
            A dict keyed by agent role name, plus a ``"total"`` key::

                {
                    "planner": {
                        "calls": 2,
                        "errors": 0,
                        "error_rate": 0.0,
                        "latency_ms": {
                            "min": 320.5,
                            "max": 410.2,
                            "avg": 365.3,
                            "p95": 410.2,
                            "p99": 410.2,
                        },
                        "tokens": {
                            "prompt": 450,
                            "completion": 120,
                            "total": 570,
                        },
                    },
                    "total": {
                        "calls": 6,
                        "errors": 0,
                        "error_rate": 0.0,
                        "tokens": {"prompt": 1500, "completion": 400, "total": 1900},
                        "duration_ms": 1240.5,
                    },
                }
        """
        # Collect per-role token data from the token tracker
        # TokenTracker stores per-role aggregates via _by_role dict of TokenUsage
        # Access via internal attribute since the public API only exposes .total and .call_count
        token_data: dict[str, dict[str, int]] = {}
        try:
            by_role = _token_tracker._by_role  # type: ignore[attr-defined]
            for role, usage in by_role.items():
                token_data[role] = {
                    "prompt": usage.prompt_tokens,
                    "completion": usage.completion_tokens,
                    "total": usage.total_tokens,
                }
        except AttributeError:
            # If TokenTracker's internals change, fall back gracefully
            logger.debug("[AgentMetrics] Could not read token tracker by_role data")

        result: dict[str, dict[str, Any]] = {}
        total_calls = 0
        total_errors = 0
        total_duration = 0.0
        total_tokens_prompt = 0
        total_tokens_completion = 0
        total_tokens = 0

        for role, snap in self._records.items():
            total_calls += snap.calls
            total_errors += snap.errors
            total_duration += snap.avg_duration_ms * snap.calls

            # Ensure tokens dict always has all keys
            role_tokens = {
                "prompt": 0,
                "completion": 0,
                "total": 0,
            }
            if role in token_data:
                role_tokens["prompt"] = token_data[role].get("prompt", 0)
                role_tokens["completion"] = token_data[role].get("completion", 0)
                role_tokens["total"] = token_data[role].get("total", 0)

            total_tokens_prompt += role_tokens["prompt"]
            total_tokens_completion += role_tokens["completion"]
            total_tokens += role_tokens["total"]

            result[role] = {
                "calls": snap.calls,
                "errors": snap.errors,
                "error_rate": round(snap.error_rate, 4),
                "latency_ms": {
                    "min": round(snap.min_duration_ms, 2),
                    "max": round(snap.max_duration_ms, 2),
                    "avg": round(snap.avg_duration_ms, 2),
                    "p95": round(snap.p95_duration_ms, 2),
                    "p99": round(snap.p99_duration_ms, 2),
                },
                "tokens": role_tokens,
            }

        # Add total row
        result["total"] = {
            "calls": total_calls,
            "errors": total_errors,
            "error_rate": round(total_errors / total_calls, 4) if total_calls > 0 else 0.0,
            "tokens": {
                "prompt": total_tokens_prompt,
                "completion": total_tokens_completion,
                "total": total_tokens,
            },
            "duration_ms": round(total_duration, 2),
        }

        return result

    def print_summary(self) -> None:
        """Print a formatted summary table to stdout."""
        summary = self.get_summary()
        if not summary or len(summary) <= 1:
            print("\n[AgentMetrics] No agent calls recorded.")
            return

        print(f"\n{'='*80}")
        print(f"  Agent Pipeline Metrics")
        print(f"{'='*80}")
        print(f"  {'Agent':<18} {'Calls':>6} {'Err%':>6} {'Avg(ms)':>8} "
              f"{'P95(ms)':>8} {'Prompt':>8} {'Comp':>8} {'Total Tok':>10}")
        print(f"  {'-'*18} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

        # Print agent roles in sorted order, then "TOTAL" at the bottom
        agent_roles = sorted(k for k in summary if k != "total")
        for role in agent_roles:
            row = summary[role]
            print(
                f"  {role:<18} "
                f"{row['calls']:>6} "
                f"{row['error_rate'] * 100:>5.1f}% "
                f"{row.get('latency_ms', {}).get('avg', 0):>8.1f} "
                f"{row.get('latency_ms', {}).get('p95', 0):>8.1f} "
                f"{row['tokens'].get('prompt', 0):>8,} "
                f"{row['tokens'].get('completion', 0):>8,} "
                f"{row['tokens'].get('total', 0):>10,}"
            )

        # Print total at the bottom with a separator
        if "total" in summary:
            print(f"  {'-'*18} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
            row = summary["total"]
            print(
                f"  {'TOTAL':<18} "
                f"{row['calls']:>6} "
                f"{row['error_rate'] * 100:>5.1f}% "
                f"{row.get('duration_ms', 0):>8.1f} "
                f"{'':>8} "  # no p95 for total
                f"{row.get('tokens', {}).get('prompt', 0):>8,} "
                f"{row.get('tokens', {}).get('completion', 0):>8,} "
                f"{row.get('tokens', {}).get('total', 0):>10,}"
            )

        print(f"{'='*80}\n")

    # ── Reset ───────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear all recorded metrics (does NOT reset token_tracker)."""
        self._records.clear()


# ── Singleton collector ──────────────────────────────────────────────────────

agent_metrics = AgentMetricsCollector()
