"""
Progress reporting mechanism for the LangGraph pipeline.

Uses a module-level dict of ``asyncio.Queue`` instances, keyed by
session_id, so that graph nodes can report progress events that are
consumed concurrently by ``handle_chat_stream`` and forwarded to the
Flutter client via WebSocket.

Usage (in a graph node)::

    from ai_engine.graph.progress import report_progress

    queue_key = state.get("progress_queue_key")
    if queue_key:
        await report_progress(queue_key, "PlaceRetriever", "running",
                              "Searching for places in Cairo...")
        # ... do work ...
        await report_progress(queue_key, "PlaceRetriever", "done",
                              "Found 45 places")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level progress queues keyed by session_id.
# Each entry maps to an asyncio.Queue of progress dicts.
_progress_queues: dict[str, asyncio.Queue] = {}


def get_progress_queue(session_id: str) -> asyncio.Queue:
    """Return (and lazily create) the progress queue for *session_id*."""
    if session_id not in _progress_queues:
        _progress_queues[session_id] = asyncio.Queue()
    return _progress_queues[session_id]


def remove_progress_queue(session_id: str) -> None:
    """Remove the progress queue for *session_id* when the pipeline finishes."""
    _progress_queues.pop(session_id, None)


async def report_progress(
    session_id: str,
    agent: str,
    status: str,
    message: str = "",
) -> None:
    """Push a progress event to the session's queue.

    Args:
        session_id: The Redis session ID (used as the queue key).
        agent:      Short agent name, e.g. ``"PlaceRetriever"``.
        status:     ``"running"`` | ``"done"`` | ``"error"``.
        message:    Human-readable status message for the UI.
    """
    queue = _progress_queues.get(session_id)
    if queue is None:
        return
    try:
        await queue.put(
            {
                "agent": agent,
                "status": status,
                "message": message,
            }
        )
    except Exception:
        logger.warning(
            "[Progress] Failed to report progress for %s: queue full/closed", session_id
        )
