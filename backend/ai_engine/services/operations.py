"""
Itinerary operations — modify stops, days, and structure.

Each operation is a Pydantic model that the Itinerary Modifier Agent
produces. The ``apply_operation`` dispatcher executes them against an
itinerary dict or ``ConversationState``.

NOTE: Hotels are handled in a separate HOTEL_SELECTION phase (like flights),
so ``ChangeHotelOperation`` is provided only for backward compatibility
with existing tests and the compiled orchestrator.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, List, Optional

from pydantic import BaseModel, Field, model_validator

from ai_engine.conversation.conversation_state import ConversationState

logger = logging.getLogger(__name__)


# ── Operation Schemas ──────────────────────────────────────────────────────────


class RemoveOperation(BaseModel):
    op: str = "REMOVE"
    place_id: str = Field(description="ID of the place to remove")
    day_number: Optional[int] = Field(default=None, description="Day number containing the place")


class SwapOperation(BaseModel):
    op: str = "SWAP"
    remove_place_id: str = Field(description="ID of the place to replace")
    add_place_id: str = Field(description="ID of the new place from the pool")
    day_number: Optional[int] = Field(default=None, description="Day number for the swap")
    new_why_recommended: Optional[str] = Field(default=None, description="Reason for this swap")


class AddOperation(BaseModel):
    op: str = "ADD"
    day_number: Optional[int] = Field(default=None, description="Day to add the place to")
    suggested_time_of_day: Optional[str] = Field(default=None, description="morning/afternoon/evening")
    add_place_id: str = Field(description="ID of the place to add")
    why_recommended: Optional[str] = Field(default=None, description="Reason for adding")
    additional_adds: List[dict] = Field(default_factory=list, description="Extra places to add")


class AddCategoryOperation(BaseModel):
    op: str = "ADD_CATEGORY"
    category: str = Field(description="Category keyword (e.g. museum, restaurant, church, park)")
    count: int = Field(default=1, description="How many to add")
    day_number: Optional[int] = Field(default=None, description="Specific day (auto if omitted)")
    suggested_time_of_day: Optional[str] = Field(default=None, description="Time slot")


class ExchangeOperation(BaseModel):
    op: str = "EXCHANGE"
    place_id_a: str = Field(description="First place ID")
    place_id_b: str = Field(description="Second place ID")


class ReorderOperation(BaseModel):
    op: str = "REORDER"
    day_number: int = Field(description="Day to reorder")
    new_order: List[str] = Field(description="Place IDs in new sequence")


class ReThemeOperation(BaseModel):
    op: str = "RE_THEME"
    day_number: int = Field(description="Day to rename")
    new_theme: str = Field(description="New theme/title for the day")


class ChangeHotelOperation(BaseModel):
    """Hotel change operation — kept for backward compatibility.

    NOTE: Hotels are now handled in the post-approval HOTEL_SELECTION phase
    (like flights). This model exists only for compatibility with the
    compiled orchestrator and existing tests.
    """
    op: str = "CHANGE_HOTEL"
    old_hotel_id: Optional[str] = Field(default=None, description="Hotel ID to replace (None = add new)")
    new_hotel_id: str = Field(description="New hotel ID from the pool")
    why_recommended: Optional[str] = Field(default=None, description="Reason for the change")


class AdditionalAdd(BaseModel):
    place_id: str = Field(description="ID of the place to add")
    suggested_time_of_day: Optional[str] = Field(default=None, description="morning/afternoon/evening")
    why_recommended: Optional[str] = Field(default=None, description="Reason for adding")


# ── ModifierResponse (LLM structured output) ────────────────────────────────────


class ModifierResponse(BaseModel):
    """Structured output from the Itinerary Modifier Agent.

    Supports both flat format (direct fields) and nested format
    (``operation`` key containing the specific operation model).
    """

    model_config = {"arbitrary_types_allowed": True}

    op: str = Field(default="UNKNOWN", description="Operation type")
    place_id: Optional[str] = Field(default=None, description="REMOVE: place ID")
    remove_place_id: Optional[str] = Field(default=None, description="SWAP: old place ID")
    add_place_id: Optional[str] = Field(default=None, description="SWAP/ADD: new place ID")
    day_number: Optional[int] = Field(default=None, description="Target day number")
    new_why_recommended: Optional[str] = Field(default=None, description="SWAP: new reason")
    suggested_time_of_day: Optional[str] = Field(default=None, description="ADD: time slot")
    why_recommended: Optional[str] = Field(default=None, description="Reason for the change")
    additional_adds: List[dict] = Field(default_factory=list, description="Extra ADD operations")
    new_order: Optional[List[str]] = Field(default=None, description="REORDER: new stop order")
    new_theme: Optional[str] = Field(default=None, description="RE_THEME: new theme")
    old_hotel_id: Optional[str] = Field(default=None, description="CHANGE_HOTEL: old hotel ID")
    new_hotel_id: Optional[str] = Field(default=None, description="CHANGE_HOTEL: new hotel ID")
    category: Optional[str] = Field(default=None, description="ADD_CATEGORY: category keyword")
    count: int = Field(default=1, description="ADD_CATEGORY: how many to add")
    place_id_a: Optional[str] = Field(default=None, description="EXCHANGE: first place")
    place_id_b: Optional[str] = Field(default=None, description="EXCHANGE: second place")
    note: str = Field(default="", description="Human-readable note / error info")

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, data: Any) -> Any:
        """Handle both flat (direct fields) and nested (``operation`` key) formats."""
        if not isinstance(data, dict):
            return data

        operation = data.get("operation")
        if operation is None:
            return data

        # Nested format: operation is a BaseModel or dict
        if isinstance(operation, BaseModel):
            op_dict = operation.model_dump()
        elif isinstance(operation, dict):
            op_dict = operation
        else:
            return data

        # Merge operation fields into the top level, keeping note from outer level
        note = data.get("note", "")
        result = dict(op_dict)
        result["note"] = note
        # Keep additional_adds if present
        if "additional_adds" in data:
            result["additional_adds"] = data["additional_adds"]
        return result


# ── Compound operation type for backward-compat apply_operation ────────────────


def _is_state_based(*args, **kwargs) -> bool:
    """Detect whether the calling convention uses ConversationState or dict."""
    if args and isinstance(args[0], ConversationState):
        return True
    if "state" in kwargs and isinstance(kwargs["state"], ConversationState):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Old-style dict-based executors (for modifier agent + tests)
# ══════════════════════════════════════════════════════════════════════════════


def _find_day(itinerary: dict, day_number: int) -> dict | None:
    """Find a day in the itinerary by its day_number."""
    for day in itinerary.get("days", []):
        if day.get("day_number") == day_number:
            return day
    return None


def _find_stop_index(stops: list[dict], place_id: str) -> int:
    """Find the index of a stop by place_id, or return -1."""
    for i, stop in enumerate(stops):
        if stop.get("id") == place_id:
            return i
    return -1


def _remove_travel_time(stop: dict) -> None:
    """Remove travel_time fields from a stop (mutates in-place)."""
    stop.pop("travel_time_to_next_minutes", None)
    stop.pop("transport_mode", None)


def _exec_remove(itinerary: dict, op: ModifierResponse) -> dict:
    """Remove a stop from the itinerary (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    place_id = op.place_id
    if not place_id:
        return result

    found = False
    for day in result.get("days", []):
        stops = day.get("stops", [])
        removed = [s for s in stops if s.get("id") != place_id]
        if len(removed) < len(stops):
            found = True
            # Clear travel time on the new last stop
            if removed:
                last_stop = removed[-1]
                if "travel_time_to_next_minutes" in last_stop or "transport_mode" in last_stop:
                    _remove_travel_time(last_stop)
        day["stops"] = removed

    if not found:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nStop {place_id} not found".strip()
    return result


def _exec_swap(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Swap a stop with a new place from the pool (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    new_place = _find_best_name_match(place_pool or [], op.add_place_id or "")
    if not new_place:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nNew place '{op.add_place_id}' not found in pool".strip()
        return result

    for day in result.get("days", []):
        if op.day_number and day.get("day_number") != op.day_number:
            continue
        for stop in day.get("stops", []):
            if stop.get("id") == op.remove_place_id:
                # Carry over travel time
                travel_time = stop.get("travel_time_to_next_minutes")
                transport = stop.get("transport_mode")
                stop["id"] = new_place["id"]
                stop["name"] = new_place.get("name", "")
                stop["category"] = new_place.get("category", "")
                stop["sub_category"] = new_place.get("sub_category", "")
                stop["cuisine_type"] = new_place.get("cuisine_type", "")
                stop["lat"] = new_place.get("lat", 0)
                stop["lon"] = new_place.get("lon", 0)
                if travel_time is not None:
                    stop["travel_time_to_next_minutes"] = travel_time
                if transport is not None:
                    stop["transport_mode"] = transport
                if op.new_why_recommended:
                    stop["why_recommended"] = op.new_why_recommended
                # Attach rich metadata
                for key in ("address", "photos", "rating", "estimated_duration_minutes"):
                    if key in new_place:
                        stop[key] = new_place[key]
                return result

    return result


def _exec_add(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Add a stop to the itinerary (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    place = _find_best_name_match(place_pool or [], op.add_place_id or "")
    if not place:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nPlace '{op.add_place_id}' not found in pool".strip()
        return result

    day_num = op.day_number or 1
    target = _find_day(result, day_num)
    if not target:
        return result

    time_slot = op.suggested_time_of_day or "afternoon"
    new_stop = {
        "id": place["id"],
        "name": place.get("name", ""),
        "category": place.get("category", ""),
        "sub_category": place.get("sub_category", ""),
        "cuisine_type": place.get("cuisine_type", ""),
        "lat": place.get("lat", 0),
        "lon": place.get("lon", 0),
        "suggested_time_of_day": time_slot,
        "why_recommended": op.why_recommended or "Added per your request",
        "estimated_duration_minutes": place.get("estimated_duration_minutes", 60),
    }
    # Attach rich metadata
    for key in ("address", "photos", "rating"):
        if key in place:
            new_stop[key] = place[key]

    stops = target.get("stops", [])
    # Set travel time on the previous stop before inserting
    if stops:
        stops[-1]["travel_time_to_next_minutes"] = 10.0
        stops[-1]["transport_mode"] = "driving"
    stops.append(new_stop)
    target["stops"] = _sort_stops_by_time_slot(stops)
    return result


def _exec_add_category(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Add places of a specific category (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    category = (op.category or "").strip().lower()
    if not category:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nADD_CATEGORY missing category".strip()
        return result

    # Filter pool by semantic match
    matches = [p for p in (place_pool or []) if place_matches_semantic_tag(p, category)]
    # Exclude places already in the itinerary
    existing_ids = set()
    for day in result.get("days", []):
        for stop in day.get("stops", []):
            existing_ids.add(stop.get("id"))
    matches = [m for m in matches if m["id"] not in existing_ids]
    # Sort by rating descending
    matches.sort(key=lambda p: p.get("rating", 0) or 0, reverse=True)

    count = min(op.count or 1, len(matches), 5)
    if count == 0:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nCannot apply ADD_CATEGORY: no matching places for '{category}'".strip()
        return result

    day_num = op.day_number or 1
    target = _find_day(result, day_num)
    if not target:
        return result

    time_slot = op.suggested_time_of_day or "afternoon"
    for place in matches[:count]:
        new_stop = {
            "id": place["id"],
            "name": place.get("name", ""),
            "category": place.get("category", ""),
            "sub_category": place.get("sub_category", ""),
            "cuisine_type": place.get("cuisine_type", ""),
            "lat": place.get("lat", 0),
            "lon": place.get("lon", 0),
            "suggested_time_of_day": time_slot,
            "why_recommended": f"Added {category} per your request",
            "estimated_duration_minutes": place.get("estimated_duration_minutes", 60),
        }
        target.setdefault("stops", []).append(new_stop)

    target["stops"] = _sort_stops_by_time_slot(target.get("stops", []))
    return result


def _exec_change_hotel(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Change a hotel in the itinerary (old-style, returns deep copy).

    NOTE: Hotels are now handled in the post-approval HOTEL_SELECTION phase.
    This executor is kept for backward compatibility with tests and the
    compiled orchestrator.
    """
    result = copy.deepcopy(itinerary)
    new_hotel = _find_best_name_match(place_pool or [], op.new_hotel_id or "")
    if not new_hotel:
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nHotel '{op.new_hotel_id}' not found in pool".strip()
        return result

    replacement = {
        "id": new_hotel["id"],
        "name": new_hotel.get("name", ""),
        "sub_category": new_hotel.get("sub_category", ""),
        "accommodation_type": new_hotel.get("accommodation_type", ""),
        "lat": new_hotel.get("lat", 0),
        "lon": new_hotel.get("lon", 0),
        "why_recommended": op.why_recommended or new_hotel.get("why_recommended", ""),
        "rating": new_hotel.get("rating", 0),
        "amenities": new_hotel.get("amenities", []),
        "nightly_rate": new_hotel.get("nightly_rate", 0),
        "address": new_hotel.get("address", ""),
        "photos": (new_hotel.get("photos") or [])[:1],
        "maps_link": new_hotel.get("maps_link", ""),
    }

    suggestions = result.get("accommodation_suggestions", [])
    if op.old_hotel_id:
        idx = _find_stop_index(suggestions, op.old_hotel_id)
        if idx >= 0:
            suggestions[idx] = replacement
        else:
            suggestions.append(replacement)
    else:
        suggestions.append(replacement)

    result["accommodation_suggestions"] = suggestions
    return result


def _exec_reorder(itinerary: dict, op: ModifierResponse) -> dict:
    """Reorder stops within a day (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    target = _find_day(result, op.day_number or 0)
    if not target or not op.new_order:
        return result

    stops = target.get("stops", [])
    stop_map = {s["id"]: s for s in stops}

    # If ANY ID in new_order is not in the stop_map, return unchanged
    for sid in op.new_order:
        if sid not in stop_map:
            return result

    reordered = [stop_map[sid] for sid in op.new_order]
    # Append any stops not in new_order (shouldn't happen with above check, but safety)
    reordered.extend(s for s in stops if s["id"] not in stop_map)

    # Carry over travel_time from old first stop to new first stop
    if reordered and stops:
        old_first_travel = stops[0].get("travel_time_to_next_minutes")
        old_first_transport = stops[0].get("transport_mode")
        if old_first_travel is not None:
            reordered[0]["travel_time_to_next_minutes"] = old_first_travel
        if old_first_transport is not None:
            reordered[0]["transport_mode"] = old_first_transport

    # Clear travel time on new last stop
    if reordered:
        _remove_travel_time(reordered[-1])

    target["stops"] = reordered
    return result


def _exec_exchange(itinerary: dict, op: ModifierResponse) -> dict:
    """Exchange time slots between two stops (old-style, returns deep copy).

    Finds both stops on the SAME day to avoid matching duplicate IDs
    that appear on different days (e.g. ``rest_001`` on both Day 1
    customisation and Day 2 of the base itinerary).
    """
    result = copy.deepcopy(itinerary)
    stop_a = None
    stop_b = None

    for day in result.get("days", []):
        stops = day.get("stops", [])
        found_a = next((s for s in stops if s.get("id") == op.place_id_a), None)
        found_b = next((s for s in stops if s.get("id") == op.place_id_b), None)
        if found_a and found_b:
            # Both on the same day — this is the intended day
            stop_a = found_a
            stop_b = found_b
            break
        # Track first single match in case pair not found on same day
        if found_a and stop_a is None:
            stop_a = found_a
        if found_b and stop_b is None:
            stop_b = found_b

    if stop_a and stop_b:
        stop_a["suggested_time_of_day"], stop_b["suggested_time_of_day"] = (
            stop_b["suggested_time_of_day"], stop_a["suggested_time_of_day"]
        )
        for day in result.get("days", []):
            day["stops"] = _sort_stops_by_time_slot(day.get("stops", []))
    else:
        missing = [x for x in (op.place_id_a, op.place_id_b) if x not in (
            (stop_a or {}).get("id"), (stop_b or {}).get("id")
        )]
        existing = result.get("_modifier_note", "")
        result["_modifier_note"] = f"{existing}\nStops not found: {', '.join(missing)}".strip()

    return result


def _exec_retheme(itinerary: dict, op: ModifierResponse) -> dict:
    """Update a day's theme (old-style, returns deep copy)."""
    result = copy.deepcopy(itinerary)
    target = _find_day(result, op.day_number or 0)
    if target:
        target["theme"] = op.new_theme or ""
    return result


# ── Execution Helpers (ConversationState-based) ────────────────────────────────


def _sort_stops_by_time_slot(stops: list[dict]) -> list[dict]:
    """Sort stops by suggested_time_of_day order: morning → afternoon → evening."""
    ORDER = {"morning": 0, "afternoon": 1, "evening": 2}
    return sorted(stops, key=lambda s: ORDER.get(s.get("suggested_time_of_day", ""), 99))


def _fix_travel_times(state: ConversationState) -> ConversationState:
    """Recalculate travel times after a structural edit."""
    try:
        from ai_engine.services.route_optimizer import recompute_travel_times
        state = recompute_travel_times(state)
    except Exception as exc:
        logger.warning("[Ops] Travel time recompute skipped: %s", exc)
    return state


def _name_match_score(name: str, query: str) -> float:
    """Simple fuzzy name match score (0-1)."""
    if not name or not query:
        return 0.0
    name = name.lower().strip()
    query = query.lower().strip()
    if query in name:
        return 1.0
    words = query.split()
    if words and all(w in name for w in words):
        return 0.8
    return 0.0


def _find_best_name_match(
    candidates: list[dict], name_or_id: str,
) -> dict | None:
    """Find a candidate place by name or ID."""
    for c in candidates:
        if c.get("id") == name_or_id:
            return c
    best = None
    best_score = 0.0
    for c in candidates:
        score = _name_match_score(c.get("name", ""), name_or_id)
        if score > best_score:
            best_score = score
            best = c
    return best if best_score >= 0.5 else None


def place_matches_semantic_tag(place: dict, tag: str) -> bool:
    """Check if a place matches a semantic category tag.

    For tags that have precise semantic aliases in ``_SEMANTIC_KEYWORDS``
    (e.g. ``church`` vs ``mosque``), only those specific aliases are used
    to avoid false matches between related but distinct categories.
    """
    tag = tag.lower().strip()
    name = (place.get("name") or "").lower()
    category = (place.get("category") or "").lower()
    sub_category = (place.get("sub_category") or "").lower()
    cuisine_type = (place.get("cuisine_type") or "").lower()

    # If this tag has precise semantic aliases, use ONLY those (narrow match)
    if tag in _SEMANTIC_KEYWORDS:
        aliases = _SEMANTIC_KEYWORDS[tag]
        return any(alias in name for alias in aliases)

    # Generic tags: use broad matching
    direct_match = tag in name or tag in sub_category or tag in category
    cuisine_match = tag in cuisine_type
    category_match = tag == category

    tag_map = {
        "museum": ["museum", "historical", "heritage"],
        "restaurant": ["restaurant", "food", "dining", "lunch", "dinner"],
        "park": ["park", "garden", "nature", "outdoor"],
        "shopping": ["shopping", "mall", "market", "souk", "bazaar"],
        "viewpoint": ["viewpoint", "observation", "skyline", "panorama"],
        "historical": ["historical", "historical site", "monument", "ancient"],
        "beach": ["beach", "shore", "coast"],
        "nightlife": ["nightlife", "club", "bar", "entertainment"],
        "cafe": ["cafe", "coffee", "bakery", "pastry"],
    }
    mapped = [d for k, vals in tag_map.items() for d in vals if tag == k]
    mapped_match = any(m in name or m in sub_category for m in mapped)

    return direct_match or cuisine_match or category_match or mapped_match


def filter_places_by_semantics(places: list[dict], tag: str | list[str]) -> list[dict]:
    """Filter places by semantic category tag(s).

    Args:
        places: List of place dicts to filter.
        tag: A single tag string, or a list of tags (any match passes).
    """
    if isinstance(tag, list):
        tags = tag
        return [p for p in places if any(place_matches_semantic_tag(p, t) for t in tags)]
    return [p for p in places if place_matches_semantic_tag(p, tag)]


# ── State-based executors (for compiled _orchestrator) ─────────────────────────


def _exec_remove_state(state: ConversationState, op: RemoveOperation) -> ConversationState:
    """Remove a stop by place_id (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    found = False
    for day in days:
        stops = day.get("stops", [])
        day["stops"] = [s for s in stops if s.get("id") != op.place_id]
        if len(stops) != len(day["stops"]):
            # Clear travel time on new last stop
            if day["stops"]:
                _remove_travel_time(day["stops"][-1])
            found = True
    if found:
        state.itinerary = itinerary
        logger.info("[Ops] Removed stop %s", op.place_id)
    else:
        logger.warning("[Ops] Stop %s not found for removal", op.place_id)
    return state


def _exec_add_state(state: ConversationState, op: AddOperation) -> ConversationState:
    """Add a stop (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    candidates = state.candidate_places or []

    place = _find_best_name_match(candidates, op.add_place_id)
    if not place:
        logger.warning("[Ops] Place %s not found for ADD", op.add_place_id)
        return state

    day_num = op.day_number or 1
    target_day = next((d for d in days if d.get("day_number") == day_num), None)
    if not target_day:
        return state

    new_stop = {
        "id": place["id"],
        "name": place.get("name", ""),
        "category": place.get("category", ""),
        "sub_category": place.get("sub_category", ""),
        "cuisine_type": place.get("cuisine_type", ""),
        "lat": place.get("lat", 0),
        "lon": place.get("lon", 0),
        "suggested_time_of_day": op.suggested_time_of_day or "afternoon",
        "why_recommended": op.why_recommended or "Added per your request",
        "estimated_duration_minutes": place.get("estimated_duration_minutes", 60),
    }
    target_day.setdefault("stops", []).append(new_stop)
    target_day["stops"] = _sort_stops_by_time_slot(target_day["stops"])
    state.itinerary = itinerary
    logger.info("[Ops] Added stop %s to day %d", place.get("name"), day_num)

    for extra in (op.additional_adds or []):
        extra_place = _find_best_name_match(candidates, extra.get("place_id", ""))
        if extra_place:
            extra_stop = {
                "id": extra_place["id"],
                "name": extra_place.get("name", ""),
                "category": extra_place.get("category", ""),
                "sub_category": extra_place.get("sub_category", ""),
                "cuisine_type": extra_place.get("cuisine_type", ""),
                "lat": extra_place.get("lat", 0),
                "lon": extra_place.get("lon", 0),
                "suggested_time_of_day": extra.get("suggested_time_of_day", "afternoon"),
                "why_recommended": extra.get("why_recommended", "Added per your request"),
                "estimated_duration_minutes": extra_place.get("estimated_duration_minutes", 60),
            }
            target_day.setdefault("stops", []).append(extra_stop)
            target_day["stops"] = _sort_stops_by_time_slot(target_day["stops"])

    return state


def _exec_add_category_state(state: ConversationState, op: AddCategoryOperation) -> ConversationState:
    """Add places of a specific category (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    candidates = state.candidate_places or []

    matches = filter_places_by_semantics(candidates, op.category)
    existing_ids = set()
    for day in days:
        for stop in day.get("stops", []):
            existing_ids.add(stop.get("id"))
    matches = [m for m in matches if m["id"] not in existing_ids]

    count = min(op.count, len(matches))
    if count == 0:
        logger.warning("[Ops] No matching places for category '%s'", op.category)
        return state

    day_num = op.day_number or 1
    target_day = next((d for d in days if d.get("day_number") == day_num), None)
    if not target_day:
        return state

    for place in matches[:count]:
        new_stop = {
            "id": place["id"],
            "name": place.get("name", ""),
            "category": place.get("category", ""),
            "sub_category": place.get("sub_category", ""),
            "cuisine_type": place.get("cuisine_type", ""),
            "lat": place.get("lat", 0),
            "lon": place.get("lon", 0),
            "suggested_time_of_day": op.suggested_time_of_day or "afternoon",
            "why_recommended": f"Added {op.category} per your request",
            "estimated_duration_minutes": place.get("estimated_duration_minutes", 60),
        }
        target_day.setdefault("stops", []).append(new_stop)

    target_day["stops"] = _sort_stops_by_time_slot(target_day["stops"])
    state.itinerary = itinerary
    logger.info("[Ops] Added %d places for category '%s'", count, op.category)
    return state


def _exec_exchange_state(state: ConversationState, op: ExchangeOperation) -> ConversationState:
    """Swap time slots between two existing stops (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    stop_a = None
    stop_b = None

    for day in days:
        for stop in day.get("stops", []):
            if stop.get("id") == op.place_id_a:
                stop_a = stop
            if stop.get("id") == op.place_id_b:
                stop_b = stop

    if stop_a and stop_b:
        stop_a["suggested_time_of_day"], stop_b["suggested_time_of_day"] = (
            stop_b["suggested_time_of_day"], stop_a["suggested_time_of_day"]
        )
        for day in days:
            day["stops"] = _sort_stops_by_time_slot(day.get("stops", []))
        state.itinerary = itinerary
        logger.info("[Ops] Exchanged time slots between %s and %s", op.place_id_a, op.place_id_b)
    return state


def _exec_swap_state(state: ConversationState, op: SwapOperation) -> ConversationState:
    """Replace a stop with a new place (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    candidates = state.candidate_places or []

    new_place = _find_best_name_match(candidates, op.add_place_id)
    if not new_place:
        logger.warning("[Ops] New place %s not found for SWAP", op.add_place_id)
        return state

    for day in days:
        for stop in day.get("stops", []):
            if stop.get("id") == op.remove_place_id:
                stop["id"] = new_place["id"]
                stop["name"] = new_place.get("name", "")
                stop["category"] = new_place.get("category", "")
                stop["sub_category"] = new_place.get("sub_category", "")
                stop["cuisine_type"] = new_place.get("cuisine_type", "")
                stop["lat"] = new_place.get("lat", 0)
                stop["lon"] = new_place.get("lon", 0)
                if op.new_why_recommended:
                    stop["why_recommended"] = op.new_why_recommended
                state.itinerary = itinerary
                logger.info("[Ops] Swapped %s → %s", op.remove_place_id, op.add_place_id)
                return state

    logger.warning("[Ops] Old place %s not found for SWAP", op.remove_place_id)
    return state


def _exec_reorder_state(state: ConversationState, op: ReorderOperation) -> ConversationState:
    """Reorder stops within a day (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])

    target_day = next((d for d in days if d.get("day_number") == op.day_number), None)
    if not target_day:
        return state

    stops = target_day.get("stops", [])
    stop_map = {s["id"]: s for s in stops}
    reordered = [stop_map[sid] for sid in op.new_order if sid in stop_map]
    reordered.extend(s for s in stops if s["id"] not in stop_map)

    if reordered:
        _remove_travel_time(reordered[-1])

    target_day["stops"] = reordered
    state.itinerary = itinerary
    logger.info("[Ops] Reordered day %d", op.day_number)
    return state


def _exec_retheme_state(state: ConversationState, op: ReThemeOperation) -> ConversationState:
    """Update a day's theme (ConversationState-based)."""
    itinerary = state.itinerary or {}
    days = itinerary.get("days", [])
    target_day = next((d for d in days if d.get("day_number") == op.day_number), None)
    if target_day:
        target_day["theme"] = op.new_theme
        state.itinerary = itinerary
        logger.info("[Ops] Re-themed day %d → '%s'", op.day_number, op.new_theme)
    return state


def _insert_stop_by_time_slot(stops: list[dict], new_stop: dict) -> list[dict]:
    """Insert a stop into the correct position based on its time slot."""
    ORDER = {"morning": 0, "afternoon": 1, "evening": 2}
    new_order = ORDER.get(new_stop.get("suggested_time_of_day", "afternoon"), 1)
    for i, stop in enumerate(stops):
        stop_order = ORDER.get(stop.get("suggested_time_of_day", ""), 99)
        if new_order < stop_order:
            stops.insert(i, new_stop)
            return stops
    stops.append(new_stop)
    return stops


def _find_best_day_for_place(
    place: dict, days: list[dict], candidates: list[dict] | None = None,
) -> int | None:
    """Find the best day to add this place based on proximity to existing stops."""
    from ai_engine.tools.haversine import haversine

    pl = (place.get("lat", 0), place.get("lon", 0))
    best_day = None
    best_dist = float("inf")

    for day in days:
        day_stops = day.get("stops", [])
        if not day_stops:
            continue
        total = 0.0
        count = 0
        for stop in day_stops:
            sl = (stop.get("lat", 0), stop.get("lon", 0))
            total += haversine(pl[0], pl[1], sl[0], sl[1])
            count += 1
        if count > 0:
            avg = total / count
            if avg < best_dist:
                best_dist = avg
                best_day = day.get("day_number")

    return best_day or 1


def _find_best_day_and_slot_for_place(
    place: dict,
    itinerary: dict,
    used_slots_per_day: dict[int, set[str]] | None = None,
) -> tuple[int, str]:
    """Find the best day and time slot for a place.

    Args:
        place: The place dict with lat/lon.
        itinerary: Full itinerary dict.
        used_slots_per_day: Track already-used slots to avoid clustering.

    Returns:
        Tuple of (day_number, time_slot).
    """
    days = itinerary.get("days", [])
    if not days:
        return 1, "afternoon"

    # Score each day by proximity
    best_day = 1
    best_score = -1.0

    for day in days:
        day_num = day.get("day_number", 1)
        score = _score_day_for_place(place, day)
        # Penalize days that already have many stops
        n_stops = len(day.get("stops", []))
        score -= n_stops * 0.1
        if score > best_score:
            best_score = score
            best_day = day_num

    # Find the most available slot for the chosen day
    used = used_slots_per_day.get(best_day, set()) if used_slots_per_day else set()
    for slot in ("morning", "afternoon", "evening"):
        if slot not in used:
            return best_day, slot

    return best_day, "afternoon"


def _score_day_for_place(place: dict, day: dict) -> float:
    """Score how well a place fits in a day (higher = better)."""
    from ai_engine.tools.haversine import haversine

    stops = day.get("stops", [])
    if not stops:
        return 0.0

    total_dist = 0.0
    for stop in stops:
        total_dist += haversine(
            place.get("lat", 0), place.get("lon", 0),
            stop.get("lat", 0), stop.get("lon", 0),
        )
    avg_dist = total_dist / len(stops)

    proximity = max(0.0, 1.0 - (avg_dist / 20.0))
    return proximity


def _rebalance_clustered_slots(itinerary: dict) -> dict:
    """Redistribute stops when one day has too many."""
    days = itinerary.get("days", [])
    changed = False
    for day in days:
        stops = day.get("stops", [])
        if len(stops) > 5:
            overflow = stops[5:]
            day["stops"] = stops[:5]
            lightest = min(days, key=lambda d: len(d.get("stops", [])))
            for s in overflow:
                lightest.setdefault("stops", []).append(s)
            changed = True
    if changed:
        for day in days:
            day["stops"] = _sort_stops_by_time_slot(day.get("stops", []))
    return itinerary


# ── Category Detection ──────────────────────────────────────────────────────────


_CATEGORY_KEYWORDS: dict[str, tuple[list[str], list[str]]] = {
    # (categories, sub_categories)
    "museum":     (["attraction"], ["museums"]),
    "museums":    (["attraction"], ["museums"]),
    "art gallery":(["attraction"], ["galleries", "art"]),
    "gallery":    (["attraction"], ["galleries", "art"]),
    "galleries":  (["attraction"], ["galleries", "art"]),
    "historic":   (["attraction"], ["historical", "historic sites"]),
    "historical": (["attraction"], ["historical", "historic sites"]),
    "monument":   (["attraction"], ["monuments"]),
    "monuments":  (["attraction"], ["monuments"]),
    "temple":     (["attraction"], ["temples", "religious"]),
    "temples":    (["attraction"], ["temples", "religious"]),
    "mosque":     (["attraction"], ["religious", "mosques"]),
    "mosques":    (["attraction"], ["religious", "mosques"]),
    "church":     (["attraction"], ["religious", "churches"]),
    "churches":   (["attraction"], ["religious", "churches"]),
    "religious":  (["attraction"], ["religious"]),
    "park":       (["attraction"], ["parks"]),
    "parks":      (["attraction"], ["parks"]),
    "garden":     (["attraction"], ["parks", "gardens"]),
    "gardens":    (["attraction"], ["parks", "gardens"]),
    "nature":     (["attraction"], ["nature", "parks"]),
    "beach":      (["attraction"], ["beaches", "nature"]),
    "beaches":    (["attraction"], ["beaches", "nature"]),
    "nightlife":  (["attraction"], ["nightlife"]),
    "shopping":   (["attraction"], ["shopping", "markets"]),
    "market":     (["attraction"], ["markets", "shopping"]),
    "markets":    (["attraction"], ["markets", "shopping"]),
    "souk":       (["attraction"], ["markets", "shopping"]),
    "viewpoint":  (["attraction"], ["viewpoints"]),
    "viewpoints": (["attraction"], ["viewpoints"]),
    "cafe":       (["restaurant"], ["cafe", "coffee"]),
    "cafes":      (["restaurant"], ["cafe", "coffee"]),
    "coffee":     (["restaurant"], ["cafe", "coffee"]),
    "restaurant": (["restaurant"], ["restaurants", "dining"]),
    "restaurants":(["restaurant"], ["restaurants", "dining"]),
    "food":       (["restaurant"], ["restaurants", "dining", "local cuisine"]),
    "dining":     (["restaurant"], ["restaurants", "dining"]),
    "bakery":     (["restaurant"], ["bakery", "pastry"]),
    "hotel":      (["hotel"], []),
    "hotels":     (["hotel"], []),
    "accommodation": (["hotel"], []),
}

_SEMANTIC_KEYWORDS: dict[str, list[str]] = {
    # Only keywords that need semantic differentiation beyond category/subcategory.
    # "church" and "mosque" both map to the same sub_category "religious",
    # so the semantic tag is needed to distinguish them for filtering.
    # All other keywords (museum, park, restaurant, etc.) are fully covered
    # by _CATEGORY_KEYWORDS mapping.
    "church": ["church", "chapel", "cathedral", "basilica"],
    "mosque": ["mosque", "masjid"],
}


def _detect_category_hints(
    modification_request: str,
    pool: list[dict] | None = None,
) -> dict:
    """Detect which category of places the user wants to add/modify.

    Returns a dict with keys: "category" (list[str]), "sub_category" (list[str]),
    and optionally "semantic" (list[str]).
    """
    if not modification_request:
        return {}

    text = modification_request.lower().strip()
    categories: list[str] = []
    sub_categories: list[str] = []

    for keyword, (cats, subcats) in _CATEGORY_KEYWORDS.items():
        if keyword in text:
            for c in cats:
                if c not in categories:
                    categories.append(c)
            for sc in subcats:
                if sc not in sub_categories:
                    sub_categories.append(sc)

    result: dict = {}
    if categories:
        result["category"] = categories
    if sub_categories:
        result["sub_category"] = sub_categories

    # Semantic detection
    semantics: list[str] = []
    for tag, aliases in _SEMANTIC_KEYWORDS.items():
        if any(alias in text for alias in aliases):
            semantics.append(tag)

    if semantics:
        result["semantic"] = semantics

    # Pool-based semantic refinement
    if pool and result.get("semantic"):
        refined = []
        for sem in result["semantic"]:
            matches = [p for p in pool if place_matches_semantic_tag(p, sem)]
            if matches:
                refined.append(sem)
        if refined:
            result["semantic"] = refined

    return result


def _reorder_pool_by_category(pool: list[dict], hints: dict) -> list[dict]:
    """Reorder the pool so matching places come first."""
    if not hints or not pool:
        return list(pool)

    # Normalize hint values to lists (callers may pass strings or lists)
    cats_raw = hints.get("category", [])
    subcats_raw = hints.get("sub_category", [])
    cats = cats_raw if isinstance(cats_raw, list) else [cats_raw]
    subcats = subcats_raw if isinstance(subcats_raw, list) else [subcats_raw]

    def _score(p: dict) -> int:
        score = 0
        if cats and p.get("category", "").lower() in [c.lower() for c in cats]:
            score += 10
        if subcats and p.get("sub_category", "").lower() in [sc.lower() for sc in subcats]:
            score += 5
        return score

    return sorted(pool, key=_score, reverse=True)


def _build_subcategory_texts(pool: list[dict]) -> dict[tuple[str, str], str]:
    """Build a mapping of (category, sub_category) → descriptive text for embeddings."""
    result: dict[tuple[str, str], str] = {}
    for place in pool:
        cat = (place.get("category") or "").strip().lower()
        sub = (place.get("sub_category") or "").strip().lower()
        if not cat or not sub:
            continue

        key = (cat, sub)
        parts = [f"category: {cat}", f"type: {sub}"]

        # Add unique place names (filter stop words)
        name = (place.get("name") or "").strip()
        if name:
            words = [w for w in name.lower().split() if w not in ("the", "a", "an", "of", "and", "&")]
            if words:
                parts.append("names: " + " ".join(words[:3]))

        # Add cuisine type if available
        cuisine = place.get("cuisine_type", "")
        if cuisine:
            parts.append(f"cuisine: {cuisine}")

        # Add interest tags
        tags = place.get("interest_tags", [])
        if tags:
            parts.append("tags: " + ", ".join(tags[:3]))

        text = " | ".join(parts)
        if key in result:
            # Merge descriptions for same subcategory (avoid duplicates)
            existing_names = result[key]
            if text not in existing_names:
                result[key] = existing_names + "\n" + text
        else:
            result[key] = text

    return result


# ── Context Builder ────────────────────────────────────────────────────────────


async def build_compact_context(
    itinerary: dict,
    modification_request: str,
    available_places: list[dict] | None = None,
    preferences: dict | None = None,
    max_places: int = 30,
) -> str:
    """Build a compact text summary of the itinerary and available places.

    Args:
        itinerary: The full itinerary dict.
        modification_request: The user's edit request.
        available_places: Pool of candidate places.
        preferences: Dict with budget/pace/interests.
        max_places: Maximum places to include in the context.

    Returns:
        A compact text context string for the LLM.
    """
    parts = [f"Modification request: {modification_request}"]

    destination = itinerary.get("destination", "")
    duration = itinerary.get("duration_days", "")
    if destination:
        parts.append(f"Destination: {destination}")
    if duration:
        parts.append(f"Duration: {duration} days")

    # Day-by-day summary
    days = itinerary.get("days", [])
    for day in days:
        day_num = day.get("day_number", "?")
        theme = day.get("theme", "")
        stops = day.get("stops", [])
        stop_texts = []
        for s in stops:
            sid = s.get("id", "")
            sname = s.get("name", "?")
            stime = s.get("suggested_time_of_day", "")
            time_str = f" ({stime})" if stime else ""
            stop_texts.append(f"{sname}[{sid}]{time_str}")
        parts.append(f"Day {day_num}: {theme} — {' → '.join(stop_texts)}")

    # Current hotels
    hotels = itinerary.get("accommodation_suggestions", [])
    if hotels:
        hotel_texts = []
        for h in hotels:
            hid = h.get("id", "")
            hname = h.get("name", "?")
            hotel_texts.append(f"{hname}[{hid}]")
        parts.append(f"Current hotels: {', '.join(hotel_texts)}")

    # Available places
    if available_places:
        # Exclude places already in the itinerary
        used_ids = set()
        for day in days:
            for s in day.get("stops", []):
                used_ids.add(s.get("id"))
        for h in hotels:
            used_ids.add(h.get("id"))

        available = [p for p in available_places if p.get("id") not in used_ids]
        if available:
            available = available[:max_places]
            place_texts = []
            for p in available:
                pid = p.get("id", "")
                pname = p.get("name", "?")
                pcat = p.get("category", "")
                psub = p.get("sub_category", "")
                cat_str = f" ({pcat}/{psub})" if pcat or psub else ""
                place_texts.append(f"{pname}[{pid}]{cat_str}")
            parts.append(f"Available places ({len(available)}):")
            parts.append("\n".join(place_texts))

    # Preferences
    if preferences:
        pref_parts = []
        for key in ("budget_level", "travel_style", "pace"):
            val = preferences.get(key)
            if val:
                pref_parts.append(f"{key}: {val}")
        interests = preferences.get("interests")
        if interests:
            pref_parts.append(f"interests: {', '.join(interests[:5])}")
        food = preferences.get("food_preferences")
        if food:
            pref_parts.append(f"food: {', '.join(food[:3])}")
        acc = preferences.get("accommodation_preferences")
        if acc:
            pref_parts.append(f"accommodation: {', '.join(acc[:3])}")
        if pref_parts:
            parts.append("User preferences: " + " | ".join(pref_parts))

    return "\n".join(parts)


def place_matches_semantic_hints(place: dict, semantics: list[str]) -> bool:
    """Check if a place matches any of the semantic hints."""
    if not semantics:
        return True
    return any(place_matches_semantic_tag(place, tag) for tag in semantics)


# ── Main Dispatchers ───────────────────────────────────────────────────────────


def _apply_operation_state(state: ConversationState, operation: dict | BaseModel) -> ConversationState:
    """Dispatch an operation against a ConversationState (internal)."""
    op_data = operation
    if isinstance(op_data, BaseModel):
        op_data = op_data.model_dump()
    elif not isinstance(op_data, dict):
        logger.error("[Ops] Invalid operation type: %s", type(op_data).__name__)
        return state

    op = (op_data.get("op") or "").upper()
    logger.info("[Ops] Applying operation: %s")

    try:
        if op == "REMOVE":
            op_obj = RemoveOperation(**op_data)
            state = _exec_remove_state(state, op_obj)
        elif op == "SWAP":
            op_obj = SwapOperation(**op_data)
            state = _exec_swap_state(state, op_obj)
        elif op == "ADD":
            op_obj = AddOperation(**op_data)
            state = _exec_add_state(state, op_obj)
        elif op == "ADD_CATEGORY":
            op_obj = AddCategoryOperation(**op_data)
            state = _exec_add_category_state(state, op_obj)
        elif op == "EXCHANGE":
            op_obj = ExchangeOperation(**op_data)
            state = _exec_exchange_state(state, op_obj)
        elif op == "REORDER":
            op_obj = ReorderOperation(**op_data)
            state = _exec_reorder_state(state, op_obj)
        elif op == "RE_THEME":
            op_obj = ReThemeOperation(**op_data)
            state = _exec_retheme_state(state, op_obj)
        else:
            logger.warning("[Ops] Unknown operation: %s", op)
            return state

        if state.itinerary:
            state.itinerary = _rebalance_clustered_slots(state.itinerary)
            state = _fix_travel_times(state)

    except Exception as exc:
        logger.error("[Ops] Failed to apply operation %s: %s", op, exc)

    return state


# ── Public API (dual dispatch) ─────────────────────────────────────────────────


def apply_operation(
    itinerary: dict | ConversationState,
    operation: ModifierResponse | BaseModel | dict | None = None,
    place_pool: list[dict] | None = None,
) -> dict | ConversationState:
    """Apply an itinerary modification operation.

    Supports both calling conventions:

    **New-style (ConversationState-based)**:
        apply_operation(state=ConversationState, operation=dict|BaseModel) -> ConversationState

    **Old-style (dict-based, for modifier agent + tests)**:
        apply_operation(itinerary=dict, operation=ModifierResponse, place_pool=list) -> dict

    Args:
        itinerary: Either a ConversationState or an itinerary dict.
        operation: The operation to apply (ModifierResponse, BaseModel, or dict).
        place_pool: Pool of available places (only used in old-style dict mode).

    Returns:
        The updated ConversationState or itinerary dict.
    """
    # Detect calling convention
    if isinstance(itinerary, ConversationState):
        # New-style: state-based
        return _apply_operation_state(itinerary, operation or {})

    # Old-style: dict-based
    op = operation

    if itinerary is None:
        return None
    if op is None:
        return itinerary

    # Convert ModifierResponse to op_data
    if isinstance(op, ModifierResponse):
        op = op.model_dump()
    elif isinstance(op, BaseModel):
        op = op.model_dump()
    elif not isinstance(op, dict):
        logger.error("[Ops] Invalid operation type: %s", type(op).__name__)
        return copy.deepcopy(itinerary)

    op = dict(op)  # make a mutable copy
    op_code = (op.get("op") or "").upper()
    logger.info("[Ops] Applying operation (dict-mode): %s", op_code)

    pool = place_pool or []
    result = itinerary

    try:
        if op_code == "REMOVE":
            wrapper = ModifierResponse(**op)
            result = _exec_remove(itinerary, wrapper)
        elif op_code == "SWAP":
            wrapper = ModifierResponse(**op)
            result = _exec_swap(itinerary, wrapper, pool)
        elif op_code == "ADD":
            wrapper = ModifierResponse(**op)
            result = _exec_add(itinerary, wrapper, pool)
        elif op_code == "ADD_CATEGORY":
            wrapper = ModifierResponse(**op)
            result = _exec_add_category(itinerary, wrapper, pool)
        elif op_code == "EXCHANGE":
            wrapper = ModifierResponse(**op)
            result = _exec_exchange(itinerary, wrapper)
        elif op_code == "REORDER":
            wrapper = ModifierResponse(**op)
            result = _exec_reorder(itinerary, wrapper)
        elif op_code == "RE_THEME":
            wrapper = ModifierResponse(**op)
            result = _exec_retheme(itinerary, wrapper)
        elif op_code == "CHANGE_HOTEL":
            wrapper = ModifierResponse(**op)
            result = _exec_change_hotel(itinerary, wrapper, pool)
        else:
            logger.warning("[Ops] Unknown operation (dict-mode): %s", op_code)
            return copy.deepcopy(itinerary)

        # Rebalance after structural edit
        result = _rebalance_clustered_slots(result)

    except Exception as exc:
        logger.error("[Ops] Failed to apply operation %s: %s", op_code, exc)
        return copy.deepcopy(itinerary)

    return result
