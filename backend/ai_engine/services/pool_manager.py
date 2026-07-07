"""
Candidate pool management — coverage metrics, DB refresh decisions, and state helpers.

Keeps edit workflows pool-first: most modifications should resolve from the
stored candidate pool without re-querying PostgreSQL.

Now includes hybrid search functionality for place addition:
1. Extract place name from request (LLM)
2. Try exact match (PostgreSQL)
3. Fall back to vector search in pool
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ai_engine.constants import (
    MODIFIER_POOL_DISPLAY,
    POOL_REFRESH_THRESHOLD,
)
from ai_engine.services.operations import _detect_category_hints, place_matches_semantic_hints
from ai_engine.services.place_extractor import (
    extract_place_name,
    is_high_confidence_extraction,
    is_add_action,
)
from ai_engine.services.embedding_service import (
    build_query_text,
    embed_query_async,
    cosine_similarity,
    load_place_embeddings,
)
from app.core.database import async_session
from app.repositories.place_repo import PlaceRepository

logger = logging.getLogger(__name__)


def extract_used_place_ids(itinerary: dict | None) -> set[str]:
    """Collect place IDs already present in the itinerary (stops + hotels)."""
    used: set[str] = set()
    if not itinerary:
        return used

    for day in itinerary.get("days", []):
        for stop in day.get("stops", []):
            pid = stop.get("id")
            if pid:
                used.add(pid)

    # Hotels are handled in the post-approval HOTEL_SELECTION phase
    # (like flights), so they are no longer part of the itinerary
    # pool management. They are not tracked as used IDs.

    return used


def compute_coverage_by_category(
    pool: list[dict],
    used_ids: set[str],
) -> dict[str, int]:
    """Count unused places per category/subcategory in the pool."""
    coverage: dict[str, int] = {}
    for place in pool:
        pid = place.get("id", "")
        if not pid or pid in used_ids:
            continue
        cat = (place.get("category") or "other").lower()
        sub = (place.get("sub_category") or place.get("subcategory") or "").lower()
        key = f"{cat}:{sub}" if sub else cat
        coverage[key] = coverage.get(key, 0) + 1
    return coverage


def compute_pool_metadata(
    filtered_places: list[dict] | None,
    candidate_places: list[dict] | None,
    itinerary: dict | None,
) -> dict[str, Any]:
    """Build pool health metrics stored alongside conversation state."""
    filtered = filtered_places or []
    candidates = candidate_places or []
    used_ids = extract_used_place_ids(itinerary)

    pool_for_coverage = filtered if filtered else candidates
    unused = [p for p in pool_for_coverage if p.get("id") not in used_ids]

    return {
        "filtered_count": len(filtered),
        "candidate_count": len(candidates),
        "used_count": len(used_ids),
        "remaining_unused": len(unused),
        "coverage_by_category": compute_coverage_by_category(pool_for_coverage, used_ids),
        "coverage_score": round(len(unused) / max(len(pool_for_coverage), 1), 3),
        "last_refreshed_at": datetime.now(timezone.utc).isoformat(),
    }


def get_fresh_pool(
    available_places: list[dict] | None,
    used_ids: set[str] | None = None,
) -> list[dict]:
    """Return pool places not already used in the itinerary."""
    used = used_ids or set()
    return [p for p in (available_places or []) if p.get("id") not in used]


def _category_available(pool: list[dict], used_ids: set[str], hints: dict[str, list[str]]) -> int:
    """Count unused pool places matching category and optional semantic hints."""
    cats = hints.get("category", [])
    subcats = hints.get("sub_category", [])
    semantics = hints.get("semantic", [])
    count = 0
    for p in pool:
        pid = p.get("id", "")
        if not pid or pid in used_ids:
            continue
        p_cat = (p.get("category") or "").lower()
        p_sub = (p.get("sub_category") or p.get("subcategory") or "").lower()
        if subcats and p_sub not in subcats:
            continue
        if cats and not subcats and p_cat not in cats:
            continue
        if semantics and not place_matches_semantic_hints(p, semantics):
            continue
        count += 1
    return count


def _is_major_preference_change(classification: dict | None) -> bool:
    if not classification:
        return False
    edit_type = (classification.get("edit_type") or "").upper()
    return edit_type in (
        "CHANGE_PREFERENCES",
        "CHANGE_BUDGET",
        "CHANGE_PACE",
        "CHANGE_INTERESTS",
        "REGENERATE",
    )


def needs_database_query(
    modification_request: str,
    filtered_places: list[dict] | None,
    candidate_places: list[dict] | None,
    itinerary: dict | None,
    classification: dict | None = None,
) -> tuple[bool, str]:
    """Decide whether an edit requires a fresh database query.

    Returns ``(should_query, reason)`` where *reason* explains the decision.
    """
    pool = filtered_places or candidate_places or []
    used_ids = extract_used_place_ids(itinerary)
    unused = get_fresh_pool(pool, used_ids)
    pool = filtered_places or candidate_places or []
    hints = _detect_category_hints(modification_request, pool=pool)

    if _is_major_preference_change(classification):
        edit_type = (classification or {}).get("edit_type", "").upper()
        if edit_type == "REGENERATE":
            return True, "regenerate_requested"
        return True, "preference_shift"

    if hints:
        available = _category_available(pool, used_ids, hints)
        if available == 0:
            reason = "missing_semantic" if hints.get("semantic") else "missing_category"
            return True, reason
        if available < 2 and any(kw in modification_request.lower() for kw in ("more", "another", "add", "extra")):
            return True, "insufficient_category"

    if len(unused) < POOL_REFRESH_THRESHOLD:
        return True, "low_coverage"

    return False, "pool_sufficient"


def build_pool_state_dict(
    filtered_places: list[dict] | None,
    candidate_places: list[dict] | None,
    itinerary: dict | None,
) -> dict[str, Any]:
    """Serializable pool snapshot for Redis and PostgreSQL persistence."""
    return {
        "filtered_places": filtered_places or [],
        "candidate_places": candidate_places or [],
        "used_place_ids": sorted(extract_used_place_ids(itinerary)),
        "pool_metadata": compute_pool_metadata(filtered_places, candidate_places, itinerary),
    }


def merge_pool_enrichment(existing: list[dict], new_places: list[dict]) -> list[dict]:
    """Add new places to the pool without duplicating IDs."""
    existing_ids = {p.get("id") for p in existing if p.get("id")}
    merged = list(existing)
    for p in new_places:
        pid = p.get("id")
        if pid and pid not in existing_ids:
            merged.append(p)
            existing_ids.add(pid)
    return merged


# ── Hybrid Search for Place Addition ────────────────────────────────────────

# Generic words that describe a place type rather than its name
# (used to strip trailing descriptors before DB matching)
_GENERIC_DESCRIPTORS = {
    "restaurant", "hotel", "museum", "cafe", "café", "shop", "store",
    "park", "bar", "club", "gallery", "theater", "theatre", "temple",
    "mosque", "church", "palace", "fort", "tower", "bridge", "square",
    "market", "mall", "garden", "beach", "lake", "river", "island",
    "street", "road", "avenue", "place", "area", "zone", "district",
    "house", "building", "center", "centre", "point", "view", "spot",
}


def _strip_trailing_generic_words(name: str) -> str:
    """Remove trailing generic descriptors from a place name.

    E.g. "wa7wa7 restaurant" → "wa7wa7"
         "Grand Egyptian Museum" → "Grand Egyptian"  (last word stripped)
         "Pyramids of Giza" → "Pyramids of"  (of is not in generic set)
         "il Nilo" → "il Nilo"  (no change)

    This improves DB matching when users type "add <name> restaurant".
    """
    words = name.strip().split()
    while words and words[-1].lower().strip(".,!?") in _GENERIC_DESCRIPTORS:
        words.pop()
    return " ".join(words) if words else name


async def find_place_for_add(
    modification_request: str,
    city: str | None,
    country: str | None,
    available_places: list[dict] | None,
    preferences: dict | None = None,
) -> list[dict]:
    """
    Hybrid search for finding places to add to the itinerary.

    Implements a multi-stage search pipeline:
    1. Extract place names from request using LLM (can be multiple for "add X and Y")
    2. Try exact match in database for each place name
    3. Fall back to vector search within available pool
    4. Return list of matched places (empty if none found)

    Args:
        modification_request: User's modification request (e.g., "Add the Grand Egyptian Museum and Pyramids")
        city: City name for disambiguation
        country: Country name for disambiguation
        available_places: Candidate pool of places to search within
        preferences: User preferences for semantic search fallback

    Returns:
        List of matching place dicts (can be empty if no matches found)
    """
    logger.info(
        "[HybridSearch] Starting hybrid search for request: '%s' (city=%s, country=%s)",
        modification_request,
        city,
        country,
    )

    if not modification_request:
        logger.warning("[HybridSearch] Empty modification request")
        return []

    # Step 1: Extract place names using LLM
    extraction = await extract_place_name(modification_request)
    logger.info(
        "[HybridSearch] LLM extraction result: place_names=%s, action='%s', confidence=%.2f",
        extraction.place_names,
        extraction.action,
        extraction.confidence,
    )

    # If no high-confidence place names extracted, return empty list
    # (Let the standard modifier agent handle vague requests)
    if not is_high_confidence_extraction(extraction):
        logger.info(
            "[HybridSearch] No high-confidence place names extracted (confidence=%.2f) — "
            "falling back to standard modifier flow",
            extraction.confidence,
        )
        return []

    place_names = extraction.place_names
    logger.info(
        "[HybridSearch] Extracted %d place names: %s with confidence %.2f",
        len(place_names),
        place_names,
        extraction.confidence,
    )

    matched_places = []

    # Search for each place name
    for place_name in place_names:
        # Strip trailing generic words for better DB matching
        # e.g. "wa7wa7 restaurant" → "wa7wa7", "Grand Egyptian Museum" → "Grand Egyptian"
        clean_name = _strip_trailing_generic_words(place_name)
        if clean_name != place_name:
            logger.info(
                "[HybridSearch] Stripped generic descriptor: '%s' → '%s'",
                place_name, clean_name,
            )
            place_name = clean_name

        # Step 2: Try exact match in the in-memory pool
        exact_match = None
        for place in (available_places or []):
            if place_name.lower() in place.get("name", "").lower():
                # Check city match if provided
                if city and place.get("city", "").lower() != city.lower():
                    continue
                # Check country match if provided
                if country and place.get("country", "").lower() != country.lower():
                    continue
                exact_match = place
                logger.info(
                    "[HybridSearch] Found exact match in pool: '%s' (id: %s)",
                    exact_match.get("name"),
                    exact_match.get("id"),
                )
                break

        if exact_match:
            matched_places.append(exact_match)
            continue

        # Step 2b: Fall back to direct database query
        # The pool is a sampled subset — the place may exist in the database
        # but not in the pool (e.g. filtered out by subcategory capping).
        logger.info("[HybridSearch] Not found in pool — querying database for '%s'", place_name)
        logger.info("[HybridSearch] Available pool size: %d places", len(available_places or []))
        try:
            async with async_session() as session:
                repo = PlaceRepository(session)
                db_match = await repo.find_by_name_exact(
                    name=place_name,
                    city=city,
                    country=country,
                )
                if db_match:
                    logger.info(
                        "[HybridSearch] Found in database: '%s' (id: %s)",
                        db_match.get("name"),
                        db_match.get("id"),
                    )
                    matched_places.append(db_match)
                else:
                    logger.info("[HybridSearch] Database query returned None for '%s'", place_name)
        except Exception as exc:
            logger.warning("[HybridSearch] Database query failed for '%s': %s", place_name, exc)

    # If we found any matches, return them
    if matched_places:
        logger.info(
            "[HybridSearch] Found %d matches out of %d requested places",
            len(matched_places),
            len(place_names),
        )
        return matched_places

    # ══════════════════════════════════════════════════════════════════════
    # Step 2c: Vector semantic search across ALL database places
    # ══════════════════════════════════════════════════════════════════════
    # This searches every place in the city that has an embedding, not just
    # the in-memory pool (which is a sampled subset). Catches cases where
    # exact name matching fails but semantic similarity works.
    logger.info(
        "[HybridSearch] Exact name match failed — trying DB vector search across all %s places",
        city or "available",
    )

    # Build query text from place name + preferences
    query_parts = [f"place: {place_name}"]
    if preferences:
        pref_text = build_query_text(preferences)
        if "query: " in pref_text:
            pref_text = pref_text.split("query: ")[1]
        query_parts.append(pref_text)

    query_text = "task: search result | query: " + ". ".join(query_parts)
    query_vector = await embed_query_async(query_text)

    if query_vector is not None and city:
        try:
            from sqlalchemy import select, func
            from sqlalchemy.orm import selectinload
            from app.models.place import Place

            async with async_session() as session:
                # Get ALL place IDs with embeddings for this city
                id_stmt = (
                    select(Place.place_id, Place.embedding)
                    .where(func.lower(Place.city) == city.lower())
                    .where(Place.embedding.isnot(None))
                )
                if country:
                    id_stmt = id_stmt.where(func.lower(Place.country) == country.lower())
                id_result = await session.execute(id_stmt)
                id_rows = id_result.all()

                if id_rows:
                    db_vectors: dict[str, list[float]] = {}
                    for row in id_rows:
                        if row.embedding:
                            db_vectors[row.place_id] = list(row.embedding)

                    if db_vectors:
                        best_id: str | None = None
                        best_sim = -1.0
                        for pid, vec in db_vectors.items():
                            sim = cosine_similarity(query_vector, vec)
                            if sim > best_sim:
                                best_sim = sim
                                best_id = pid

                        if best_id and best_sim > 0.3:
                            # Load full place data for the best match
                            full_stmt = (
                                select(Place)
                                .options(
                                    selectinload(Place.attraction_details),
                                    selectinload(Place.restaurant_details),
                                    selectinload(Place.hotel_details),
                                )
                                .where(Place.place_id == best_id)
                            )
                            full_result = await session.execute(full_stmt)
                            full_place = full_result.scalar_one_or_none()
                            if full_place:
                                repo = PlaceRepository(session)
                                db_match = repo._place_to_dict(full_place)
                                logger.info(
                                    "[HybridSearch] Found DB vector match: '%s' "
                                    "(id: %s, similarity: %.3f)",
                                    db_match.get("name"),
                                    db_match.get("id"),
                                    best_sim,
                                )
                                return [db_match]

                        logger.info(
                            "[HybridSearch] DB vector search: best similarity=%.3f "
                            "(below 0.3 threshold)",
                            best_sim,
                        )
                else:
                    logger.info("[HybridSearch] No places with embeddings found in %s", city)
        except Exception as exc:
            logger.warning("[HybridSearch] DB vector search failed: %s", exc)

    # ══════════════════════════════════════════════════════════════════════
    # Step 3: Fall back to vector search within available pool
    # ══════════════════════════════════════════════════════════════════════
    logger.info("[HybridSearch] DB vector search unavailable — trying pool vector search")

    if query_vector is None:
        # Re-embed if Step 2c didn't already (e.g. if city was None)
        query_vector = await embed_query_async(query_text)
        if query_vector is None:
            logger.warning("[HybridSearch] Query embedding failed — cannot perform vector search")
            return None

    # Load embeddings for available places
    place_ids = [p.get("id", "") for p in (available_places or []) if p.get("id")]
    place_vectors = await load_place_embeddings(place_ids)

    if not place_vectors:
        logger.warning("[HybridSearch] No embeddings available for pool places")
        return None

    # Find best match by cosine similarity
    best_place = None
    best_similarity = -1.0

    for place in (available_places or []):
        place_id = place.get("id", "")
        if place_id not in place_vectors:
            continue

        similarity = cosine_similarity(query_vector, place_vectors[place_id])
        if similarity > best_similarity:
            best_similarity = similarity
            best_place = place

    if best_place and best_similarity > 0.3:  # Minimum similarity threshold
        logger.info(
            "[HybridSearch] Found pool vector match: '%s' (id: %s, similarity: %.3f)",
            best_place.get("name"),
            best_place.get("id"),
            best_similarity,
        )
        return [best_place]

    logger.info(
        "[HybridSearch] No suitable match found (best similarity: %.3f)",
        best_similarity if best_place else 0.0,
    )
    return []
