"""
Delta-based Itinerary Operations — Pydantic schemas + executor functions.

Instead of asking the LLM to regenerate the entire itinerary JSON for every
modification request, we ask it to output a **tiny operation** like::

    {"op": "REMOVE", "place_id": "saladin_citadel"}

Then deterministic Python code applies the operation to the in-memory
itinerary dict.  This eliminates JSON formatting errors, reduces token
usage, and makes the modifier faster and more reliable.

Operation types:
    - REMOVE:      Delete a specific stop by ID
    - SWAP:        Replace one stop with another from the available pool
    - ADD:         Insert a new stop from the pool into a specific day/time
    - CHANGE_HOTEL: Replace or add a hotel from the pool
    - REORDER:     Change the order of stops within a day
    - RE_THEME:    Update a day's theme string
"""

from __future__ import annotations

import copy
import logging
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Operation Schemas — the LLM outputs exactly one of these via structured output
# ═══════════════════════════════════════════════════════════════════════════════


class RemoveOperation(BaseModel):
    """Delete a specific stop from the itinerary."""

    op: Literal["REMOVE"] = "REMOVE"
    place_id: str = Field(description="ID of the stop to remove")


class SwapOperation(BaseModel):
    """Replace one stop with a different place from the available pool."""

    op: Literal["SWAP"] = "SWAP"
    remove_place_id: str = Field(description="ID of the stop to remove")
    add_place_id: str = Field(description="ID of the new place from the available pool")
    day_number: int = Field(default=0, description="Day number where the swap occurs (1-based)")
    new_why_recommended: str = Field(
        default="",
        description="Updated reason why the new place fits the user's request",
    )


class AddOperation(BaseModel):
    """Insert a new stop from the available pool into a specific day/time."""

    op: Literal["ADD"] = "ADD"
    day_number: int = Field(description="Day number to add to (1-based)")
    suggested_time_of_day: Literal["morning", "afternoon", "evening"] = Field(
        description="Time slot for the new stop"
    )
    add_place_id: str = Field(description="ID of the new place from the available pool")
    why_recommended: str = Field(
        default="",
        description="Reason why this new stop fits the user's request",
    )


class ChangeHotelOperation(BaseModel):
    """Replace or add a hotel from the available pool."""

    op: Literal["CHANGE_HOTEL"] = "CHANGE_HOTEL"
    old_hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the hotel to replace. If null/empty, adds a new hotel.",
    )
    new_hotel_id: str = Field(description="ID of the new hotel from the available pool")
    why_recommended: str = Field(
        default="",
        description="Reason why this hotel fits the user's request",
    )


class ReorderOperation(BaseModel):
    """Change the order of stops within a day."""

    op: Literal["REORDER"] = "REORDER"
    day_number: int = Field(description="Day number to reorder (1-based)")
    new_order: List[str] = Field(
        description="Ordered list of place IDs representing the new stop sequence"
    )


class ReThemeOperation(BaseModel):
    """Update a day's theme string."""

    op: Literal["RE_THEME"] = "RE_THEME"
    day_number: int = Field(description="Day number to update (1-based)")
    new_theme: str = Field(description="New theme/title for the day")


# ── Discriminated union ───────────────────────────────────────────────────

ModifierOperation = Union[
    RemoveOperation,
    SwapOperation,
    AddOperation,
    ChangeHotelOperation,
    ReorderOperation,
    ReThemeOperation,
]


