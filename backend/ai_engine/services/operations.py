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
    - EXCHANGE:    Swap time slots (and positions) between two existing stops
    - ADD:         Insert a new stop from the pool into a specific day/time
    - CHANGE_HOTEL: Replace or add a hotel from the pool
    - REORDER:     Change the order of stops within a day (preserves time slots)
    - RE_THEME:    Update a day's theme string
"""

from __future__ import annotations

import copy
import logging
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from ai_engine.constants import MODIFIER_POOL_DISPLAY
from ai_engine.tools.haversine import haversine

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


class ExchangeOperation(BaseModel):
    """Swap time slots and positions between two stops already in the itinerary."""

    op: Literal["EXCHANGE"] = "EXCHANGE"
    place_id_a: str = Field(description="ID of the first stop to exchange")
    place_id_b: str = Field(description="ID of the second stop to exchange")


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


class AddCategoryOperation(BaseModel):
    """Add places of a specific category from the available pool.

    Unlike ADD (which requires the LLM to pick a specific place_id),
    ADD_CATEGORY lets the system find and insert the best matching
    places deterministically.  The LLM only specifies the category
    and count; the executor handles selection and distribution.
    """

    op: Literal["ADD_CATEGORY"] = "ADD_CATEGORY"
    category: str = Field(
        description="Category to add (e.g. museum, restaurant, church, park, nightlife)"
    )
    count: int = Field(
        default=1,
        description="How many places of this category to add (system picks the best)",
    )
    day_number: Optional[int] = Field(
        default=None,
        description="Specific day to add to (1-based). None = auto-distribute across days.",
    )
    suggested_time_of_day: Optional[Literal["morning", "afternoon", "evening"]] = Field(
        default=None,
        description="Preferred time slot. None = auto-assign.",
    )


class AdditionalAdd(BaseModel):
    """An additional ADD operation within a multi-ADD response.

    Used when the LLM wants to add more than one place in a single response
    (e.g. "add churches" → add Hanging Church + St. George's Church).
    """

    add_place_id: str = Field(description="ID of the new place from the available pool")
    day_number: int = Field(description="Day number to add to (1-based)")
    suggested_time_of_day: Literal["morning", "afternoon", "evening"] = Field(
        description="Time slot for the new stop"
    )
    why_recommended: str = Field(
        default="",
        description="Reason why this new stop fits the user's request",
    )


class ModifierResponse(BaseModel):
    """Structured response from the itinerary modifier LLM.

    Uses a **flat schema** (no discriminated union) so that ANY operation
    name from the LLM is accepted without a Pydantic ValidationError.
    Unknown operation names fall through to ``apply_operation``'s ``else``
    branch, which logs a warning and returns the original itinerary
    unchanged — much more graceful than crashing.

    The ``@model_validator`` also accepts the old nested format
    ``{"operation": SwapOperation(...), "note": "..."}`` for backward
    compatibility with existing test code.

    For multi-ADD responses (e.g. "add several churches"), the LLM sets
    ``op="ADD"`` and fills in the primary ``add_place_id``, then adds
    extras via the ``additional_adds`` list.  The executor applies all of
    them sequentially.
    """

    op: str = Field(description="The operation to perform")
    note: str = Field(
        default="",
        description="Brief human-readable explanation of changes made",
    )
    additional_adds: List[AdditionalAdd] = Field(
        default_factory=list,
        description="Extra ADD operations when the user wants multiple places of a type "
        "(e.g. 'add churches' → primary ADD + additional_adds). "
        "Each entry specifies place_id, day_number, time_of_day, and why_recommended. "
        "Leave empty for single-ADD or non-ADD operations.",
    )

    # ── All fields from all operation types, all optional ──────────────
    place_id: Optional[str] = Field(
        default=None,
        description="ID of the stop to remove (REMOVE)",
    )
    remove_place_id: Optional[str] = Field(
        default=None,
        description="ID of the stop to remove (SWAP)",
    )
    add_place_id: Optional[str] = Field(
        default=None,
        description="ID of the new place from the available pool (SWAP, ADD)",
    )
    day_number: Optional[int] = Field(
        default=None,
        description="Day number (1-based) (SWAP, ADD, REORDER, RE_THEME)",
    )
    new_order: Optional[List[str]] = Field(
        default=None,
        description="Ordered list of place IDs representing the new stop sequence (REORDER)",
    )
    new_why_recommended: Optional[str] = Field(
        default=None,
        description="Updated recommendation reason for the new place (SWAP)",
    )
    suggested_time_of_day: Optional[Literal["morning", "afternoon", "evening"]] = Field(
        default=None,
        description="Best time of day for this stop (ADD)",
    )
    why_recommended: Optional[str] = Field(
        default=None,
        description="Reason why this new stop/hotel fits the user's request (ADD, CHANGE_HOTEL)",
    )
    old_hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the hotel to replace. If None, adds a new hotel (CHANGE_HOTEL)",
    )
    new_hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the new hotel from the available pool (CHANGE_HOTEL)",
    )
    # ── ADD_CATEGORY fields ──────────────────────────────────────────
    category: Optional[str] = Field(
        default=None,
        description="Category to add (ADD_CATEGORY)",
    )
    count: Optional[int] = Field(
        default=None,
        description="How many places of this category to add (ADD_CATEGORY)",
    )
    new_theme: Optional[str] = Field(
        default=None,
        description="New theme/title for the day (RE_THEME)",
    )
    place_id_a: Optional[str] = Field(
        default=None,
        description="ID of the first stop to exchange (EXCHANGE)",
    )
    place_id_b: Optional[str] = Field(
        default=None,
        description="ID of the second stop to exchange (EXCHANGE)",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, data: dict) -> dict:
        """Accept both flat and nested operation formats.

        The LLM outputs flat format:
            ``{"op": "REORDER", "day_number": 1, "new_order": [...], "note": "..."}``

        The test code uses nested format:
            ``{"operation": SwapOperation(...), "note": "..."}``

        This validator flattens the nested format into the flat format
        so the rest of the code always works with a flat response.
        """
        if isinstance(data, dict):
            op = data.get("operation")
            if op is not None and not isinstance(op, str):
                # Unpack nested operation (Pydantic model or dict)
                op_data = op.model_dump() if hasattr(op, "model_dump") else op
                if isinstance(op_data, dict):
                    for k, v in op_data.items():
                        if k not in data:
                            data[k] = v
                data.pop("operation", None)
        return data


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


def _find_stop_location(
    itinerary: dict,
    place_id: str,
) -> tuple[Optional[dict], int, Optional[dict]]:
    """Find a stop by ID. Returns (day_dict, stop_index, stop_dict) or (None, -1, None)."""
    for day in itinerary.get("days", []):
        stops = day.get("stops", [])
        idx = _find_stop_index(stops, place_id)
        if idx != -1:
            return day, idx, stops[idx]
    return None, -1, None


_TIME_RANK = {"morning": 0, "afternoon": 1, "evening": 2}
_AVAILABLE_SLOTS = ["morning", "afternoon", "evening"]


def _time_rank(slot: str) -> int:
    return _TIME_RANK.get(slot or "", 1)


def _sort_stops_by_time_slot(stops: list[dict]) -> list[dict]:
    """Sort stops by time-of-day while preserving relative order within the same slot."""
    indexed = list(enumerate(stops))
    indexed.sort(key=lambda pair: (_time_rank(pair[1].get("suggested_time_of_day", "")), pair[0]))
    return [stop for _, stop in indexed]


def _fix_travel_times(stops: list[dict]) -> None:
    """Ensure travel-time fields are consistent for an ordered stop list."""
    for i, stop in enumerate(stops):
        if i < len(stops) - 1:
            if "travel_time_to_next_minutes" not in stop:
                stop["travel_time_to_next_minutes"] = 10.0
                stop["transport_mode"] = "driving"
        else:
            _remove_travel_time(stop)


def _insert_stop_by_time_slot(stops: list[dict], new_stop: dict) -> list[dict]:
    """Insert *new_stop* into *stops* at the position matching its time slot."""
    time_slot = new_stop.get("suggested_time_of_day", "afternoon")
    target_rank = _time_rank(time_slot)

    insert_idx = len(stops)
    for i, s in enumerate(stops):
        s_rank = _time_rank(s.get("suggested_time_of_day", ""))
        if s_rank > target_rank:
            insert_idx = i
            break
        if s_rank == target_rank:
            insert_idx = i + 1

    updated = list(stops)
    updated.insert(insert_idx, new_stop)
    return updated


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
    website, opening_hours, cuisine_type, etc.) from the
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
                    "cuisine_type", "address", "maps_link",
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
                    "cuisine_type", "address", "maps_link",
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


def _exec_remove(itinerary: dict, op: ModifierResponse) -> dict:
    """Execute a REMOVE operation."""
    modified = copy.deepcopy(itinerary)
    
    # Validate required field
    if not op.place_id:
        modified["_modifier_note"] = "Cannot apply REMOVE: missing required field 'place_id'"
        logger.warning("[OperationExecutor] REMOVE: missing place_id")
        return modified
    
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


def _exec_swap(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Execute a SWAP operation — replace one stop with another place."""
    modified = copy.deepcopy(itinerary)
    
    # Validate required fields
    if not op.remove_place_id:
        modified["_modifier_note"] = "Cannot apply SWAP: missing required field 'remove_place_id'"
        logger.warning("[OperationExecutor] SWAP: missing remove_place_id")
        return modified
    
    if not op.add_place_id:
        modified["_modifier_note"] = "Cannot apply SWAP: missing required field 'add_place_id'"
        logger.warning("[OperationExecutor] SWAP: missing add_place_id")
        return modified
    
    if not op.day_number or op.day_number <= 0:
        modified["_modifier_note"] = "Cannot apply SWAP: invalid or missing 'day_number'"
        logger.warning("[OperationExecutor] SWAP: invalid day_number %s", op.day_number)
        return modified
    
    day = _find_day(modified, op.day_number)
    if day is None:
        modified["_modifier_note"] = f"Cannot apply SWAP: day {op.day_number} not found in itinerary"
        logger.warning("[OperationExecutor] SWAP: day %d not found", op.day_number)
        return modified

    stops = day.get("stops", [])
    idx = _find_stop_index(stops, op.remove_place_id)
    if idx == -1:
        modified["_modifier_note"] = f"Cannot apply SWAP: stop '{op.remove_place_id}' not found in day {op.day_number}"
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


def _exec_add(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Execute an ADD operation — insert a new stop into a specific day/time."""
    modified = copy.deepcopy(itinerary)
    
    # Validate required fields
    if not op.add_place_id:
        modified["_modifier_note"] = "Cannot apply ADD: missing required field 'add_place_id'"
        logger.warning("[OperationExecutor] ADD: missing add_place_id")
        return modified
    
    if not op.day_number or op.day_number <= 0:
        modified["_modifier_note"] = "Cannot apply ADD: invalid or missing 'day_number'"
        logger.warning("[OperationExecutor] ADD: invalid day_number %s", op.day_number)
        return modified
    
    day = _find_day(modified, op.day_number)
    if day is None:
        modified["_modifier_note"] = f"Cannot apply ADD: day {op.day_number} not found in itinerary"
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

    time_slot = op.suggested_time_of_day or "afternoon"
    new_stop = {
        "id": new_place.get("id", op.add_place_id),
        "name": new_place.get("name", ""),
        "category": new_place.get("category", ""),
        "sub_category": new_place.get("sub_category", new_place.get("subcategory", "")),
        "lat": new_place.get("lat", 0),
        "lon": new_place.get("lon", 0),
        "cuisine_type": new_place.get("cuisine_type"),
        "why_recommended": op.why_recommended or new_place.get("why_recommended", ""),
        "estimated_duration_minutes": new_place.get("estimated_duration_minutes")
            or new_place.get("duration_minutes", 60),
        "suggested_time_of_day": time_slot,
    }
    stops = _insert_stop_by_time_slot(day.get("stops", []), new_stop)
    _fix_travel_times(stops)
    day["stops"] = stops

    logger.info(
        "[OperationExecutor] ADDED %s to day %d (%s slot)",
        op.add_place_id, op.day_number, time_slot,
    )

    return modified


def _exec_change_hotel(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Execute a CHANGE_HOTEL operation — replace or add a hotel."""
    modified = copy.deepcopy(itinerary)
    
    # Validate required field
    if not op.new_hotel_id:
        modified["_modifier_note"] = "Cannot apply CHANGE_HOTEL: missing required field 'new_hotel_id'"
        logger.warning("[OperationExecutor] CHANGE_HOTEL: missing new_hotel_id")
        return modified

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


def _exec_reorder(itinerary: dict, op: ModifierResponse) -> dict:
    """Execute a REORDER operation — reorder stops within a day."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number or 0)
    if day is None:
        logger.warning("[OperationExecutor] REORDER: day %d not found", op.day_number)
        return modified

    stops = day.get("stops", [])
    # Build index of existing stops by ID
    stop_index: dict[str, dict] = {s.get("id", ""): s for s in stops}

    new_order = op.new_order or []
    # Validate that all IDs in new_order exist
    missing = [pid for pid in new_order if pid not in stop_index]
    if missing:
        logger.warning(
            "[OperationExecutor] REORDER: place IDs %s not found in day %d — skipping",
            missing, op.day_number,
        )
        return modified

    # Reorder according to new_order (preserve each stop's time slot)
    reordered = [stop_index[pid] for pid in new_order]
    _fix_travel_times(reordered)

    day["stops"] = reordered

    logger.info(
        "[OperationExecutor] REORDERED day %d: %s",
        op.day_number, [s.get("id", "?") for s in reordered],
    )

    return modified


def _exec_exchange(itinerary: dict, op: ModifierResponse) -> dict:
    """Exchange time slots and positions between two existing stops."""
    modified = copy.deepcopy(itinerary)
    place_a = op.place_id_a
    place_b = op.place_id_b

    if not place_a or not place_b:
        modified["_modifier_note"] = "Cannot apply EXCHANGE: place_id_a and place_id_b are required"
        logger.warning("[OperationExecutor] EXCHANGE: missing place IDs")
        return modified

    if place_a == place_b:
        modified["_modifier_note"] = "Cannot apply EXCHANGE: both place IDs are the same"
        return modified

    day_a, idx_a, stop_a = _find_stop_location(modified, place_a)
    day_b, idx_b, stop_b = _find_stop_location(modified, place_b)

    if day_a is None or day_b is None:
        missing = [pid for pid, loc in ((place_a, day_a), (place_b, day_b)) if loc is None]
        modified["_modifier_note"] = f"Cannot apply EXCHANGE: stop(s) not found: {', '.join(missing)}"
        logger.warning("[OperationExecutor] EXCHANGE: stop(s) not found: %s", missing)
        return modified

    slot_a = stop_a.get("suggested_time_of_day", "morning")
    slot_b = stop_b.get("suggested_time_of_day", "morning")
    stop_a["suggested_time_of_day"] = slot_b
    stop_b["suggested_time_of_day"] = slot_a

    if day_a is day_b:
        day_a["stops"] = _sort_stops_by_time_slot(day_a.get("stops", []))
        _fix_travel_times(day_a["stops"])
    else:
        day_num_a = day_a.get("day_number")
        day_num_b = day_b.get("day_number")

        day_a["stops"].pop(idx_a)
        day_b["stops"].pop(idx_b)

        day_a["stops"] = _insert_stop_by_time_slot(day_a.get("stops", []), stop_b)
        day_b["stops"] = _insert_stop_by_time_slot(day_b.get("stops", []), stop_a)
        _fix_travel_times(day_a["stops"])
        _fix_travel_times(day_b["stops"])

        logger.info(
            "[OperationExecutor] EXCHANGED %s (day %s) ↔ %s (day %s)",
            place_a, day_num_a, place_b, day_num_b,
        )
        return modified

    logger.info(
        "[OperationExecutor] EXCHANGED %s ↔ %s on day %d",
        place_a, place_b, day_a.get("day_number"),
    )
    return modified


def _exec_retheme(itinerary: dict, op: ModifierResponse) -> dict:
    """Execute a RE_THEME operation — update a day's theme."""
    modified = copy.deepcopy(itinerary)
    day = _find_day(modified, op.day_number or 0)
    if day is None:
        logger.warning("[OperationExecutor] RE_THEME: day %d not found", op.day_number)
        return modified

    day["theme"] = op.new_theme or ""
    logger.info("[OperationExecutor] RE_THEME day %d → '%s'", op.day_number, op.new_theme)
    return modified


# ── ADD_CATEGORY Executor ──────────────────────────────────────────────────


def _exec_add_category(itinerary: dict, op: ModifierResponse, place_pool: list[dict]) -> dict:
    """Execute an ADD_CATEGORY operation — find and insert places by category.

    The LLM specifies a category keyword (e.g. "museum", "church", "park") and
    an optional count.  This executor:

    1. Uses ``_detect_category_hints`` to map the keyword → DB category/subcategory
    2. Scans the pool for unused places matching that category
    3. Scores and selects the best ``count`` places
    4. Distributes them across days using ``_find_best_day_and_slot_for_place``

    Returns the modified itinerary, or the original with a ``_modifier_note``
    if no matching places were found.
    """
    modified = copy.deepcopy(itinerary)

    if not op.category:
        modified["_modifier_note"] = "Cannot apply ADD_CATEGORY: missing required field 'category'"
        logger.warning("[OperationExecutor] ADD_CATEGORY: missing category")
        return modified

    count = op.count or 1
    if count < 1:
        count = 1
    elif count > 5:
        count = 5  # cap at 5 to avoid overloading

    # Map category keyword → DB category/subcategory
    hints = _detect_category_hints(f"add {op.category}", pool=place_pool)
    if not hints:
        modified["_modifier_note"] = (
            f"Cannot apply ADD_CATEGORY: unknown category '{op.category}'"
        )
        logger.warning(
            "[OperationExecutor] ADD_CATEGORY: no hints for '%s'", op.category
        )
        return modified

    cats = hints.get("category", [])
    subcats = hints.get("sub_category", [])
    semantics = hints.get("semantic", [])

    # Collect unused place IDs
    used_ids: set[str] = set()
    for day in modified.get("days", []):
        for stop in day.get("stops", []):
            pid = stop.get("id", "")
            if pid:
                used_ids.add(pid)

    # Find matching places in the pool
    matching: list[dict] = []
    for p in (place_pool or []):
        pid = p.get("id", "")
        if not pid or pid in used_ids:
            continue
        p_cat = (p.get("category") or "").lower()
        p_sub = (p.get("sub_category") or p.get("subcategory") or "").lower()

        cat_match = not cats or p_cat in cats
        sub_match = not subcats or p_sub in subcats
        if cat_match and sub_match:
            if semantics and not place_matches_semantic_hints(p, semantics):
                continue
            matching.append(p)

    if not matching:
        modified["_modifier_note"] = (
            f"Cannot apply ADD_CATEGORY: no unused '{op.category}' places in pool"
        )
        logger.warning(
            "[OperationExecutor] ADD_CATEGORY: no matches for '%s' in pool",
            op.category,
        )
        return modified

    # Sort by rating descending, take top N
    matching.sort(key=lambda p: p.get("rating", 0) or 0, reverse=True)
    to_add = matching[:count]

    # Track used slots per day for batch distribution
    used_slots_per_day: dict[int, set[str]] = {}
    added_names: list[str] = []

    target_day_num = op.day_number
    target_slot = op.suggested_time_of_day

    for i, place in enumerate(to_add):
        if target_day_num and i == 0:
            best_day = target_day_num
            best_slot = target_slot or "afternoon"
        else:
            best_day, best_slot = _find_best_day_and_slot_for_place(
                modified, place, used_slots_per_day,
            )

        used_slots_per_day.setdefault(best_day, set()).add(best_slot)

        new_stop = {
            "id": place.get("id", ""),
            "name": place.get("name", ""),
            "category": place.get("category", ""),
            "sub_category": place.get("sub_category", place.get("subcategory", "")),
            "lat": place.get("lat", 0),
            "lon": place.get("lon", 0),
            "cuisine_type": place.get("cuisine_type"),
            "why_recommended": place.get(
                "why_recommended", f"Great {op.category} choice"
            ),
            "estimated_duration_minutes": place.get("estimated_duration_minutes")
                or place.get("duration_minutes", 60),
            "suggested_time_of_day": best_slot,
        }
        day = _find_day(modified, best_day)
        if day is None:
            logger.warning(
                "[OperationExecutor] ADD_CATEGORY: day %d not found — skipping",
                best_day,
            )
            continue

        stops = _insert_stop_by_time_slot(day.get("stops", []), new_stop)
        _fix_travel_times(stops)
        day["stops"] = stops
        added_names.append(place.get("name", "") or place.get("id", ""))

    if added_names:
        label = ", ".join(added_names)
        logger.info(
            "[OperationExecutor] ADD_CATEGORY '%s' → added %d place(s): %s",
            op.category, len(added_names), label,
        )
    else:
        modified["_modifier_note"] = (
            f"ADD_CATEGORY '{op.category}': no valid days to add to"
        )

    return modified


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════


def apply_operation(
    itinerary: dict,
    operation: ModifierResponse,
    place_pool: list[dict] | None = None,
) -> dict:
    """Apply a modifier operation to an itinerary and return the result.

    This is the main entry point.  It dispatches to the correct executor
    based on the operation type, then runs post-processing (metadata
    reattachment) on the result.

    Args:
        itinerary: The current itinerary dict (kept unchanged — a deep
            copy is made internally).
        operation: A parsed ``ModifierResponse`` with flat fields.
        place_pool: Full place pool used to fill in rich metadata for
            newly introduced stops/hotels.

    Returns:
        A new modified itinerary dict with the operation applied.
    """
    if not itinerary or not operation:
        return itinerary

    # Dispatch to the correct executor based on the operation name.
    # Unlike the old discriminated-union approach, this NEVER raises a
    # ValidationError — unknown op names fall through to the ``else``
    # branch which logs a warning and returns a deep copy unchanged.
    op_type = operation.op

    if op_type == "REMOVE":
        modified = _exec_remove(itinerary, operation)
    elif op_type == "SWAP":
        modified = _exec_swap(itinerary, operation, place_pool or [])
    elif op_type == "ADD":
        modified = _exec_add(itinerary, operation, place_pool or [])
    elif op_type == "ADD_CATEGORY":
        modified = _exec_add_category(itinerary, operation, place_pool or [])
    elif op_type == "CHANGE_HOTEL":
        modified = _exec_change_hotel(itinerary, operation, place_pool or [])
    elif op_type == "REORDER":
        modified = _exec_reorder(itinerary, operation)
    elif op_type == "EXCHANGE":
        modified = _exec_exchange(itinerary, operation)
    elif op_type == "RE_THEME":
        modified = _exec_retheme(itinerary, operation)
    else:
        logger.warning(
            "[OperationExecutor] Unknown operation type: '%s' — "
            "returning itinerary unchanged",
            op_type,
        )
        return copy.deepcopy(itinerary)

    # Reattach full metadata for any newly introduced stops/hotels
    _reattach_full_metadata(modified, itinerary, place_pool or [])

    return modified


# ═══════════════════════════════════════════════════════════════════════════════
# Category Detection & Pool Reordering
# ═══════════════════════════════════════════════════════════════════════════════


# ── English category aliases (words that map to different subcategory values) ──
# These cover common English travel terms whose mapping differs from the
# literal subcategory value in the database (e.g. "museum" → subcategory "museums",
# "church" → subcategory "religious").
#
# For subcategory values that DO match the user's word directly (e.g. "museums",
# "parks", "history", "religious"), the pool-derived map handles them automatically.

_ENGLISH_ALIAS_MAP: dict[str, tuple[str | None, str | None]] = {
    # Attraction English aliases (word ≠ subcategory value)
    "museum":      ("attraction", "museums"),
    "park":        ("attraction", "parks"),
    "garden":      ("attraction", "parks"),
    "beach":       ("attraction", "nature"),
    "shopping":      ("attraction", "shopping"),
    "nightlife":     ("attraction", "nightlife"),
    # Religious places — map to "religious" subcategory
    "church":      ("attraction", "religious"),
    "churches":    ("attraction", "religious"),
    "cathedral":   ("attraction", "religious"),
    "coptic":      ("attraction", "religious"),
    "mosque":      ("attraction", "religious"),
    "mosques":     ("attraction", "religious"),
    "synagogue":   ("attraction", "religious"),
    "temple":      ("attraction", "religious"),
    # Restaurants (generic — no subcategory needed)
    "restaurant":   ("restaurant", None),
    "food":         ("restaurant", None),
    "eat":          ("restaurant", None),
    "breakfast":    ("restaurant", None),
    "lunch":        ("restaurant", None),
    "dinner":       ("restaurant", None),
    "cafe":         ("restaurant", None),
    "coffee":       ("restaurant", None),
    "bakery":       ("restaurant", None),
    "street food":  ("restaurant", None),
    # Hotels (generic — no subcategory needed)
    "hotel":         ("hotel", None),
    "accommodation": ("hotel", None),
    "stay":          ("hotel", None),
    "lodge":         ("hotel", None),
    "hostel":        ("hotel", None),
    "resort":        ("hotel", None),
}

# Maps request keywords → canonical semantic tag for fine-grained pool filtering.
_SEMANTIC_KEYWORD_MAP: dict[str, str] = {
    "churches": "church",
    "church": "church",
    "cathedral": "church",
    "chapel": "church",
    "coptic": "church",
    "basilica": "church",
    "mosques": "mosque",
    "mosque": "mosque",
    "masjid": "mosque",
    "synagogues": "synagogue",
    "synagogue": "synagogue",
    "temples": "temple",
    "temple": "temple",
}

# Per-tag rules for matching places by name / tags (used when sub_category is too coarse).
_SEMANTIC_RULES: dict[str, dict[str, list[str]]] = {
    "church": {
        "include": ["church", "cathedral", "chapel", "coptic", "basilica", "monastery"],
        "exclude": ["mosque", "masjid"],
    },
    "mosque": {
        "include": ["mosque", "masjid"],
        "exclude": ["church", "cathedral", "chapel", "coptic", "synagogue"],
    },
    "synagogue": {
        "include": ["synagogue", "jewish"],
        "exclude": ["mosque", "church"],
    },
    "temple": {
        "include": ["temple", "shrine"],
        "exclude": [],
    },
}


def _place_search_text(place: dict) -> str:
    """Lowercase text blob used for semantic matching."""
    parts = [
        place.get("name") or "",
        place.get("sub_category") or place.get("subcategory") or "",
        "",  # interest_tags removed,
    ]
    return " ".join(parts).lower()


def place_matches_semantic_tag(place: dict, semantic_tag: str) -> bool:
    """Return True if *place* matches a canonical semantic tag (e.g. church vs mosque)."""
    rules = _SEMANTIC_RULES.get(semantic_tag)
    if not rules:
        return True

    name = (place.get("name") or "").lower()
    text = _place_search_text(place)

    for token in rules.get("exclude", []):
        if token in name:
            return False

    for token in rules.get("include", []):
        if token in text:
            return True

    return False


def place_matches_semantic_hints(place: dict, semantic_hints: list[str]) -> bool:
    """True when *place* matches at least one semantic hint (or hints are empty)."""
    if not semantic_hints:
        return True
    return any(place_matches_semantic_tag(place, tag) for tag in semantic_hints)


def filter_places_by_semantics(
    places: list[dict],
    semantic_hints: list[str],
) -> list[dict]:
    """Keep only places matching the requested semantic tags."""
    if not semantic_hints:
        return list(places)
    return [p for p in places if place_matches_semantic_hints(p, semantic_hints)]


def _detect_semantic_hints(modification_request: str) -> list[str]:
    """Detect fine-grained semantic tags (church, mosque, …) from the request."""
    request_lower = modification_request.lower()
    seen: set[str] = set()
    tags: list[str] = []

    for keyword in sorted(_SEMANTIC_KEYWORD_MAP.keys(), key=len, reverse=True):
        if keyword not in request_lower:
            continue
        tag = _SEMANTIC_KEYWORD_MAP[keyword]
        if tag not in seen:
            tags.append(tag)
            seen.add(tag)

    return tags


_SUBCATEGORY_SIMILARITY_THRESHOLD = 0.3


def _build_subcategory_texts(pool: list[dict]) -> dict[tuple[str, str], str]:
    """Build descriptive texts for each unique (category, subcategory) pair in the pool.

    Groups places by (category, subcategory) and for each group builds a text that
    includes the subcategory name, cuisine_types, and
    cuisine_types (for restaurants). The resulting text is used for embedding
    similarity comparison against user requests.

    Args:
        pool: List of place dicts with ``category``, ``sub_category``,
            and ``cuisine_type``.

    Returns:
        Dict mapping ``(category, subcategory)`` → descriptive text string.
    """
    groups: dict[tuple[str, str], dict[str, set]] = {}
    for p in pool:
        cat = (p.get("category") or "").strip().lower()
        sub = (p.get("sub_category") or p.get("subcategory") or "").strip().lower()
        if not cat and not sub:
            continue
        key = (cat, sub)
        if key not in groups:
            groups[key] = {"tags": set(), "cuisines": set(), "names": set()}
        # interest_tags removed from _build_subcategory_texts
        c = p.get("cuisine_type") or ""
        if c:
            groups[key]["cuisines"].add(c.lower())
        n = p.get("name") or ""
        if n:
            # Take first 2 meaningful words from the name
            words = [w for w in n.lower().split() if w not in ("the", "a", "an", "of", "in", "and", "&", "-")]
            if words:
                groups[key]["names"].add(" ".join(words[:2]))

    result: dict[tuple[str, str], str] = {}
    for (cat, sub), data in groups.items():
        parts = [f"category: {cat}", f"type: {sub}"]
        # tags/interest_tags omitted
        if data["cuisines"]:
            parts.append(f"cuisine: {', '.join(sorted(data['cuisines']))}")
        if data["names"]:
            parts.append(f"examples: {', '.join(sorted(data['names']))}")
        result[(cat, sub)] = ". ".join(parts)

    return result


async def _embedding_category_hints(
    modification_request: str,
    pool: list[dict] | None = None,
) -> dict[str, list[str]]:
    """Detect category hints via embedding similarity when keyword matching fails.

    Falls back to Gemini embeddings to find semantically similar subcategory values
    from the pool. Only runs when *pool* is provided and contains places.

    For each unique ``(category, subcategory)`` pair in the pool, builds a descriptive
    text (including interest_tags, cuisine_type, and example names), embeds both the
    request and the subcategory text, and returns hints for pairs where cosine
    similarity exceeds ``_SUBCATEGORY_SIMILARITY_THRESHOLD`` (0.3).

    The embedding text for each subcategory follows the same ``task: search result | query: ...``
    format used throughout the codebase for consistency.

    Args:
        modification_request: The user's modification text (e.g. "add shrines").
        pool: List of place dicts to derive subcategory texts from.

    Returns:
        Same format as ``_detect_category_hints`` — a dict with optional ``"category"``
        and ``"sub_category"`` keys mapping to lists.  Returns ``{}`` when no match
        is found or embeddings are unavailable.
    """
    if not pool:
        return {}

    subcat_texts = _build_subcategory_texts(pool)
    if not subcat_texts:
        return {}

    # Lazy import to avoid circular dependency at module level
    try:
        from ai_engine.services.embedding_service import cosine_similarity, embed_query_async
    except ImportError:
        logger.warning("[EmbeddingFallback] Could not import embedding service")
        return {}

    # Embed the request
    request_embedding = await embed_query_async(f"task: search result | query: find places matching: {modification_request}")
    if request_embedding is None:
        logger.info("[EmbeddingFallback] Request embedding failed — skipping")
        return {}

    # Embed each subcategory text and find matches
    seen_categories: set[str] = set()
    seen_subcategories: set[str] = set()
    result: dict[str, list[str]] = {}

    for (cat, sub), text in subcat_texts.items():
        subcat_embedding = await embed_query_async(f"task: search result | query: {text}")
        if subcat_embedding is None:
            continue

        sim = cosine_similarity(request_embedding, subcat_embedding)
        logger.debug(
            "[EmbeddingFallback] '%s' — %s/%s similarity=%.3f",
            modification_request[:40], cat, sub, sim,
        )

        if sim >= _SUBCATEGORY_SIMILARITY_THRESHOLD:
            if cat and cat not in seen_categories:
                result.setdefault("category", []).append(cat)
                seen_categories.add(cat)
            if sub and sub not in seen_subcategories:
                result.setdefault("sub_category", []).append(sub)
                seen_subcategories.add(sub)

    if result:
        label = ", ".join(result.get("sub_category", result.get("category", [])))
        logger.info(
            "[EmbeddingFallback] Found %d matching subcategories: %s (sim threshold=%.2f)",
            len(result.get("sub_category", [])), label, _SUBCATEGORY_SIMILARITY_THRESHOLD,
        )

    return result


def _extract_subcategories_from_pool(pool: list[dict]) -> dict[str, tuple[str | None, str | None]]:
    """Build a keyword map from the distinct subcategory values in the place pool.

    Each distinct ``sub_category`` value in the pool becomes a keyword that maps
    to its own category.  This makes the category detection automatically adapt
    to whatever subcategory values exist in each city's data (e.g. "shrines",
    "temples", "buddhist", "water sports") without any hardcoded mapping.

    Example, if the pool contains::

        [{"category": "attraction", "sub_category": "museums"}, ...]

    The map will include: ``{"museums": ("attraction", "museums"), ...}``

    Args:
        pool: List of place dicts with ``category`` and ``sub_category`` keys.

    Returns:
        A dict keyed by subcategory value (lowercase), mapping to
        ``(category, subcategory)`` tuples.
    """
    subcat_map: dict[str, tuple[str | None, str | None]] = {}
    for p in pool:
        sub = (p.get("sub_category") or "").strip().lower()
        cat = (p.get("category") or "").strip().lower()
        if sub:
            # Only set if not already present (first wins or skip)
            if sub not in subcat_map:
                subcat_map[sub] = (cat, sub)
        elif cat and cat not in subcat_map:
            # Places with no subcategory still contribute their category
            subcat_map[cat] = (cat, None)
    return subcat_map


def _detect_category_hints(
    modification_request: str,
    pool: list[dict] | None = None,
) -> dict[str, list[str]]:
    """Detect category/subcategory hints from the user's modification request.

    Uses two sources:
    1. ``_ENGLISH_ALIAS_MAP`` — hand-written English aliases for common terms
       (e.g. "museum" → subcategory "museums", "church" → "religious")
    2. ``pool`` — if provided, extracts distinct subcategory values from the
       pool so city-specific categories (e.g. "shrines", "water sports") are
       automatically matched without hardcoding.

    Collects ALL matching keywords (not just the first) so a request like
    "add a museum and a restaurant" promotes both types.  Duplicate
    categories/subcategories are deduplicated.

    The hints are used to promote matching places to the front of the pool
    so they survive the ``max_places`` cap.

    Example::
        >>> _detect_category_hints("add a museum to day 2", pool)
        {'category': ['attraction'], 'sub_category': ['museums']}

        >>> _detect_category_hints("change the hotel")
        {'category': ['hotel']}

        >>> _detect_category_hints("add a museum and a restaurant")
        {'category': ['attraction', 'restaurant'], 'sub_category': ['museums']}
    """
    request_lower = modification_request.lower()
    result: dict[str, list[str]] = {}
    seen_categories: set[str] = set()
    seen_subcategories: set[str] = set()

    # 1. Check English aliases
    for keyword, (cat, subcat) in _ENGLISH_ALIAS_MAP.items():
        if keyword in request_lower:
            if cat and cat not in seen_categories:
                result.setdefault("category", []).append(cat)
                seen_categories.add(cat)
            if subcat and subcat not in seen_subcategories:
                result.setdefault("sub_category", []).append(subcat)
                seen_subcategories.add(subcat)

    # 2. Check pool-derived subcategories (auto-detect city-specific values)
    if pool is not None:
        pool_map = _extract_subcategories_from_pool(pool)
        for keyword, (cat, subcat) in pool_map.items():
            if keyword in request_lower:
                if cat and cat not in seen_categories:
                    result.setdefault("category", []).append(cat)
                    seen_categories.add(cat)
                if subcat and subcat not in seen_subcategories:
                    result.setdefault("sub_category", []).append(subcat)
                    seen_subcategories.add(subcat)

    semantic = _detect_semantic_hints(modification_request)
    if semantic:
        result["semantic"] = semantic

    return result


def _reorder_pool_by_category(
    fresh_pool: list[dict],
    category_hints: dict[str, list[str]],
) -> list[dict]:
    """Reorder the place pool so places matching *category_hints* come first.

    ``category_hints`` is a dict with optional ``"category"`` and
    ``"sub_category"`` keys, each mapping to a **list** of accepted
    values (produced by ``_detect_category_hints``).

    Places matching ANY of the specified categories OR subcategories are
    promoted to the front.  This ensures relevant places survive the
    ``max_places`` cap.
    """
    if not category_hints:
        return fresh_pool

    cats: list[str] = category_hints.get("category", [])
    subcats: list[str] = category_hints.get("sub_category", [])
    semantics: list[str] = category_hints.get("semantic", [])

    semantic_match: list[dict] = []
    category_match: list[dict] = []
    non_matching: list[dict] = []

    for p in fresh_pool:
        p_cat = p.get("category", "").lower()
        p_subcat = p.get("sub_category", p.get("subcategory", "")).lower()

        matches_category = not cats or p_cat in cats
        matches_subcategory = not subcats or p_subcat in subcats
        matches_cat = matches_category and matches_subcategory

        if semantics and matches_cat and place_matches_semantic_hints(p, semantics):
            semantic_match.append(p)
        elif matches_cat:
            category_match.append(p)
        else:
            non_matching.append(p)

    if semantic_match:
        label = ", ".join(semantics) or ", ".join(subcats or cats) or "matching"
        logger.info(
            "[CategoryReorder] %s — %d semantic match(es) out of %d",
            label, len(semantic_match), len(fresh_pool),
        )
        return semantic_match + category_match + non_matching

    if category_match:
        label = ", ".join(subcats or cats) or "matching"
        logger.info(
            "[CategoryReorder] %s — %d matching place(s) out of %d",
            label, len(category_match), len(fresh_pool),
        )

    return category_match + non_matching


# ═══════════════════════════════════════════════════════════════════════════════
# Day Scoring for Place Insertion
# ═══════════════════════════════════════════════════════════════════════════════

# Default daily activity budget in minutes (8 hours for sightseeing)
_DAY_BUDGET_MINUTES = 480


def _score_day_for_place(
    day: dict,
    new_place: dict,
) -> float:
    """
    Score how well a single day fits a new place (0.0–1.0).

    Three factors, each weighted:
      - Free time (0.4): does the day have enough remaining minutes?
      - Category balance (0.3): avoid packing too many of the same type into one day
      - Proximity (0.3): how close is the new place to existing stops?

    Returns a float in [0.0, 1.0] where higher = better fit.
    """
    stops = day.get("stops", [])
    new_cat = (new_place.get("category") or "").lower()
    new_duration = new_place.get("estimated_duration_minutes") or 60
    new_lat = new_place.get("lat")
    new_lon = new_place.get("lon")

    # ── Factor 1: Free time (weight 0.4) ────────────────────────────
    used_minutes = sum(
        s.get("estimated_duration_minutes") or 60
        for s in stops
    )
    remaining = _DAY_BUDGET_MINUTES - used_minutes
    if remaining >= new_duration:
        free_score = 1.0
    elif remaining > 0:
        free_score = remaining / new_duration  # partial fit
    else:
        free_score = 0.0  # completely full

    # ── Factor 2: Category balance (weight 0.3) ─────────────────────
    same_cat_count = sum(
        1 for s in stops
        if (s.get("category") or "").lower() == new_cat
    )
    if same_cat_count == 0:
        balance_score = 1.0
    elif same_cat_count == 1:
        balance_score = 0.6
    else:
        balance_score = 0.2  # 2+ same-category stops → crowded

    # ── Factor 3: Geographic proximity (weight 0.3) ─────────────────
    if new_lat is not None and new_lon is not None and stops:
        distances = []
        for s in stops:
            slat = s.get("lat")
            slon = s.get("lon")
            if slat is not None and slon is not None:
                distances.append(haversine(new_lat, new_lon, slat, slon))
        if distances:
            avg_distance = sum(distances) / len(distances)
            if avg_distance <= 1.0:
                proximity_score = 1.0
            elif avg_distance <= 5.0:
                proximity_score = 0.7
            elif avg_distance <= 10.0:
                proximity_score = 0.4
            else:
                proximity_score = 0.1
        else:
            proximity_score = 0.5  # no coordinate data to compare
    else:
        proximity_score = 0.5  # neutral when no location data

    # ── Weighted combination ────────────────────────────────────────
    score = (
        free_score * 0.4
        + balance_score * 0.3
        + proximity_score * 0.3
    )
    return round(score, 3)


def _find_best_day_for_place(
    itinerary: dict,
    new_place: dict,
) -> tuple[int | None, float]:
    """
    Find the day with the highest score for inserting *new_place*.

    Args:
        itinerary: Full itinerary dict with ``days`` list.
        new_place: Place dict with ``category``, ``lat``, ``lon``,
            ``estimated_duration_minutes``.

    Returns:
        ``(best_day_number, best_score)`` or ``(None, 0.0)`` if no days exist.
    """
    days = itinerary.get("days", [])
    if not days:
        return None, 0.0

    best_day: int | None = None
    best_score = -1.0

    for day in days:
        day_num = day.get("day_number")
        if day_num is None:
            continue
        score = _score_day_for_place(day, new_place)
        if score > best_score:
            best_score = score
            best_day = day_num

    return best_day, best_score


# ═══════════════════════════════════════════════════════════════════════════════
# Slot & Day Distribution — avoids clustering similar places
# ═══════════════════════════════════════════════════════════════════════════════


def _count_same_category_in_slot(
    day: dict,
    new_place: dict,
    time_slot: str,
) -> int:
    """Count how many stops in the same time slot share category+subcategory."""
    new_cat = (new_place.get("category") or "").lower()
    new_sub = (new_place.get("sub_category") or "").lower()
    count = 0
    for stop in day.get("stops", []):
        if stop.get("suggested_time_of_day") != time_slot:
            continue
        stop_cat = (stop.get("category") or "").lower()
        stop_sub = (stop.get("sub_category") or "").lower()
        if stop_cat == new_cat and stop_sub == new_sub:
            count += 1
    return count


def _find_best_day_and_slot_for_place(
    itinerary: dict,
    new_place: dict,
    used_slots_per_day: dict[int, set[str]] | None = None,
) -> tuple[int, str]:
    """Find the best (day_number, time_slot) combination for inserting a new place.

    Combines day-level scoring from ``_score_day_for_place`` with slot-level
    clustering avoidance.  ``used_slots_per_day`` tracks slots already consumed
    in the current batch of additions so multiple places get spread out.
    """
    days = itinerary.get("days", [])
    if not days:
        return (1, "afternoon")

    used_slots_per_day = used_slots_per_day or {}

    best_day_num = 1
    best_slot = "afternoon"
    best_score = float("-inf")

    for day in days:
        day_num = day.get("day_number", 1)

        # Use the day-level scoring from _score_day_for_place
        day_score = _score_day_for_place(day, new_place)

        # For each slot in this day, compute the combined score
        for slot in _AVAILABLE_SLOTS:
            combined = day_score * 2.0  # Base: day-level fit

            # Penalize if this slot was already used in this batch for this day
            day_used = used_slots_per_day.get(day_num, set())
            if slot in day_used:
                combined -= 3.0

            # Penalize same-category clustering in this slot
            same_cat = _count_same_category_in_slot(day, new_place, slot)
            combined -= same_cat * 4.0

            if combined > best_score:
                best_score = combined
                best_day_num = day_num
                best_slot = slot

    return (best_day_num, best_slot)


# ═══════════════════════════════════════════════════════════════════════════════
# Post-edit Rebalancing — fixes clustering after all operations are applied
# ═══════════════════════════════════════════════════════════════════════════════


def _rebalance_clustered_slots(itinerary: dict) -> dict:
    """Post-edit pass: detect and fix slot clustering of same-category stops.

    Scans each day for time slots containing 2+ stops with the same
    (category, sub_category) pair, then moves the excess stop(s) to a
    different available slot within the same day.  Re-sorts stops after
    adjustments.

    Returns the original *itinerary* unchanged if no adjustments were needed.
    """
    modified = copy.deepcopy(itinerary)
    adjusted = False

    for day in modified.get("days", []):
        stops = day.get("stops", [])
        if len(stops) < 2:
            continue

        # Build groups: (category, sub_category, time_slot) → list of stop indices
        groups: dict[tuple[str, str, str], list[int]] = {}
        for i, stop in enumerate(stops):
            key = (
                (stop.get("category") or "").lower(),
                (stop.get("sub_category") or "").lower(),
                stop.get("suggested_time_of_day", "afternoon"),
            )
            groups.setdefault(key, []).append(i)

        # Find groups with 2+ same-category stops crammed into the same slot
        for (cat, sub, slot), indices in groups.items():
            if len(indices) < 2:
                continue

            # Move the excess stops to different slots
            for idx in indices[1:]:
                stop = stops[idx]
                available_slots = [s for s in _AVAILABLE_SLOTS if s != slot]
                moved = False
                for alt_slot in available_slots:
                    # Check if the alternative slot already has the same category
                    conflict = False
                    for s in stops:
                        if s is stop:
                            continue
                        if (
                            (s.get("category") or "").lower() == cat
                            and (s.get("sub_category") or "").lower() == sub
                            and s.get("suggested_time_of_day") == alt_slot
                        ):
                            conflict = True
                            break
                    if not conflict:
                        stop["suggested_time_of_day"] = alt_slot
                        adjusted = True
                        moved = True
                        logger.info(
                            "[Rebalance] Moved '%s' from %s to %s on day %d",
                            stop.get("name", "?"), slot, alt_slot,
                            day.get("day_number"),
                        )
                        break
                if not moved:
                    logger.debug(
                        "[Rebalance] Could not move '%s' — all other slots also have '%s' stops",
                        stop.get("name", "?"), sub or cat,
                    )

        if adjusted:
            day["stops"] = _sort_stops_by_time_slot(stops)
            _fix_travel_times(day["stops"])

    return modified if adjusted else itinerary


# ═══════════════════════════════════════════════════════════════════════════════
# Compact Context Builder
# ═══════════════════════════════════════════════════════════════════════════════

async def build_compact_context(
    itinerary: dict,
    modification_request: str,
    available_places: list[dict] | None = None,
    preferences: dict | None = None,
    max_places: int = MODIFIER_POOL_DISPLAY,
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
    category_hints = _detect_category_hints(modification_request, pool=available_places)

    # If keyword matching returned empty, try embedding-based fallback
    # to catch semantically similar subcategories not in any keyword map.
    if not category_hints and available_places:
        embedding_hints = await _embedding_category_hints(modification_request, pool=available_places)
        if embedding_hints:
            logger.info(
                "[BuildContext] Embedding fallback detected: %s",
                embedding_hints.get("sub_category", embedding_hints.get("category", [])),
            )
            category_hints = embedding_hints

    fresh_pool = _reorder_pool_by_category(fresh_pool, category_hints)

    semantics = category_hints.get("semantic", [])
    if semantics:
        lines.append(
            f"Required place type: {', '.join(semantics)} — "
            "pick ONLY places whose name/type matches (never substitute a different religion or category)."
        )
        semantic_matches = filter_places_by_semantics(fresh_pool, semantics)
        if semantic_matches:
            fresh_pool = semantic_matches + [p for p in fresh_pool if p not in semantic_matches]
        else:
            lines.append(
                f"⚠ No unused places in the pool match {', '.join(semantics)} — "
                "do NOT add a substitute; explain in `note` and leave the itinerary unchanged."
            )
        lines.append("")

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
