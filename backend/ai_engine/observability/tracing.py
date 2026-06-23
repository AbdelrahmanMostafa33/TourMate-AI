"""
LangSmith Tracing for TourMate AI Agents.

Provides @traceable wrappers that automatically instrument every agent
with full input/output tracing in LangSmith when enabled.

When LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY are set, all
LangChain calls are automatically traced. This module adds explicit
@traceable decorators on the agent-level functions so the LangSmith
dashboard shows the full agent hierarchy:

    trip_pipeline (trace)
    ├── load_profile
    ├── retrieval_agent
    ├── ranking_agent
    ├── planning_agent
    │   └── invoke_with_fallback (planner LLM)
    ├── optimization_agent
    └── validation_agent
        └── invoke_with_fallback (validator LLM)

Additionally, every LLM call via `invoke_with_fallback` is already
traced by LangChain's automatic tracer when env vars are set.

Usage::

    # In any agent module:
    from ai_engine.observability import traced

    @traced(name="my_agent", metadata={"role": "planner"})
    async def run_my_agent(state):
        ...
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Check if tracing is enabled
# ══════════════════════════════════════════════════════════════════════════════

def get_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled via environment variables."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"


# ══════════════════════════════════════════════════════════════════════════════
# @traceable decorator — works whether langsmith is installed or not
# ══════════════════════════════════════════════════════════════════════════════

def traced(
    name: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list[str]] = None,
) -> Callable:
    """
    Decorator that instruments a function with LangSmith tracing.

    When LangSmith tracing is enabled (LANGCHAIN_TRACING_V2=true),
    the function's inputs and outputs are sent to the LangSmith dashboard.

    When tracing is disabled, the decorator is a pure pass-through with
    zero overhead.

    Args:
        name:      Display name in the LangSmith trace tree.
        metadata:  Key/value pairs attached to the run for filtering.
        tags:      Tags for grouping runs (e.g. ["agent", "planner"]).
    """

    def decorator(func: Callable) -> Callable:
        # Try to import langsmith's traceable; fall back to a no-op if missing
        try:
            from langsmith import traceable as _traceable

            return _traceable(
                name=name or func.__name__,
                metadata=metadata or {},
                tags=tags or [],
            )(func)

        except ImportError:
            # langsmith not installed — return the function unchanged
            logger.debug(
                "[Tracing] langsmith not installed, skipping trace for %s",
                name or func.__name__,
            )
            return func

    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# setup_langsmith — log LangSmith status at startup
# ══════════════════════════════════════════════════════════════════════════════

def setup_langsmith() -> None:
    """
    Log LangSmith tracing status at application startup.

    LangChain automatically reads LANGCHAIN_TRACING_V2, LANGCHAIN_API_KEY,
    and LANGCHAIN_PROJECT from environment variables. This function simply
    logs the status so operators know tracing is active.

    Add these to your .env file to enable tracing:
        LANGCHAIN_TRACING_V2=true
        LANGCHAIN_API_KEY=ls_...
        LANGCHAIN_PROJECT=tourmate-ai
    """
    enabled = os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
    api_key = os.environ.get("LANGCHAIN_API_KEY", "")
    project = os.environ.get("LANGCHAIN_PROJECT", "default")

    if enabled and api_key:
        logger.info(
            "[LangSmith] Tracing ENABLED — project: %s",
            project,
        )
    elif enabled and not api_key:
        logger.warning(
            "[LangSmith] LANGCHAIN_TRACING_V2=true but LANGCHAIN_API_KEY not set. "
            "Tracing will not work. Add LANGCHAIN_API_KEY to your .env."
        )
    else:
        logger.info("[LangSmith] Tracing disabled")