class ModifierResponse(BaseModel):
    """Structured response from the itinerary modifier LLM.

    The LLM outputs this via ``with_structured_output``. It contains
    the operation to apply plus a human-readable explanation note.
    """

    operation: Union[
        RemoveOperation,
        SwapOperation,
        AddOperation,
        ChangeHotelOperation,
        ReorderOperation,
        ReThemeOperation,
    ] = Field(
        discriminator="op",
        description="The operation to perform on the itinerary",
    )
    note: str = Field(
        default="",
        description="Brief human-readable explanation of changes made",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Executor functions — deterministic Python that manipulates the itinerary dict
# ═══════════════════════════════════════════════════════════════════════════════


def _find_day(itinerary: dict, day_number: int) -> Optional[dict]:
    """Find a day dict by ``day_number`` (1-based). Returns None if not found."""
    for day in itinerary.get("days", []):
        if day.get("day_number") == day_number:
            return day
    return None


def _find_stop_index(stops: list[dict], place_id: str) -> int:
    """Return the index of a stop with ``id == place_id``, or -1 if not found."""
    for i, stop in enumerate(stops):
        if stop.get("id") == place_id:
            return i
    return -1


def _remove_travel_time(stop: dict) -> None:
    """Remove travel-time fields from a stop (it's now the last stop)."""
    stop.pop("travel_time_to_next_minutes", None)
    stop.pop("transport_mode", None)


def _reattach_full_metadata(
    modified: dict,
    original: dict,
    place_pool: list[dict],
) -> None:
    """Reattach full place metadata for any newly introduced stops/hotels.

    New stops (added via SWAP or ADD) come from the LLM with only the
    compact fields (id, name, category, lat, lon, why_recommended, etc.).
    This function fills in the rich metadata (address, photos, phone,
    website, opening_hours, interest_tags, cuisine_type, etc.) from the
    original itinerary or the place pool.
    """
    # Build index of original stop IDs → full stop dict
    orig_stops: dict[str, dict] = {}
    for day in original.get("days", []):
        for stop in day.get("stops", []):
            sid = stop.get("id", "")
            if sid:
                orig_stops[sid] = stop

    # Build index of hotel IDs from original
    orig_hotels: dict[str, dict] = {}
    for hotel in original.get("accommodation_suggestions", []):
        hid = hotel.get("id", "")
        if hid:
            orig_hotels[hid] = hotel

    # Build index from place pool
    pool_index: dict[str, dict] = {}
    for p in (place_pool or []):
        pid = p.get("id", "")
        if pid:
            pool_index[pid] = p

    # Track IDs that were in the original itinerary (existing stops)
    used_ids = set(orig_stops.keys())
    used_hotel_ids = set(orig_hotels.keys())

    # Reattach metadata for stops
    for day in modified.get("days", []):
        for stop in day.get("stops", []):
            sid = stop.get("id", "")
            if not sid:
                continue

            # If this stop already existed, ensure its metadata is preserved
            if sid in orig_stops:
                full = orig_stops[sid]
                # NOTE: travel_time_to_next_minutes and transport_mode are NOT
                # reattached because they are position-dependent — executors
                # like _exec_reorder and _exec_remove manage them independently.
                for key in (
                    "cuisine_type", "interest_tags", "address", "maps_link",
                    "photos", "phone", "website", "price_level",
                    "opening_hours", "review_count", "rating",
                    "sub_category",
                ):
                    if key in full and key not in stop:
                        stop[key] = full[key]
            elif sid in pool_index and sid not in used_ids:
                # Newly introduced stop — copy full metadata from pool
                full = pool_index[sid]
                for key in (
                    "cuisine_type", "interest_tags", "address", "maps_link",
                    "photos", "phone", "website", "price_level",
                    "opening_hours", "review_count", "rating",
                    "sub_category",
                ):
                    if full.get(key) and not stop.get(key):
                        stop[key] = full[key]

    # Reattach metadata for hotels
    for hotel in modified.get("accommodation_suggestions", []):
        hid = hotel.get("id", "")
        if not hid:
            continue

        if hid in orig_hotels:
            full = orig_hotels[hid]
            for key in ("rating", "amenities", "accommodation_type",
                        "category", "price_level", "address", "photos"):
                if key in full and key not in hotel:
                    hotel[key] = full[key]
        elif hid in pool_index and hid not in used_hotel_ids:
            full = pool_index[hid]
            for key in ("rating", "amenities", "accommodation_type",
                        "category", "price_level", "address", "photos"):
                if full.get(key) and not hotel.get(key):
                    hotel[key] = full[key]


# ── Individual operation executors ─────────────────────────────────────────


def _exec_remove(itinerary: dict, op: RemoveOperation) -> dict:
    """Execute a REMOVE operation."""
    modified = copy.deepcopy(itinerary)
    removed = False

    for day in modified.get("days", []):
        stops = day.get("stops", [])
        idx = _find_stop_index(stops, op.place_id)
        if idx != -1:
            del stops[idx]

            # If we removed the last stop, clear travel time on the new last stop
            if idx == len(stops) and idx > 0:
                _remove_travel_time(stops[idx - 1])

            day["stops"] = stops
            removed = True
            logger.info(
                "[OperationExecutor] REMOVED stop %s from day %d",
                op.place_id, day.get("day_number"),
            )
            break

    if not removed:
        modified["_modifier_note"] = (
            f"Cannot apply REMOVE: '{op.place_id}' not found in any day"
        )
        logger.warning(
            "[OperationExecutor] REMOVE: stop %s not found in any day — added note",
            op.place_id,
        )

    return modified


def _exec_swap(itinerary: dict, op: SwapOperation, place_pool: list[dict]) -> dict:
    """Execute a SWAP operation — replace one stop with another place."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number)
    if day is None:
        logger.warning("[OperationExecutor] SWAP: day %d not found", op.day_number)
        return modified

    stops = day.get("stops", [])
    idx = _find_stop_index(stops, op.remove_place_id)
    if idx == -1:
        logger.warning("[OperationExecutor] SWAP: stop %s not found in day %d", op.remove_place_id, op.day_number)
        return modified

    # Find the new place in the pool
    new_place = None
    for p in (place_pool or []):
        if p.get("id") == op.add_place_id:
            new_place = p
            break

    if new_place is None:
        modified["_modifier_note"] = (
            f"Cannot apply SWAP: '{op.add_place_id}' not found in available pool"
        )
        logger.warning(
            "[OperationExecutor] SWAP: place %s not found in pool — added note",
            op.add_place_id,
        )
        return modified

    # Save the travel time from the old stop (if any)
    old_travel_time = stops[idx].get("travel_time_to_next_minutes")
    old_transport = stops[idx].get("transport_mode")

    # Build the new stop entry from the place pool data
    new_stop = {
        "id": new_place.get("id", op.add_place_id),
        "name": new_place.get("name", ""),
        "category": new_place.get("category", ""),
        "sub_category": new_place.get("sub_category", new_place.get("subcategory", "")),
        "lat": new_place.get("lat", 0),
        "lon": new_place.get("lon", 0),
        "cuisine_type": new_place.get("cuisine_type"),
        "interest_tags": new_place.get("interest_tags", []),
        "why_recommended": op.new_why_recommended or new_place.get("why_recommended", ""),
        "estimated_duration_minutes": new_place.get("estimated_duration_minutes")
            or new_place.get("duration_minutes", 60),
        "suggested_time_of_day": stops[idx].get("suggested_time_of_day", "morning"),
    }

    # Carry over travel time from the old stop if the new stop isn't last
    if old_travel_time is not None:
        new_stop["travel_time_to_next_minutes"] = old_travel_time
        new_stop["transport_mode"] = old_transport or "driving"

    stops[idx] = new_stop
    day["stops"] = stops

    logger.info(
        "[OperationExecutor] SWAPPED %s → %s in day %d",
        op.remove_place_id, op.add_place_id, op.day_number,
    )

    return modified


def _exec_add(itinerary: dict, op: AddOperation, place_pool: list[dict]) -> dict:
    """Execute an ADD operation — insert a new stop into a specific day/time."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number)
    if day is None:
        logger.warning("[OperationExecutor] ADD: day %d not found", op.day_number)
        return modified

    # Find the new place in the pool
    new_place = None
    for p in (place_pool or []):
        if p.get("id") == op.add_place_id:
            new_place = p
            break

    if new_place is None:
        modified["_modifier_note"] = (
            f"Cannot apply ADD: '{op.add_place_id}' not found in available pool"
        )
        logger.warning(
            "[OperationExecutor] ADD: place %s not found in pool — added note",
            op.add_place_id,
        )
        return modified

    new_stop = {
        "id": new_place.get("id", op.add_place_id),
        "name": new_place.get("name", ""),
        "category": new_place.get("category", ""),
        "sub_category": new_place.get("sub_category", new_place.get("subcategory", "")),
        "lat": new_place.get("lat", 0),
        "lon": new_place.get("lon", 0),
        "cuisine_type": new_place.get("cuisine_type"),
        "interest_tags": new_place.get("interest_tags", []),
        "why_recommended": op.why_recommended or new_place.get("why_recommended", ""),
        "estimated_duration_minutes": new_place.get("estimated_duration_minutes")
            or new_place.get("duration_minutes", 60),
        "suggested_time_of_day": op.suggested_time_of_day,
    }

    # Decide where to insert based on time of day
    stops = day.get("stops", [])
    time_order = {"morning": 0, "afternoon": 1, "evening": 2}
    target_rank = time_order.get(op.suggested_time_of_day, 1)

    insert_idx = len(stops)  # default: append
    for i, s in enumerate(stops):
        s_rank = time_order.get(s.get("suggested_time_of_day", ""), 1)
        if s_rank > target_rank:
            insert_idx = i
            break
        elif s_rank == target_rank:
            # Insert after the last stop with the same time slot
            insert_idx = i + 1

    stops.insert(insert_idx, new_stop)

    # If stop was inserted NOT at the end, the previous stop now needs
    # a travel time to the new stop (set it to a reasonable default)
    if insert_idx > 0:
        prev_stop = stops[insert_idx - 1]
        if "travel_time_to_next_minutes" not in prev_stop:
            prev_stop["travel_time_to_next_minutes"] = 10.0
            prev_stop["transport_mode"] = "driving"

    # Remove travel time from the new last stop if it's now last
    if insert_idx == len(stops) - 1:
        _remove_travel_time(new_stop)

    day["stops"] = stops

    logger.info(
        "[OperationExecutor] ADDED %s to day %d (%s slot)",
        op.add_place_id, op.day_number, op.suggested_time_of_day,
    )

    return modified


def _exec_change_hotel(itinerary: dict, op: ChangeHotelOperation, place_pool: list[dict]) -> dict:
    """Execute a CHANGE_HOTEL operation — replace or add a hotel."""
    modified = copy.deepcopy(itinerary)

    # Find the new hotel in the pool
    new_hotel = None
    for p in (place_pool or []):
        if p.get("id") == op.new_hotel_id:
            new_hotel = p
            break

    if new_hotel is None:
        modified["_modifier_note"] = (
            f"Cannot apply CHANGE_HOTEL: '{op.new_hotel_id}' not found in available pool"
        )
        logger.warning(
            "[OperationExecutor] CHANGE_HOTEL: hotel %s not found in pool — added note",
            op.new_hotel_id,
        )
        return modified

    new_entry = {
        "id": new_hotel.get("id", op.new_hotel_id),
        "name": new_hotel.get("name", ""),
        "sub_category": new_hotel.get("sub_category", new_hotel.get("subcategory", "")),
        "accommodation_type": new_hotel.get("accommodation_type", ""),
        "lat": new_hotel.get("lat", 0),
        "lon": new_hotel.get("lon", 0),
        "rating": new_hotel.get("rating", 0),
        "why_recommended": op.why_recommended or new_hotel.get("why_recommended", ""),
        "amenities": new_hotel.get("amenities", []),
    }

    hotels = modified.get("accommodation_suggestions", [])

    if op.old_hotel_id:
        # Replace a specific hotel
        replaced = False
        for i, h in enumerate(hotels):
            if h.get("id") == op.old_hotel_id:
                hotels[i] = new_entry
                replaced = True
                logger.info(
                    "[OperationExecutor] CHANGED hotel %s → %s",
                    op.old_hotel_id, op.new_hotel_id,
                )
                break
        if not replaced:
            logger.warning(
                "[OperationExecutor] CHANGE_HOTEL: old hotel %s not found — appending",
                op.old_hotel_id,
            )
            hotels.append(new_entry)
    else:
        # Add a new hotel
        hotels.append(new_entry)
        logger.info("[OperationExecutor] ADDED hotel %s", op.new_hotel_id)

    modified["accommodation_suggestions"] = hotels
    return modified


def _exec_reorder(itinerary: dict, op: ReorderOperation) -> dict:
    """Execute a REORDER operation — reorder stops within a day."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number)
    if day is None:
        logger.warning("[OperationExecutor] REORDER: day %d not found", op.day_number)
        return modified

    stops = day.get("stops", [])
    # Build index of existing stops by ID
    stop_index: dict[str, dict] = {s.get("id", ""): s for s in stops}

    # Validate that all IDs in new_order exist
    missing = [pid for pid in op.new_order if pid not in stop_index]
    if missing:
        logger.warning(
            "[OperationExecutor] REORDER: place IDs %s not found in day %d — skipping",
            missing, op.day_number,
        )
        return modified

    # Reorder according to new_order
    reordered = [stop_index[pid] for pid in op.new_order]

    # Fix travel times — each stop except the last gets a travel time
    for i, s in enumerate(reordered):
        if i < len(reordered) - 1:
            # Keep existing travel time if available, otherwise default
            if "travel_time_to_next_minutes" not in s:
                s["travel_time_to_next_minutes"] = 10.0
                s["transport_mode"] = "driving"
        else:
            _remove_travel_time(s)

    # Update time-of-day suggestions based on position
    time_slots = ["morning", "afternoon", "evening"]
    for i, s in enumerate(reordered):
        slot_idx = min(i, len(time_slots) - 1)
        s["suggested_time_of_day"] = time_slots[slot_idx]

    day["stops"] = reordered

    logger.info(
        "[OperationExecutor] REORDERED day %d: %s",
        op.day_number, [s.get("id", "?") for s in reordered],
    )

    return modified


def _exec_retheme(itinerary: dict, op: ReThemeOperation) -> dict:
    """Execute a RE_THEME operation — update a day's theme."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number)
    if day is None:
        logger.warning("[OperationExecutor] RE_THEME: day %d not found", op.day_number)
        return modified

    day["theme"] = op.new_theme
    logger.info("[OperationExecutor] RE_THEME day %d → '%s'", op.day_number, op.new_theme)
    return modified


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def apply_operation(
    itinerary: dict,
    operation: ModifierOperation,
    place_pool: list[dict] | None = None,
) -> dict:
    """Apply a modifier operation to an itinerary and return the result.

    This is the main entry point.  It dispatches to the correct executor
    based on the operation type, then runs post-processing (metadata
    reattachment) on the result.

    Args:
        itinerary: The current itinerary dict (kept unchanged — a deep
            copy is made internally).
        operation: One of the ``*Operation`` Pydantic models.
        place_pool: Full place pool used to fill in rich metadata for
            newly introduced stops/hotels.

    Returns:
        A new modified itinerary dict with the operation applied.
    """
    if not itinerary or not operation:
        return itinerary

    # Dispatch to the correct executor
    op_type = operation.op

    if op_type == "REMOVE":
        modified = _exec_remove(itinerary, operation)
    elif op_type == "SWAP":
        modified = _exec_swap(itinerary, operation, place_pool or [])
    elif op_type == "ADD":
        modified = _exec_add(itinerary, operation, place_pool or [])
    elif op_type == "CHANGE_HOTEL":
        modified = _exec_change_hotel(itinerary, operation, place_pool or [])
    elif op_type == "REORDER":
        modified = _exec_reorder(itinerary, operation)
    elif op_type == "RE_THEME":
        modified = _exec_retheme(itinerary, operation)
    else:
        logger.warning("[OperationExecutor] Unknown operation type: %s", op_type)
        return copy.deepcopy(itinerary)

    # Reattach full metadata for any newly introduced stops/hotels
    _reattach_full_metadata(modified, itinerary, place_pool or [])

    return modified


# ═══════════════════════════════════════════════════════════════════════════════
# Category Detection & Pool Reordering
# ═══════════════════════════════════════════════════════════════════════════════


_CATEGORY_KEYWORDS: dict[str, tuple[str | None, str | None]] = {
    # Attractions by subcategory
    "museum": ("attraction", "museums"),
    "park": ("attraction", "parks"),
    "shopping": ("attraction", "shopping"),
    "nightlife": ("attraction", "nightlife"),
    "history": ("attraction", "history"),
    "nature": ("attraction", "nature"),
    "religious": ("attraction", "religious"),
    "sightseeing": ("attraction", "sightseeing"),
    "sports": ("attraction", "sports"),
    "wellness": ("attraction", "wellness"),
    "entertainment": ("attraction", "entertainment"),
    "family": ("attraction", "family"),
    "beach": ("attraction", "nature"),
    "garden": ("attraction", "parks"),
    # Restaurants
    "restaurant": ("restaurant", None),
    "food": ("restaurant", None),
    "eat": ("restaurant", None),
    "breakfast": ("restaurant", None),
    "lunch": ("restaurant", None),
    "dinner": ("restaurant", None),
    "cafe": ("restaurant", None),
    "coffee": ("restaurant", None),
    "bakery": ("restaurant", None),
    "street food": ("restaurant", None),
    # Hotels
    "hotel": ("hotel", None),
    "accommodation": ("hotel", None),
    "stay": ("hotel", None),
    "lodge": ("hotel", None),
    "hostel": ("hotel", None),
    "resort": ("hotel", None),
}


def _detect_category_hints(modification_request: str) -> dict[str, str]:
    """Detect category/subcategory hints from the user's modification request.

    Uses keyword matching to determine what type of place the user is
    asking about.  The hints are used to promote matching places to the
    front of the pool so they survive the ``max_places`` cap.

    Example::
        >>> _detect_category_hints("add a museum to day 2")
        {'category': 'attraction', 'sub_category': 'museums'}

        >>> _detect_category_hints("change the hotel")
        {'category': 'hotel'}
    """
    request_lower = modification_request.lower()
    for keyword, (cat, subcat) in _CATEGORY_KEYWORDS.items():
        if keyword in request_lower:
            result: dict[str, str] = {}
            if cat:
                result["category"] = cat
            if subcat:
                result["sub_category"] = subcat
            return result
    return {}


def _reorder_pool_by_category(
    fresh_pool: list[dict],
    category_hints: dict[str, str],
) -> list[dict]:
    """Reorder the place pool so places matching *category_hints* come first.

    Places matching both category AND subcategory (if specified) are
    promoted to the front.  This ensures relevant places survive the
    ``max_places`` cap.
    """
    if not category_hints:
        return fresh_pool

    cat = category_hints.get("category")
    subcat = category_hints.get("sub_category")

    matching: list[dict] = []
    non_matching: list[dict] = []

    for p in fresh_pool:
        p_cat = p.get("category", "").lower()
        p_subcat = p.get("sub_category", p.get("subcategory", "")).lower()

        match = True
        if cat and p_cat != cat:
            match = False
        if subcat and p_subcat != subcat:
            match = False
        if match:
            matching.append(p)
        else:
            non_matching.append(p)

    if matching:
        label = subcat or cat or "matching"
        logger.info(
            "[CategoryReorder] '%s' — %d matching place(s) out of %d",
            label, len(matching), len(fresh_pool),
        )

    return matching + non_matching


# ═══════════════════════════════════════════════════════════════════════════════
# Compact Context Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_compact_context(
    itinerary: dict,
    modification_request: str,
    available_places: list[dict] | None = None,
    preferences: dict | None = None,
    max_places: int = 30,
) -> str:
    """Build a compact textual context for the LLM modifier prompt.

    Instead of sending the full itinerary JSON (6000+ chars) and full
    place pool (8000+ chars), this builds a stripped-down summary that
    gives the LLM just enough information to decide what operation to
    perform.

    Args:
        itinerary: The current itinerary dict.
        modification_request: The user's edit request.
        available_places: Pool of candidate places.
        preferences: Optional user preferences dict.
        max_places: Maximum number of places to include in the context.

    Returns:
        A compact text string that fits easily within the LLM's context.
    """
    lines: list[str] = []

    # ── Modification request ──────────────────────────────────────────
    lines.append(f"User request: {modification_request}")
    lines.append("")

    # ── Day-by-day summary ────────────────────────────────────────────
    num_hotels = len(itinerary.get('accommodation_suggestions', []))
    lines.append(f"Itinerary: {itinerary.get('destination', '?')}, "
                 f"{itinerary.get('duration_days', '?')} days, "
                 f"{num_hotels} hotels")
    for day in itinerary.get("days", []):
        stops_desc = ", ".join(
            f"{s.get('name', '?')} ({s.get('id', '')})"
            for s in day.get("stops", [])
        )
        lines.append(
            f"  Day {day.get('day_number')} — {day.get('theme', 'No theme')}: {stops_desc}"
        )
    lines.append("")

    # ── Hotels ────────────────────────────────────────────────────────
    hotels = itinerary.get("accommodation_suggestions", [])
    if hotels:
        lines.append("Hotels:")
        for h in hotels:
            lines.append(f"  • {h.get('name', '?')} ({h.get('id', '')}) — "
                         f"{h.get('accommodation_type', 'hotel')}, "
                         f"rating {h.get('rating', '?')}")
        lines.append("")

    # ── Available places (trimmed) ────────────────────────────────────
    # Remove places already in the itinerary
    used_ids = set()
    for day in itinerary.get("days", []):
        for s in day.get("stops", []):
            used_ids.add(s.get("id", ""))
    for h in hotels:
        used_ids.add(h.get("id", ""))

    fresh_pool = [p for p in (available_places or []) if p.get("id", "") not in used_ids]

    # Detect category from the user's request and promote matching places
    # to the front so they survive the max_places cap.
    category_hints = _detect_category_hints(modification_request)
    fresh_pool = _reorder_pool_by_category(fresh_pool, category_hints)

    pool_section = fresh_pool[:max_places]

    if pool_section:
        lines.append(f"Available places ({len(pool_section)} shown out of {len(fresh_pool)}):")
        for p in pool_section:
            parts = [
                f"  • {p.get('name', '?')} ({p.get('id', '')})",
                f"{p.get('category', '?')}",
            ]
            subcat = p.get("sub_category", p.get("subcategory", ""))
            if subcat:
                parts.append(subcat)
            if p.get("cuisine_type"):
                parts.append(p["cuisine_type"])
            rating = p.get("rating")
            if rating:
                parts.append(f"⭐{rating}")
            lines.append(", ".join(parts))
        lines.append("")

    # ── Preferences ───────────────────────────────────────────────────
    if preferences:
        pref_parts = []
        for key, label in [
            ("budget_level", "budget"),
            ("travel_style", "style"),
            ("pace", "pace"),
        ]:
            val = preferences.get(key)
            if val:
                pref_parts.append(f"{label}: {val}")
        for key, label in [
            ("interests", "interests"),
            ("food_preferences", "food"),
            ("accommodation_preferences", "accommodation"),
        ]:
            vals = preferences.get(key)
            if vals:
                pref_parts.append(f"{label}: {', '.join(vals)}")
        if pref_parts:
            lines.append(f"User preferences: {' | '.join(pref_parts)}")
            lines.append("")

    return "\n".join(lines)
