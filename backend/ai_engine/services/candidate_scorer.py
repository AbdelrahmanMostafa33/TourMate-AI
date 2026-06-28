"""
Candidate Scorer — Stage 3 of the multi-agent pipeline.

Responsibilities:
1. Score each candidate with a multi-signal formula:
   - Popularity (0.35)
   - User preference match via **semantic embeddings** (0.25)
   - Proximity to city center (0.15)
   - Rating quality (0.15)
   - Diversity bonus (0.10)
2. Optimize for category diversity in the final set.
3. Cap the candidate list to 15–30 places.

Semantic embedding scoring:
   The user's preferences are converted into a natural-language query and
   embedded via gemini-embedding-2 (1 API call per pipeline run).  Each
   place is scored by cosine similarity against that query vector.
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

from ai_engine.constants import MAX_TOTAL_CANDIDATES

# ── Embedding fallback ───────────────────────────────────────────────────────

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
    """Score a place by cosine similarity between the user query and place embedding."""
    if query_vector is None:
        return FALLBACK_EMBEDDING_SCORE
    place_id = place.get("id", "")
    place_vec = place_vectors.get(place_id)
    if place_vec is None:
        return FALLBACK_EMBEDDING_SCORE
    sim = cosine_similarity(query_vector, place_vec)
    return max(0.0, (sim + 1.0) / 2.0)


def _score_proximity(
    place: dict,
    center_lat: float,
    center_lon: float,
) -> float:
    """Score proximity to city center."""
    if place.get("category") == "hotel":
        return 0.5
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
    """Compute the final composite score for a place."""
    pop = _score_popularity(place)
    pref = _score_preference_embedding(place, query_vector, place_vectors)
    prox = _score_proximity(place, center_lat, center_lon)
    rat = _score_rating(place)

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


# ── Semantic interest-to-subcategory matching ───────────────────────────────
#
# Instead of exact keyword mapping (which misses "night" → "nightlife"),
# we use a single lightweight LLM call (via the `router` role — Groq, fast)
# to semantically match the user's interests against the available place
# subcategories.
#
# This naturally handles:
#   - "night" → "nightlife" (semantically related)
#   - "partying" → "nightlife", "entertainment" (related concepts)
#   - "urban exploration" → "history", "sightseeing" (semantic overlap)

_SEMANTIC_MATCH_SYSTEM_PROMPT = """You are a semantic router for a travel planning system.
Your job: given a list of USER INTERESTS and a list of PLACE SUBCATEGORIES,
output ONLY the subcategories that are semantically related to the user's interests.

Rules:
- Think about synonyms, related concepts, and semantic overlap.
- If the user says "night", match "nightlife".
- If the user says "partying", match "nightlife" and "entertainment".
- If the user says "urban exploration", match "history", "sightseeing", and "shopping".
- If the user says "desert", match "nature".
- If the user says "culture", match "museums" and "history".
- If the user says "food" or "dining", match nothing (food is handled by restaurant category).

