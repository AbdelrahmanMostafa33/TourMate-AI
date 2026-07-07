"""
Embedding Service — semantic similarity scoring for the ranking agent.

Provides:
    build_query_text()     Format user preferences as a gemini-embedding-2 query.
    embed_query()          One-shot embedding via gemini-embedding-2 (with key rotation).
    cosine_similarity()    Pure-numpy cosine similarity between two vectors.
    load_place_embeddings()  Batch-load embeddings from the database.

Uses gemini-embedding-2 (768-dim) via the google-genai SDK.
Place embeddings are pre-generated and stored as JSON arrays in the
``places.embedding`` column.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from google import genai
from google.genai import types
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session
from app.models.place import Place

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMS = 768

# ── Multi-key round-robin (for embed_query) ──────────────────────────────────

_embed_key_index = 0
_embed_keys: list[str] = []


def _init_embed_keys() -> None:
    global _embed_keys
    raw = settings.google_api_key
    _embed_keys = [k.strip() for k in raw.split(",") if k.strip()]


_init_embed_keys()


def _get_next_embed_key() -> str | None:
    global _embed_key_index
    if not _embed_keys:
        return None
    key = _embed_keys[_embed_key_index % len(_embed_keys)]
    _embed_key_index += 1
    return key


# ── Query Text Builder ───────────────────────────────────────────────────────


def build_query_text(preferences: dict) -> str:
    """
    Convert user preferences into a gemini-embedding-2 query string.

    Format follows the asymmetric retrieval convention:
        task: search result | query: <natural-language description>

    Args:
        preferences: The profile dict from TripState (or similar with
            interests, travel_style, food_preferences, etc.).

    Returns:
        A single string ready to pass to ``embed_query()``.
    """
    parts: list[str] = []

    interests = preferences.get("interests") or []
    travel_style = (preferences.get("travel_style") or "").strip()
    food_prefs = preferences.get("food_preferences") or []
    budget = (preferences.get("budget_level") or "").strip()
    pace = (preferences.get("pace") or "").strip()

    # Travel style + pace context
    style_parts = []
    if travel_style:
        style_parts.append(travel_style)
    if pace:
        style_parts.append(f"{pace} pace")
    if budget:
        style_parts.append(f"{budget} budget")
    if style_parts:
        parts.append(f"{' - '.join(style_parts)} trip")

    # Interests
    if interests:
        formatted = ", ".join(interests)
        parts.append(f"interested in {formatted}")

    # Food
    if food_prefs:
        formatted = ", ".join(food_prefs)
        parts.append(f"food: {formatted}")

    # Fallback if nothing was provided
    if not parts:
        parts.append("general sightseeing trip")

    query = ". ".join(parts)
    return f"task: search result | query: {query}"


# ── Embedding ────────────────────────────────────────────────────────────────


# ── Error classification helpers ──────────────────────────────────────────


#: Embedding error categories — used to provide actionable log messages.
_EMBED_ERROR_AUTH = "AUTH"            # 401 — bad / missing API key
_EMBED_ERROR_PERMISSION = "PERMISSION"  # 403 — quota exceeded / API not enabled
_EMBED_ERROR_RATE_LIMIT = "RATE_LIMIT"  # 429 — too many requests
_EMBED_ERROR_SERVER = "SERVER"          # 5xx — temporary API outage
_EMBED_ERROR_NETWORK = "NETWORK"        # ConnectionError, timeout
_EMBED_ERROR_UNKNOWN = "UNKNOWN"        # everything else

_EMBED_ADVICE: dict[str, str] = {
    _EMBED_ERROR_AUTH: (
        "Check that GOOGLE_API_KEY in .env is a valid Gemini API key "
        "(generated at https://aistudio.google.com/app/apikey)"
    ),
    _EMBED_ERROR_PERMISSION: (
        "The API key may have hit its quota or the Generative Language API "
        "may not be enabled in your Google Cloud project"
    ),
    _EMBED_ERROR_RATE_LIMIT: (
        "Rate-limited — consider adding more API keys to GOOGLE_API_KEY "
        "(comma-separated) for automatic rotation"
    ),
    _EMBED_ERROR_SERVER: (
        "Gemini API server temporarily unavailable — retry later"
    ),
    _EMBED_ERROR_NETWORK: (
        "Network error — check your internet connection or firewall settings"
    ),
    _EMBED_ERROR_UNKNOWN: (
        "Unexpected error — check the full traceback above"
    ),
}


OUTCOME_NO_KEY = "No API keys configured — set GOOGLE_API_KEY in .env"


def _classify_embed_error(exc: Exception) -> tuple[str, str]:
    """Classify an embedding error and return ``(category, readable_message)``.

    The category is one of ``_EMBED_ERROR_*`` constants.
    The message is a short human-readable label (e.g. ``"401 UNAUTHENTICATED"``).
    """
    msg = str(exc).lower()

    # Try to extract HTTP status code from google.genai.errors.ClientError
    status_code = getattr(exc, "code", None)
    if status_code is None:
        # Fallback: scan the error message for common codes
        for code in (401, 403, 429, 500, 502, 503):
            if str(code) in msg:
                status_code = code
                break

    if status_code == 401:
        return _EMBED_ERROR_AUTH, "401 UNAUTHENTICATED"
    if status_code == 403:
        return _EMBED_ERROR_PERMISSION, "403 PERMISSION_DENIED"
    if status_code == 429 or "rate" in msg or "quota" in msg:
        return _EMBED_ERROR_RATE_LIMIT, "429 RATE_LIMITED"
    if status_code and 500 <= status_code < 600:
        return _EMBED_ERROR_SERVER, f"{status_code} SERVER_ERROR"

    # Network-level errors (connection refused, timeout, DNS failure)
    if any(
        t in type(exc).__name__.lower()
        for t in ("connectionerror", "timeout", "connecterror")
    ):
        return _EMBED_ERROR_NETWORK, type(exc).__name__
    if any(kw in msg for kw in ("timed out", "connection refused", "dns", "resolve")):
        return _EMBED_ERROR_NETWORK, type(exc).__name__

    return _EMBED_ERROR_UNKNOWN, type(exc).__name__


# ── Embedding ──────────────────────────────────────────────────────────────


def embed_query(
    query_text: str,
) -> list[float] | None:
    """
    Embed a single query string using gemini-embedding-2 (synchronous).

    Rotates through configured API keys on failure.
    Prefer ``await embed_query_async()`` in async contexts.

    Args:
        query_text: Pre-formatted text with the ``task: search result | query: ...`` prefix.

    Returns:
        768-dimensional vector as a Python list, or **None** on failure.
    """
    vectors = _embed_multi([query_text])
    return vectors[0] if vectors else None


def _embed_multi(texts: list[str]) -> list[list[float] | None]:
    """Internal: embed 1+ texts with key rotation (synchronous)."""
    if not _embed_keys or not texts:
        logger.warning("[EmbedService] %s", OUTCOME_NO_KEY)
        return [None] * len(texts)

    last_error = None
    last_category = _EMBED_ERROR_UNKNOWN
    for _ in range(len(_embed_keys)):
        key = _get_next_embed_key()
        if not key:
            break
        client = None
        try:
            client = genai.Client(api_key=key)
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMS,
                ),
            )
            return [e.values for e in result.embeddings]
        except Exception as exc:
            last_error = exc
            category, label = _classify_embed_error(exc)
            last_category = category
            logger.warning(
                "[EmbedService] Key ...%s %s — %s",
                key[-4:], label, str(exc).splitlines()[0][:120],
            )
            continue
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass  # Suppress cleanup errors

    # Final summary with actionable advice
    advice = _EMBED_ADVICE.get(last_category, _EMBED_ADVICE[_EMBED_ERROR_UNKNOWN])
    logger.warning(
        "[EmbedService] Exhausted all %d API key(s) — last error: %s. %s",
        len(_embed_keys), last_error or "unknown", advice,
    )
    return [None] * len(texts)


async def embed_query_async(
    query_text: str,
) -> list[float] | None:
    """
    Embed a single query string using gemini-embedding-2 (async).

    Uses ``genai.AsyncClient`` so it does NOT block the event loop.
    Rotates through configured API keys on failure.

    Args:
        query_text: Pre-formatted text with the ``task: search result | query: ...`` prefix.

    Returns:
        768-dimensional vector as a Python list, or **None** on failure.
    """
    vectors = await _embed_multi_async([query_text])
    return vectors[0] if vectors else None


async def _embed_multi_async(texts: list[str]) -> list[list[float] | None]:
    """Internal: embed 1+ texts with key rotation using ``genai.AsyncClient``.

    Each API call creates a fresh client and tears it down via ``aclose()``
    to prevent "Task exception was never retrieved" warnings from lingering
    async client connections.
    """
    if not _embed_keys or not texts:
        logger.warning("[EmbedService] %s", OUTCOME_NO_KEY)
        return [None] * len(texts)

    last_error = None
    last_category = _EMBED_ERROR_UNKNOWN
    for _ in range(len(_embed_keys)):
        key = _get_next_embed_key()
        if not key:
            break
        client = None
        try:
            client = genai.Client(api_key=key)
            result = await client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMS,
                ),
            )
            return [e.values for e in result.embeddings]
        except Exception as exc:
            last_error = exc
            category, label = _classify_embed_error(exc)
            last_category = category
            logger.warning(
                "[EmbedService] Key ...%s %s — %s",
                key[-4:], label, str(exc).splitlines()[0][:120],
            )
            continue
        finally:
            if client is not None:
                try:
                    await client.aio.aclose()
                except Exception:
                    pass  # Suppress cleanup errors (e.g. connection already gone)

    # Final summary with actionable advice
    advice = _EMBED_ADVICE.get(last_category, _EMBED_ADVICE[_EMBED_ERROR_UNKNOWN])
    logger.warning(
        "[EmbedService] Exhausted all %d API key(s) — last error: %s. %s",
        len(_embed_keys), last_error or "unknown", advice,
    )
    return [None] * len(texts)


# ── Similarity ───────────────────────────────────────────────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two vectors.

    Returns a value between -1.0 and 1.0 (1.0 = identical direction).
    Returns 0.0 if either vector is empty or zero-magnitude.
    """
    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
    if a_arr.size == 0 or b_arr.size == 0:
        logger.debug("[EmbedService] cosine_similarity called with empty vector")
        return 0.0
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ── Database Loading ─────────────────────────────────────────────────────────


async def load_place_embeddings(
    place_ids: list[str],
) -> dict[str, list[float]]:
    """
    Batch-load embedding vectors for a list of place IDs.

    Only places that have a non-null ``embedding`` column are returned,
    so the result dict may be smaller than the input list.

    Args:
        place_ids: Place identifiers to look up.

    Returns:
        Mapping of ``place_id → embedding_vector`` for every place that has
        an embedding stored in the database.
    """
    if not place_ids:
        return {}

    try:
        async with async_session() as session:
            stmt = (
                select(Place.place_id, Place.embedding)
                .where(Place.place_id.in_(place_ids))
                .where(Place.embedding.isnot(None))
            )
            result = await session.execute(stmt)
            rows = result.all()
        return {row.place_id: list(row.embedding) for row in rows}
    except Exception as exc:
        logger.error("[EmbedService] Failed to load embeddings: %s", exc)
        return {}
