"""
Ranking Agent — Stage 3 of the multi-agent pipeline.

Responsibilities:
1. Score each candidate with a multi-signal formula:
   - Popularity (0.35)
   - User preference match via **semantic embeddings** (0.25)
   - Proximity to city center (0.15)
   - Rating quality (0.15)
   - Diversity bonus (0.10)
2. Optimize for category diversity in the final set.
3. Cap the candidate list to 15–30 places (the optimal range for LLM reasoning).

Semantic embedding scoring (`_score_preference`):
   The user's preferences are converted into a natural-language query and
   embedded via gemini-embedding-2 (1 API call per pipeline run).  Each
   place is scored by cosine similarity against that query vector, replacing
   the old fragile keyword‑matching approach.

   Places without a stored embedding fall back to a mild default score
   (0.3) so they aren't completely excluded.
"""

import logging
from typing import Optional
from ai_engine.graph.state import TripState
from ai_engine.tools.haversine import haversine
from ai_engine.services.embedding_service import (
    build_query_text,
    embed_query,
    cosine_similarity,
    load_place_embeddings,
)

logger = logging.getLogger(__name__)

# ── Scoring weights ──────────────────────────────────────────────────────────

WEIGHT_POPULARITY  = 0.35
WEIGHT_PREFERENCE  = 0.25
WEIGHT_PROXIMITY   = 0.15
WEIGHT_RATING      = 0.15
WEIGHT_DIVERSITY   = 0.10

# ── Candidate caps ───────────────────────────────────────────────────────────

MAX_TOTAL_CANDIDATES = 40

# ── Embedding fallback ───────────────────────────────────────────────────────

# Score assigned to places that don't have a stored embedding
# (mild default — they still rely on popularity / rating / proximity).
FALLBACK_EMBEDDING_SCORE = 0.3


# ── Scoring helpers ──────────────────────────────────────────────────────────


def _score_popularity(place: dict) -> float:
    """Normalize popularity score to 0–1 range."""
    pop = place.get("popularity_score", 0) or 0
    return min(pop / 100.0, 1.0)


def _score_preference_embedding(
    place: dict,
    query_vector: list[float] | None,
    place_vectors: dict[str, list[float]],
) -> float:
    """
    Score a place by cosine similarity between the user query and place embedding.

    Args:
        place:         Place dict (from ``filtered_places``).
        query_vector:  Embedded user-preference query (or ``None`` if
                       embedding failed).
        place_vectors: Mapping of ``place_id → embedding_vector`` loaded
                       from the database.

    Returns:
        Score in [0, 1].
    """
    # No query vector → cannot compute similarity → fallback
    if query_vector is None:
        return FALLBACK_EMBEDDING_SCORE

    place_id = place.get("id", "")
    place_vec = place_vectors.get(place_id)

    # No stored embedding for this place → fallback
    if place_vec is None:
        return FALLBACK_EMBEDDING_SCORE

    # Cosine similarity is in [-1, 1]; we map to [0, 1]
    sim = cosine_similarity(query_vector, place_vec)
    return max(0.0, (sim + 1.0) / 2.0)


def _score_proximity(
    place: dict,
    center_lat: float,
    center_lon: float,
) -> float:
    """
    Score proximity to city center.

    Closer places get higher scores. Hotels are exempt
    (users pick hotels by preference, not centrality).
    """
    if place.get("category") == "hotel":
        return 0.5  # Neutral score for hotels

    dist = haversine(center_lat, center_lon, place["lat"], place["lon"])

    if dist <= 5:
        return 1.0
    elif dist <= 10:
        return 0.8
    elif dist <= 20:
        return 0.5
    elif dist <= 35:
        return 0.3
    else:
        return max(0.0, 1.0 - (dist / 50.0))


def _score_rating(place: dict) -> float:
    """Normalize rating to 0–1 range."""
    rating = place.get("rating", 3.0) or 3.0
    return min(max((rating - 1.0) / 4.0, 0.0), 1.0)