Respond with a comma-separated list of matching subcategory names ONLY.
No explanation, no markdown, no extra text. If nothing matches, output "NONE".
"""


async def _compute_semantic_interest_subcats(
    profile_interests: Optional[list[str]],
    subcategory_names: list[str],
) -> set[str]:
    """
    Use a single lightweight LLM call to semantically match user interests
    to available place subcategories.

    Args:
        profile_interests: List of user interest strings (e.g.
            ["nightlife", "food", "socializing"]).
        subcategory_names: List of available subcategory names from the
            place database (e.g. ["history", "museums", "nightlife", ...]).

    Returns:
        Set of subcategory names that semantically match the user's interests.
    """
    if not profile_interests or not subcategory_names:
        return set()

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from ai_engine.llm.invoke import invoke_with_fallback

        interests_str = ", ".join(profile_interests)
        subcats_str = ", ".join(sorted(subcategory_names))
        subcategory_names_set = {s.lower() for s in subcategory_names}

        messages = [
            SystemMessage(content=_SEMANTIC_MATCH_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"User interests: [{interests_str}]\n"
                    f"Available subcategories: [{subcats_str}]\n"
                    "Which subcategories match?"
                )
            ),
        ]

        response = await invoke_with_fallback(
            agent_role="router",
            messages=messages,
        )
        raw = response.content.strip() if hasattr(response, "content") else str(response).strip()

        if raw.upper() == "NONE" or not raw:
            return set()

        # Parse comma-separated list
        matched: set[str] = set()
        for part in raw.split(","):
            name = part.strip().lower()
            # Only include if it's an actual subcategory name
            if name in subcategory_names_set:
                matched.add(name)

        return matched
    except Exception as exc:
        logger.warning("[CandidateScorer] LLM semantic match failed: %s — falling back to empty set", exc)
        return set()


def _diversity_optimize(
    scored_places: list[tuple[dict, float]],
    duration_days: int,
    interest_subcats: Optional[set[str]] = None,
) -> list[dict]:
    """Select the final candidate set with diversity constraints.

    Ensures **category-level** diversity (attraction / restaurant / hotel)
    and **subcategory-level** diversity within attractions (history, museums,
    nightlife, parks, etc.), so the planner isn't starved of variety.

    Uses a **3-phase selection** for attractions:
    1. Interest-matching subcategories get 2 picks (semantic boost)
    2. Every other subcategory gets 1 pick (baseline diversity)
    3. Remaining slots filled via round-robin

    ``interest_subcats`` is pre-computed by ``_compute_semantic_interest_subcats``
    using a lightweight LLM call, so it naturally handles semantic variations
    like "night" → "nightlife" without exact keyword mapping.
    """
    if interest_subcats is None:
        interest_subcats = set()

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

    selected: list[tuple[dict, float]] = []

    for cat, items in by_category.items():
        cap = category_caps.get(cat, category_caps["_default"])

        if cat == "attraction":
            # ── Interest-weighted subcategory selection ─────────────
            # Guarantees:
            #   1. Interest-matching subcats → at least 2 picks each
            #   2. Other subcats           → at least 1 pick each
            #   3. Remaining slots         → filled by highest-score
            #
            # This ensures the planner gets enough candidates for every
            # user interest (e.g. multiple nightlife options to choose
            # from) without sacrificing category diversity.
            by_subcat: dict[str, list[tuple[dict, float]]] = {}
            for place, score in items:
                sub = (place.get("sub_category") or "").lower() or "other"
                by_subcat.setdefault(sub, []).append((place, score))

            subcat_names = sorted(by_subcat.keys())
            cat_selected: list[tuple[dict, float]] = []
            seen_ids: set[str] = set()
            # Track index within each subcategory's sorted list
            subcat_ptr: dict[str, int] = {s: 0 for s in subcat_names}

            def _pick_next(sub: str) -> bool:
                """Pick the next unseen place from a subcategory."""
                while subcat_ptr[sub] < len(by_subcat[sub]):
                    idx = subcat_ptr[sub]
                    place, score = by_subcat[sub][idx]
                    subcat_ptr[sub] = idx + 1
                    pid = place.get("id", "")
                    if pid not in seen_ids:
                        cat_selected.append((place, score))
                        seen_ids.add(pid)
                        return True
                return False

            # Phase 1: Interest-matching subcats get up to 2 picks
            for sub in subcat_names:
                if sub in interest_subcats and len(cat_selected) < cap:
                    _pick_next(sub)  # first pick
                    if len(cat_selected) < cap:
                        _pick_next(sub)  # second pick

            # Phase 2: Every OTHER subcategory gets up to 1 pick
            for sub in subcat_names:
                if sub not in interest_subcats and len(cat_selected) < cap:
                    _pick_next(sub)

            # Phase 3: Fill remaining slots up to cap (round-robin)
            while len(cat_selected) < cap:
                added = False
                for sub in subcat_names:
                    if len(cat_selected) >= cap:
                        break
                    if _pick_next(sub):
                        added = True
                if not added:
                    break

            selected.extend(cat_selected)
        elif cat == "hotel":
            # ── Accommodation-type diversity for hotels ─────────────
            # Same round-robin approach as _cap_candidates in place_retriever:
            # group by accommodation_type so hostels, resorts, luxury, and
            # hotels all get representation instead of just top N by score.
            by_accommodation: dict[str, list[tuple[dict, float]]] = {}
            for place, score in items:
                acc_type = (place.get("accommodation_type") or "hotel").lower().strip()
                if not acc_type:
                    acc_type = "hotel"
                by_accommodation.setdefault(acc_type, []).append((place, score))

            type_names = sorted(by_accommodation.keys())
            cat_selected: list[tuple[dict, float]] = []
            seen_ids: set[str] = set()
            ptrs = {t: 0 for t in type_names}

            while len(cat_selected) < cap:
                added = False
                for acc_type in type_names:
                    if len(cat_selected) >= cap:
                        break
                    group = by_accommodation[acc_type]
                    while ptrs[acc_type] < len(group):
                        place, score = group[ptrs[acc_type]]
                        ptrs[acc_type] += 1
                        pid = place.get("id", "")
                        if pid not in seen_ids:
                            cat_selected.append((place, score))
                            seen_ids.add(pid)
                            added = True
                            break
                if not added:
                    break

            selected.extend(cat_selected)
        else:
            selected.extend(items[:cap])

    # Final sort: highest-scored places first (preserves diversity)
    selected.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in selected[:MAX_TOTAL_CANDIDATES]]


async def score_candidates(state: TripState) -> TripState:
    """
    Main Candidate Scorer workflow.

    1. Take filtered places from the Place Retriever.
    2. Load stored embeddings for those places from the database.
    3. Embed the user's preferences as a single query vector.
    4. Score each place with the multi-signal formula.
    5. Apply diversity optimization.
    6. Store the final candidate set in state for the Planning Agent.
    """
    filtered = state.get("filtered_places") or []
    preferences = state.get("profile") or {}
    duration_days = state.get("duration_days", 3)

    if not filtered:
        state["candidate_places"] = []
        state["error"] = "No filtered places to rank"
        return state

    # 1. Load place embeddings from DB
    place_ids = [p.get("id", "") for p in filtered if p.get("id")]
    place_vectors = await load_place_embeddings(place_ids)
    embedded_count = len(place_vectors)
    logger.info(
        "[CandidateScorer] Loaded %d/%d place embeddings from DB",
        embedded_count, len(place_ids),
    )

    # 2. Embed user preferences as a query vector
    query_text = build_query_text(preferences)
    query_vector = embed_query(query_text)
    if query_vector is None:
        logger.warning(
            "[CandidateScorer] Query embedding failed — all places will use "
            "fallback preference score (%.1f)",
            FALLBACK_EMBEDDING_SCORE,
        )

    # 3. Compute city center for proximity scoring
    non_hotel = [p for p in filtered if p.get("category") != "hotel"]
    if non_hotel:
        center_lat = sum(p["lat"] for p in non_hotel) / len(non_hotel)
        center_lon = sum(p["lon"] for p in non_hotel) / len(non_hotel)
    else:
        center_lat, center_lon = 0.0, 0.0

    # 4. Target per category for diversity scoring
    target_per_category = {
        "attraction": max(duration_days * 2, 4),
        "restaurant": max(duration_days, 3),
        "hotel":      max(duration_days // 2 + 1, 2),
    }

    # 5. Score every place
    category_counts: dict[str, int] = {}
    scored = []
    for place in filtered:
        score = _compute_composite_score(
            place, query_vector, place_vectors,
            center_lat, center_lon,
            category_counts, target_per_category,
        )
        cat = place.get("category", "other")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        scored.append((place, score))

    # 6. Determine which subcategories semantically match user interests
    # (using a single lightweight LLM call via the `router` role)
    profile_interests = preferences.get("interests") if preferences else None
    interest_subcats: set[str] = set()
    if profile_interests:
        subcat_names = sorted({
            (p.get("sub_category") or "").lower() or "other"
            for p in filtered
        })
        if subcat_names:
            interest_subcats = await _compute_semantic_interest_subcats(
                profile_interests, subcat_names,
            )
            logger.info(
                "[CandidateScorer] LLM semantic interest→subcat: %d/%d subcats matched "
                "(interests=%s)",
                len(interest_subcats), len(subcat_names),
                profile_interests,
            )

    # 7. Diversity optimization with semantic interest boosting
    candidates = _diversity_optimize(scored, duration_days, interest_subcats)

    # Attach composite scores to candidate dicts so the Planning Agent
    # receives the true relevance signal (not just raw popularity).
    # Scale from 0-1 to 0-100 to match the planner prompt expectations.
    score_map: dict[str, float] = {}
    for p, s in scored:
        pid = p.get("id", "")
        if pid:
            score_map[pid] = round(s * 100.0, 1)
    for c in candidates:
        c["composite_score"] = score_map.get(c.get("id", ""), 0.0)

    state["candidate_places"] = candidates
    state["agent_messages"] = (
        state.get("agent_messages", [])
        + [f"[CandidateScorer] {len(filtered)} filtered → {len(candidates)} ranked "
           f"candidates (embeddings: {embedded_count}/{len(place_ids)})"]
    )
    return state
