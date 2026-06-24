"""
Candidate pool management — coverage metrics, DB refresh decisions, and state helpers.

Keeps edit workflows pool-first: most modifications should resolve from the
stored candidate pool without re-querying PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ai_engine.constants import (
    MODIFIER_POOL_DISPLAY,
    POOL_REFRESH_THRESHOLD,
)
from ai_engine.services.operations import _detect_category_hints


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

    for hotel in itinerary.get("accommodation_suggestions", []):
        hid = hotel.get("id")
        if hid:
            used.add(hid)

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
    """Count unused pool places matching category hints."""
    cats = hints.get("category", [])
    subcats = hints.get("sub_category", [])
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
    hints = _detect_category_hints(modification_request)

    if _is_major_preference_change(classification):
        edit_type = (classification or {}).get("edit_type", "").upper()
        if edit_type == "REGENERATE":
            return True, "regenerate_requested"
        return True, "preference_shift"

    if hints:
        available = _category_available(pool, used_ids, hints)
        if available == 0:
            return True, "missing_category"
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