def _compute_composite_score(
    place: dict,
    query_vector: list[float] | None,
    place_vectors: dict[str, list[float]],
    center_lat: float,
    center_lon: float,
    category_counts: dict,
    target_per_category: dict,
) -> float:
    """
    Compute the final composite score for a place.

    Formula:
        score = (popularity  × W1)
              + (preference  × W2)   ← now embedding-based
              + (proximity   × W3)
              + (rating      × W4)
              + (diversity   × W5)
    """
    pop = _score_popularity(place)
    pref = _score_preference_embedding(place, query_vector, place_vectors)
    prox = _score_proximity(place, center_lat, center_lon)
    rat = _score_rating(place)

    # Diversity bonus: boost underrepresented categories
    cat = place.get("category", "other")
    current_count = category_counts.get(cat, 0)
    target = target_per_category.get(cat, 3)
    if current_count < target:
        diversity = 1.0
    elif current_count < target + 2:
        diversity = 0.5
    else:
        diversity = 0.0

    composite = (
        pop * WEIGHT_POPULARITY
        + pref * WEIGHT_PREFERENCE
        + prox * WEIGHT_PROXIMITY
        + rat * WEIGHT_RATING
        + diversity * WEIGHT_DIVERSITY
    )

    return round(composite, 4)


def _diversity_optimize(
    scored_places: list[tuple[dict, float]],
    duration_days: int,
) -> list[dict]:
    """
    Select the final candidate set with diversity constraints.

    Strategy:
    1. Sort by composite score.
    2. Greedily pick top places, but cap per-category.
    3. Ensure at least 2 categories have multiple options for the LLM.
    """
    category_caps = {
        "attraction": min(duration_days * 4, 18),
        "restaurant": min(duration_days * 3, 12),
        "hotel":      min(duration_days + 2, 7),
        "_default":   5,
    }

    by_category: dict[str, list] = {}
    for place, score in scored_places:
        cat = place.get("category", "other")
        by_category.setdefault(cat, []).append((place, score))

    for cat in by_category:
        by_category[cat].sort(key=lambda x: x[1], reverse=True)

    selected = []
    for cat, items in by_category.items():
        cap = category_caps.get(cat, category_caps["_default"])
        selected.extend(items[:cap])

    selected.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in selected[:MAX_TOTAL_CANDIDATES]]


# ── Main entry point ─────────────────────────────────────────────────────────


async def run_ranking_agent(state: TripState) -> TripState:
    """
    Main Ranking Agent workflow.

    1. Take filtered places from the Retrieval Agent.
    2. Load stored embeddings for those places from the database.
    3. Embed the user's preferences as a single query vector
       (1 gemini-embedding-2 call per pipeline run).
    4. Score each place with the multi-signal formula
       (preference score now = embedding cosine similarity).
    5. Apply diversity optimization.
    6. Store the final candidate set in state for the Planning Agent.
    """
    filtered = state.get("filtered_places") or []
    preferences = state.get("extracted_preferences") or {}
    duration_days = state.get("duration_days", 3)

    if not filtered:
        state["candidate_places"] = []
        state["error"] = "No filtered places to rank"
        return state

    # ── 1. Load place embeddings from DB ──────────────────────────────────
    place_ids = [p.get("id", "") for p in filtered if p.get("id")]
    place_vectors = await load_place_embeddings(place_ids)
    embedded_count = len(place_vectors)
    logger.info(
        "[RankingAgent] Loaded %d/%d place embeddings from DB",
        embedded_count, len(place_ids),
    )

    # ── 2. Embed user preferences as a query vector ───────────────────────
    query_text = build_query_text(preferences)
    query_vector = embed_query(query_text)

    if query_vector is None:
        logger.warning(
            "[RankingAgent] Query embedding failed — all places will use "
            "fallback preference score (%.1f)",
            FALLBACK_EMBEDDING_SCORE,
        )

    # ── 3. Compute city center for proximity scoring ─────────────────────
    non_hotel = [p for p in filtered if p.get("category") != "hotel"]
    if non_hotel:
        center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)
        center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)
    else:
        center_lat, center_lon = 0.0, 0.0

    # ── 4. Target per category for diversity scoring ─────────────────────
    target_per_category = {
        "attraction": max(duration_days * 2, 4),
        "restaurant": max(duration_days, 3),
        "hotel":      max(duration_days // 2 + 1, 2),
    }

    # ── 5. Score every place ─────────────────────────────────────────────
    category_counts: dict[str, int] = {}
    scored = []
    for place in filtered:
        score = _compute_composite_score(
            place,
            query_vector,
            place_vectors,
            center_lat,
            center_lon,
            category_counts,
            target_per_category,
        )
        cat = place.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        scored.append((place, score))

    # ── 6. Diversity optimization ────────────────────────────────────────
    candidates = _diversity_optimize(scored, duration_days)

    state["candidate_places"] = candidates
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[RankingAgent] {len(filtered)} filtered → {len(candidates)} ranked "
           f"candidates (embeddings: {embedded_count}/{len(place_ids)})"]
    )

    return state
