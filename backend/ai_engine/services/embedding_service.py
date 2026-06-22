"""
Embedding Service — semantic similarity scoring for the ranking agent.

Provides:
    build_query_text()     Format user preferences as a gemini-embedding-2 query.
    embed_query()          One-shot embedding via gemini-embedding-2 (with key rotation).
    cosine_similarity()    Pure-numpy cosine similarity between two vectors.
    load_place_embeddings()  Batch-load embeddings from the database.

Uses gemini-embedding-2 (768-dim) via the google-genai SDK.
Place embeddings are pre-generated (see scripts/generate_embeddings.py) and
stored as JSON arrays in the ``places.embedding`` column.
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
    Convert extracted user preferences into a gemini-embedding-2 query string.

    Format follows the asymmetric retrieval convention:
        task: search result | query: <natural-language description>

    Args:
        preferences: The ``extracted_preferences`` dict from TripState.

    Returns:
        A single string ready to pass to ``embed_query()``.
    """
    parts: list[str] = []

    interests = preferences.get("interests_from_conversation") or []
    travel_style = (preferences.get("travel_style") or "").strip()
    food_prefs = preferences.get("food_preferences") or []
    accommodation = (preferences.get("accommodation_style") or "").strip()
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

    # Accommodation
    if accommodation:
        parts.append(f"accommodation: {accommodation}")

    # Fallback if nothing was provided
    if not parts:
        parts.append("general sightseeing trip")

    query = ". ".join(parts)
    return f"task: search result | query: {query}"


# ── Embedding ────────────────────────────────────────────────────────────────


def embed_query(
    query_text: str,
) -> list[float] | None:
    """
    Embed a single query string using gemini-embedding-2.

    Rotates through configured API keys on failure.

    Args:
        query_text: Pre-formatted text with the ``task: search result | query: ...`` prefix.

    Returns:
        768-dimensional vector as a Python list, or **None** on failure.
    """
    if not _embed_keys:
        logger.warning("[EmbedService] No Gemini API key configured")
        return None

    last_error = None
    for _ in range(len(_embed_keys)):
        key = _get_next_embed_key()
        if not key:
            break
        try:
            client = genai.Client(api_key=key)
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query_text,
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIMS,
                ),
            )
            return result.embeddings[0].values
        except Exception as exc:
            last_error = exc
            logger.warning("[EmbedService] Key ...%s failed: %s", key[-4:], exc)
            continue

    logger.warning("[EmbedService] All keys failed: %s", last_error)
    return None


# ── Similarity ───────────────────────────────────────────────────────────────


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two vectors.

    Returns a value between -1.0 and 1.0 (1.0 = identical direction).
    Returns 0.0 if either vector is zero-magnitude.
    """
    a_arr = np.array(a, dtype=np.float64)
    b_arr = np.array(b, dtype=np.float64)
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
