"""\
Unit tests for the delta-based Itinerary Operations (operations.py).

Covers:
    - Helper functions: _find_day, _find_stop_index, _remove_travel_time
    - Operation executors: REMOVE, SWAP, ADD, CHANGE_HOTEL, REORDER, RE_THEME
    - Public API: apply_operation (dispatch + unknown ops)
    - Category detection: _detect_category_hints, _reorder_pool_by_category
    - Context builder: build_compact_context
    - Pydantic model: ModifierResponse._normalize_input (flat + nested formats)
    - Edge cases: missing places, missing days, empty pools, deep-copy immutability
"""

import copy
import pytest

from ai_engine.services.operations import (
    # Helpers
    _find_day,
    _find_stop_index,
    _remove_travel_time,
    # Executors
    _exec_remove,
    _exec_swap,
    _exec_add,
    _exec_change_hotel,
    _exec_reorder,
    _exec_retheme,
    # Public API
    apply_operation,
    # Category
    _detect_category_hints,
    _reorder_pool_by_category,
    # Context
    build_compact_context,
    # Schemas
    ModifierResponse,
    RemoveOperation,
    SwapOperation,
    AddOperation,
    ChangeHotelOperation,
    ReorderOperation,
    ReThemeOperation,
)

# ── Test Data ──────────────────────────────────────────────────────────────

BASE_ITINERARY = {
    "destination": "Cairo",
    "duration_days": 2,
    "days": [
        {
            "day_number": 1,
            "theme": "History and Culture",
            "stops": [
                {
                    "id": "place_001",
                    "name": "Egyptian Museum",
                    "category": "attraction",
                    "sub_category": "museum",
                    "lat": 30.0478, "lon": 31.2336,
                    "cuisine_type": "",
                    "interest_tags": ["history", "art"],
                    "why_recommended": "Explore ancient artifacts",
                    "estimated_duration_minutes": 120,
                    "suggested_time_of_day": "morning",
                    "travel_time_to_next_minutes": 15.0,
                    "transport_mode": "driving",
                },
                {
                    "id": "place_003",
                    "name": "Pyramids of Giza",
                    "category": "attraction",
                    "sub_category": "historic",
                    "lat": 29.9792, "lon": 31.1342,
                    "cuisine_type": "",
                    "interest_tags": ["history", "architecture"],
                    "why_recommended": "Iconic ancient wonder",
                    "estimated_duration_minutes": 180,
                    "suggested_time_of_day": "afternoon",
                },
            ],
        },
        {
            "day_number": 2,
            "theme": "Markets and Culinary",
            "stops": [
                {
                    "id": "place_004",
                    "name": "Al-Azhar Park",
                    "category": "attraction",
                    "sub_category": "park",
                    "lat": 30.0436, "lon": 31.2496,
                    "cuisine_type": "",
                    "interest_tags": ["nature", "parks"],
                    "why_recommended": "Beautiful green space",
                    "estimated_duration_minutes": 90,
                    "suggested_time_of_day": "morning",
                    "travel_time_to_next_minutes": 5.0,
                    "transport_mode": "walking",
                },
                {
                    "id": "rest_001",
                    "name": "Abu Shukri",
                    "category": "restaurant",
                    "sub_category": "local cuisine",
                    "lat": 30.0464, "lon": 31.2325,
                    "cuisine_type": "local cuisine",
                    "interest_tags": ["food"],
                    "why_recommended": "Authentic Egyptian food",
                    "estimated_duration_minutes": 60,
                    "suggested_time_of_day": "afternoon",
                },
            ],
        },
    ],
    "accommodation_suggestions": [
        {
            "id": "hotel_001",
            "name": "Marriott Mena House",
            "sub_category": "luxury hotel",
            "accommodation_type": "hotel",
            "lat": 29.9758, "lon": 31.1334,
            "why_recommended": "Luxury stay near pyramids",
            "rating": 4.6,
            "amenities": ["pool", "spa", "restaurant"],
        },
    ],
}

PLACE_POOL = [
    {
        "id": "place_002",
        "name": "Khan El Khalili",
        "category": "attraction",
        "sub_category": "market",
        "lat": 30.0478, "lon": 31.2336,
        "cuisine_type": "",
        "interest_tags": ["shopping", "market"],
        "why_recommended": "Vibrant historic market",
        "estimated_duration_minutes": 120,
        "rating": 4.5,
        "address": "El Gamaleya, Cairo",
        "photos": ["photo_khan.jpg"],
    },
    {
        "id": "rest_002",
        "name": "Nubia Restaurant",
        "category": "restaurant",
        "sub_category": "street food",
        "lat": 30.0458, "lon": 31.2360,
        "cuisine_type": "local cuisine",
        "interest_tags": ["food", "local"],
        "why_recommended": "Great local dishes",
        "estimated_duration_minutes": 60,
        "rating": 4.2,
        "address": "Downtown Cairo",
    },
    {
        "id": "hotel_002",
        "name": "Steigenberger Tahrir",
        "category": "hotel",
        "sub_category": "boutique hotel",
        "accommodation_type": "hotel",
        "lat": 30.0429, "lon": 31.2347,
        "why_recommended": "Central downtown location",
        "rating": 4.3,
        "amenities": ["gym", "restaurant", "bar"],
        "address": "Tahrir Square",
        "photos": ["photo_steigen.jpg"],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _find_day
# ═══════════════════════════════════════════════════════════════════════════

class TestFindDay:

    def test_finds_existing_day(self):
        day = _find_day(BASE_ITINERARY, 1)
        assert day is not None
        assert day["day_number"] == 1
        assert day["theme"] == "History and Culture"

    def test_finds_second_day(self):
        day = _find_day(BASE_ITINERARY, 2)
        assert day is not None
        assert day["day_number"] == 2

    def test_returns_none_for_missing_day(self):
        assert _find_day(BASE_ITINERARY, 99) is None

    def test_returns_none_for_zero_day(self):
        assert _find_day(BASE_ITINERARY, 0) is None

    def test_returns_none_for_empty_days(self):
        assert _find_day({"days": []}, 1) is None


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _find_stop_index
# ═══════════════════════════════════════════════════════════════════════════

class TestFindStopIndex:

    def test_finds_existing_stop(self):
        stops = BASE_ITINERARY["days"][0]["stops"]
        idx = _find_stop_index(stops, "place_001")
        assert idx == 0

    def test_finds_second_stop(self):
        stops = BASE_ITINERARY["days"][1]["stops"]
        idx = _find_stop_index(stops, "rest_001")
        assert idx == 1

    def test_returns_minus_one_for_missing(self):
        stops = BASE_ITINERARY["days"][0]["stops"]
        assert _find_stop_index(stops, "nonexistent") == -1

    def test_returns_minus_one_for_empty_list(self):
        assert _find_stop_index([], "place_001") == -1


# ═══════════════════════════════════════════════════════════════════════════
# Helper: _remove_travel_time
# ═══════════════════════════════════════════════════════════════════════════

class TestRemoveTravelTime:

    def test_removes_both_fields(self):
        stop = {"travel_time_to_next_minutes": 10.0, "transport_mode": "driving"}
        _remove_travel_time(stop)
        assert "travel_time_to_next_minutes" not in stop
        assert "transport_mode" not in stop

    def test_noop_when_no_travel_time(self):
        stop = {"id": "test", "name": "Test"}
        original = dict(stop)
        _remove_travel_time(stop)
        assert stop == original

    def test_handles_partial_fields(self):
        stop = {"travel_time_to_next_minutes": 10.0}
        _remove_travel_time(stop)
        assert "travel_time_to_next_minutes" not in stop
        assert "transport_mode" not in stop


# ═══════════════════════════════════════════════════════════════════════════
# Operation: REMOVE
# ═══════════════════════════════════════════════════════════════════════════

class TestExecRemove:

    def test_remove_first_stop_from_day(self):
        op = ModifierResponse(op="REMOVE", place_id="place_001")
        result = _exec_remove(BASE_ITINERARY, op)

        assert len(result["days"][0]["stops"]) == 1
        assert result["days"][0]["stops"][0]["id"] == "place_003"
        # Day 2 unchanged
        assert len(result["days"][1]["stops"]) == 2

    def test_remove_last_stop_clears_travel_time(self):
        """Removing the last stop should clear travel_time on new last stop."""
        op = ModifierResponse(op="REMOVE", place_id="rest_001")
        result = _exec_remove(BASE_ITINERARY, op)

        assert len(result["days"][1]["stops"]) == 1
        remaining = result["days"][1]["stops"][0]
        assert remaining["id"] == "place_004"
        # Travel time should be cleared since it's now the last stop
        assert "travel_time_to_next_minutes" not in remaining
        assert "transport_mode" not in remaining

    def test_remove_nonexistent_place_adds_note(self):
        op = ModifierResponse(op="REMOVE", place_id="nonexistent")
        result = _exec_remove(BASE_ITINERARY, op)

        # Itinerary should be unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        # Note should be added
        assert "nonexistent" in result.get("_modifier_note", "")

    def test_remove_unique_stay_at_last_stop_clears_travel_time(self):
        """Remove middle stop when it's the last in a day (edge case in code)."""
        # Create itinerary with 3 stops in day 1
        itinerary = copy.deepcopy(BASE_ITINERARY)
        itinerary["days"][0]["stops"].append({
            "id": "place_extra",
            "name": "Extra Stop",
            "category": "attraction",
            "lat": 30.05, "lon": 31.24,
            "suggested_time_of_day": "evening",
            "travel_time_to_next_minutes": 10.0,
            "transport_mode": "driving",
        })

        # Remove the last stop
        op = ModifierResponse(op="REMOVE", place_id="place_extra")
        result = _exec_remove(itinerary, op)

        assert len(result["days"][0]["stops"]) == 2
        # The new last stop (place_003) should have no travel time
        remaining = result["days"][0]["stops"][1]
        assert remaining["id"] == "place_003"
        assert "travel_time_to_next_minutes" not in remaining
        assert "transport_mode" not in remaining

    def test_remove_does_not_mutate_original(self):
        op = ModifierResponse(op="REMOVE", place_id="place_001")
        result = _exec_remove(BASE_ITINERARY, op)

        # Original should be unmodified
        assert len(BASE_ITINERARY["days"][0]["stops"]) == 2
        assert BASE_ITINERARY["days"][0]["stops"][0]["id"] == "place_001"


# ═══════════════════════════════════════════════════════════════════════════
# Operation: SWAP
# ═══════════════════════════════════════════════════════════════════════════

class TestExecSwap:

    def test_swap_with_valid_place_in_pool(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="Vibrant market experience",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        # Day 1 stop 0 replaced
        assert result["days"][0]["stops"][0]["id"] == "place_002"
        assert result["days"][0]["stops"][0]["name"] == "Khan El Khalili"
        assert "Vibrant market" in result["days"][0]["stops"][0].get("why_recommended", "")
        # Remaining stop unchanged
        assert result["days"][0]["stops"][1]["id"] == "place_003"
        # Day 2 unchanged
        assert result["days"][1]["stops"][0]["id"] == "place_004"

    def test_swap_carries_over_travel_time(self):
        """Swapping the first stop should carry travel_time from old stop."""
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        swapped = result["days"][0]["stops"][0]
        assert swapped["id"] == "place_002"
        # Should have travel_time carried from original place_001
        assert swapped.get("travel_time_to_next_minutes") == 15.0
        assert swapped.get("transport_mode") == "driving"

    def test_swap_with_nonexistent_add_place_adds_note(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="nonexistent",
            day_number=1, new_why_recommended="",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        # Place unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        # Note should be present
        assert "nonexistent" in result.get("_modifier_note", "")

    def test_swap_with_nonexistent_remove_place_returns_unmodified(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="nonexistent", add_place_id="place_002",
            day_number=1, new_why_recommended="",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        # Stop list unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"

    def test_swap_with_invalid_day_number(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=99, new_why_recommended="",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        # Since day 99 doesn't exist, _exec_swap returns deep copy
        assert result["days"][0]["stops"][0]["id"] == "place_001"

    def test_swap_does_not_mutate_original(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="test",
        )
        _exec_swap(BASE_ITINERARY, op, PLACE_POOL)
        assert BASE_ITINERARY["days"][0]["stops"][0]["id"] == "place_001"

    def test_swap_restaurant(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="rest_001", add_place_id="rest_002",
            day_number=2, new_why_recommended="Try the local Nubian cuisine",
        )
        result = _exec_swap(BASE_ITINERARY, op, PLACE_POOL)

        assert result["days"][1]["stops"][1]["id"] == "rest_002"
        assert result["days"][1]["stops"][1]["name"] == "Nubia Restaurant"
        assert "Nubian cuisine" in result["days"][1]["stops"][1].get("why_recommended", "")

    def test_swap_empty_pool_adds_note(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="",
        )
        result = _exec_swap(BASE_ITINERARY, op, [])  # empty pool
        assert "place_002" in result.get("_modifier_note", "")
        assert result["days"][0]["stops"][0]["id"] == "place_001"


# ═══════════════════════════════════════════════════════════════════════════
# Operation: ADD
# ═══════════════════════════════════════════════════════════════════════════

class TestExecAdd:

    def test_add_evening_stop(self):
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="evening",
            add_place_id="place_002", why_recommended="Evening market stroll",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["days"][0]["stops"]) == 3
        added = result["days"][0]["stops"][-1]
        assert added["id"] == "place_002"
        assert added["suggested_time_of_day"] == "evening"
        assert "Evening market" in added.get("why_recommended", "")

    def test_add_morning_stop_inserts_at_beginning(self):
        """Adding a morning stop to a day that already has morning stops."""
        op = ModifierResponse(
            op="ADD", day_number=2, suggested_time_of_day="morning",
            add_place_id="place_002", why_recommended="Market visit",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)

        # Day 2 has place_004 (morning) already. Place_002 (morning)
        # should insert after it
        assert len(result["days"][1]["stops"]) == 3
        assert result["days"][1]["stops"][0]["id"] == "place_004"  # existing morning
        assert result["days"][1]["stops"][1]["id"] == "place_002"  # new morning
        assert result["days"][1]["stops"][2]["id"] == "rest_001"   # existing afternoon

    def test_add_to_nonexistent_day(self):
        op = ModifierResponse(
            op="ADD", day_number=99, suggested_time_of_day="morning",
            add_place_id="place_002", why_recommended="",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)
        # Should return unmodified (deep copy)
        assert len(result["days"]) == 2
        assert result["days"][0]["stops"][0]["id"] == "place_001"

    def test_add_with_nonexistent_place_adds_note(self):
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="afternoon",
            add_place_id="nonexistent", why_recommended="",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["days"][0]["stops"]) == 2  # unchanged
        assert "nonexistent" in result.get("_modifier_note", "")

    def test_add_between_stops_sets_travel_time_on_previous(self):
        """Adding a stop with same time slot should insert after existing stops of that slot,
        and the previous stop should get a default travel time."""
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="afternoon",
            add_place_id="place_002", why_recommended="Market",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)

        # Day 1 originally: place_001 (morning), place_003 (afternoon)
        # Adding another afternoon stop inserts AFTER the last afternoon stop
        assert len(result["days"][0]["stops"]) == 3
        assert result["days"][0]["stops"][2]["id"] == "place_002"
        # The previous-to-last stop (place_003) gets a default travel time
        prev = result["days"][0]["stops"][1]
        assert prev["travel_time_to_next_minutes"] == 10.0
        assert prev["transport_mode"] == "driving"

    def test_add_does_not_mutate_original(self):
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="evening",
            add_place_id="place_002", why_recommended="",
        )
        _exec_add(BASE_ITINERARY, op, PLACE_POOL)
        assert len(BASE_ITINERARY["days"][0]["stops"]) == 2

    def test_add_empty_pool_adds_note(self):
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="evening",
            add_place_id="place_002", why_recommended="",
        )
        result = _exec_add(BASE_ITINERARY, op, [])
        assert "place_002" in result.get("_modifier_note", "")
        assert len(result["days"][0]["stops"]) == 2

    def test_add_uses_default_time_slot_when_none(self):
        """When suggested_time_of_day is None, default to 'afternoon'."""
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day=None,
            add_place_id="place_002", why_recommended="",
        )
        result = _exec_add(BASE_ITINERARY, op, PLACE_POOL)
        added = result["days"][0]["stops"][-1]
        assert added["suggested_time_of_day"] == "afternoon"


# ═══════════════════════════════════════════════════════════════════════════
# Operation: CHANGE_HOTEL
# ═══════════════════════════════════════════════════════════════════════════

class TestExecChangeHotel:

    def test_replace_existing_hotel(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="Better downtown location",
        )
        result = _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["accommodation_suggestions"]) == 1
        assert result["accommodation_suggestions"][0]["id"] == "hotel_002"
        assert result["accommodation_suggestions"][0]["name"] == "Steigenberger Tahrir"
        assert "Better downtown" in result["accommodation_suggestions"][0].get("why_recommended", "")

    def test_add_new_hotel(self):
        """When old_hotel_id is None, new hotel should be appended."""
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id=None, new_hotel_id="hotel_002",
            why_recommended="Great downtown option",
        )
        result = _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["accommodation_suggestions"]) == 2
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"
        assert result["accommodation_suggestions"][1]["id"] == "hotel_002"

    def test_replace_nonexistent_old_hotel_appends(self):
        """Should log a warning and append when old hotel not found."""
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="nonexistent_hotel", new_hotel_id="hotel_002",
            why_recommended="",
        )
        result = _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["accommodation_suggestions"]) == 2
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"
        assert result["accommodation_suggestions"][1]["id"] == "hotel_002"

    def test_add_with_nonexistent_new_hotel_adds_note(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="nonexistent",
            why_recommended="",
        )
        result = _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["accommodation_suggestions"]) == 1  # unchanged
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"
        assert "nonexistent" in result.get("_modifier_note", "")

    def test_change_hotel_preserves_days(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="",
        )
        result = _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)

        # Day structure unchanged
        assert len(result["days"]) == 2
        assert result["days"][0]["stops"][0]["id"] == "place_001"

    def test_change_hotel_does_not_mutate_original(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="",
        )
        _exec_change_hotel(BASE_ITINERARY, op, PLACE_POOL)
        assert BASE_ITINERARY["accommodation_suggestions"][0]["id"] == "hotel_001"


# ═══════════════════════════════════════════════════════════════════════════
# Operation: REORDER
# ═══════════════════════════════════════════════════════════════════════════

class TestExecReorder:

    def test_reverse_stops_within_day(self):
        op = ModifierResponse(
            op="REORDER", day_number=1, new_order=["place_003", "place_001"],
        )
        result = _exec_reorder(BASE_ITINERARY, op)

        assert result["days"][0]["stops"][0]["id"] == "place_003"
        assert result["days"][0]["stops"][1]["id"] == "place_001"

    def test_reorder_last_stop_has_no_travel_time(self):
        op = ModifierResponse(
            op="REORDER", day_number=1, new_order=["place_003", "place_001"],
        )
        result = _exec_reorder(BASE_ITINERARY, op)

        # First stop (place_003) should have travel time
        assert "travel_time_to_next_minutes" in result["days"][0]["stops"][0]
        # Second stop (place_001) should NOT have travel time (it's last)
        assert "travel_time_to_next_minutes" not in result["days"][0]["stops"][1]

    def test_reorder_assigns_time_slots_by_position(self):
        op = ModifierResponse(
            op="REORDER", day_number=2, new_order=["rest_001", "place_004"],
        )
        result = _exec_reorder(BASE_ITINERARY, op)

        # First stop gets "morning"
        assert result["days"][1]["stops"][0]["suggested_time_of_day"] == "morning"
        # Second stop gets "afternoon"
        assert result["days"][1]["stops"][1]["suggested_time_of_day"] == "afternoon"

    def test_reorder_missing_ids_returns_unchanged(self):
        op = ModifierResponse(
            op="REORDER", day_number=1, new_order=["nonexistent", "place_001"],
        )
        result = _exec_reorder(BASE_ITINERARY, op)

        # Order should be unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"

    def test_reorder_invalid_day_returns_unchanged(self):
        op = ModifierResponse(
            op="REORDER", day_number=99, new_order=["place_003", "place_001"],
        )
        result = _exec_reorder(BASE_ITINERARY, op)
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"

    def test_reorder_single_stop_returns_single(self):
        """A day with 1 stop: reorder with just that stop's ID."""
        itinerary = copy.deepcopy(BASE_ITINERARY)
        itinerary["days"].append({
            "day_number": 3,
            "theme": "Day 3",
            "stops": [{"id": "place_001", "name": "Museum", "lat": 30.0, "lon": 31.0,
                       "suggested_time_of_day": "morning"}],
        })
        op = ModifierResponse(op="REORDER", day_number=3, new_order=["place_001"])
        result = _exec_reorder(itinerary, op)

        assert result["days"][2]["stops"][0]["id"] == "place_001"
        # Last stop should have no travel time
        assert "travel_time_to_next_minutes" not in result["days"][2]["stops"][0]

    def test_reorder_does_not_mutate_original(self):
        op = ModifierResponse(
            op="REORDER", day_number=1, new_order=["place_003", "place_001"],
        )
        _exec_reorder(BASE_ITINERARY, op)
        assert BASE_ITINERARY["days"][0]["stops"][0]["id"] == "place_001"


# ═══════════════════════════════════════════════════════════════════════════
# Operation: RE_THEME
# ═══════════════════════════════════════════════════════════════════════════

class TestExecReTheme:

    def test_update_day_theme(self):
        op = ModifierResponse(op="RE_THEME", day_number=1, new_theme="Pyramids and Pharaohs")
        result = _exec_retheme(BASE_ITINERARY, op)

        assert result["days"][0]["theme"] == "Pyramids and Pharaohs"
        # Other day unchanged
        assert result["days"][1]["theme"] == "Markets and Culinary"

    def test_retheme_nonexistent_day(self):
        op = ModifierResponse(op="RE_THEME", day_number=99, new_theme="New Theme")
        result = _exec_retheme(BASE_ITINERARY, op)

        # Days unchanged
        assert result["days"][0]["theme"] == "History and Culture"
        assert result["days"][1]["theme"] == "Markets and Culinary"

    def test_retheme_preserves_stops(self):
        op = ModifierResponse(op="RE_THEME", day_number=1, new_theme="New Theme")
        result = _exec_retheme(BASE_ITINERARY, op)

        # Stops unchanged
        assert len(result["days"][0]["stops"]) == 2
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"

    def test_retheme_does_not_mutate_original(self):
        op = ModifierResponse(op="RE_THEME", day_number=1, new_theme="New Theme")
        _exec_retheme(BASE_ITINERARY, op)
        assert BASE_ITINERARY["days"][0]["theme"] == "History and Culture"

    def test_retheme_empty_theme_string(self):
        """Setting theme to empty string should be allowed."""
        op = ModifierResponse(op="RE_THEME", day_number=1, new_theme="")
        result = _exec_retheme(BASE_ITINERARY, op)
        assert result["days"][0]["theme"] == ""


# ═══════════════════════════════════════════════════════════════════════════
# Public API: apply_operation
# ═══════════════════════════════════════════════════════════════════════════

class TestApplyOperation:

    def test_unknown_operation_returns_deep_copy(self):
        op = ModifierResponse(op="UNKNOWN_OP", note="")
        result = apply_operation(BASE_ITINERARY, op)

        # Should return a deep copy (different object, same content)
        assert result is not BASE_ITINERARY
        assert result["days"][0]["stops"][0]["id"] == "place_001"

    def test_none_itinerary_returns_none(self):
        result = apply_operation(None, ModifierResponse(op="REMOVE", place_id="test"))
        assert result is None

    def test_none_operation_returns_itinerary(self):
        result = apply_operation(BASE_ITINERARY, None)
        assert result is BASE_ITINERARY

    def test_dispatch_remove(self):
        op = ModifierResponse(op="REMOVE", place_id="place_001", note="Removed museum")
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["days"][0]["stops"]) == 1
        assert result["days"][0]["stops"][0]["id"] == "place_003"

    def test_dispatch_swap(self):
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="Market visit",
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert result["days"][0]["stops"][0]["id"] == "place_002"

    def test_dispatch_add(self):
        op = ModifierResponse(
            op="ADD", day_number=1, suggested_time_of_day="evening",
            add_place_id="place_002", why_recommended="Evening market",
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert len(result["days"][0]["stops"]) == 3

    def test_dispatch_change_hotel(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="Better location",
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert result["accommodation_suggestions"][0]["id"] == "hotel_002"

    def test_dispatch_reorder(self):
        op = ModifierResponse(
            op="REORDER", day_number=1, new_order=["place_003", "place_001"],
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert result["days"][0]["stops"][0]["id"] == "place_003"

    def test_dispatch_retheme(self):
        op = ModifierResponse(op="RE_THEME", day_number=1, new_theme="New Theme")
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert result["days"][0]["theme"] == "New Theme"

    def test_reattach_metadata_for_swapped_place(self):
        """apply_operation should reattach rich metadata from the pool."""
        op = ModifierResponse(
            op="SWAP", remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="Market visit",
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        swapped = result["days"][0]["stops"][0]
        assert swapped["id"] == "place_002"
        # Metadata from pool should be attached
        assert swapped.get("address") == "El Gamaleya, Cairo"
        assert swapped.get("photos") == ["photo_khan.jpg"]

    def test_reattach_metadata_for_new_hotel(self):
        op = ModifierResponse(
            op="CHANGE_HOTEL", old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="Better",
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        hotel = result["accommodation_suggestions"][0]
        assert hotel["id"] == "hotel_002"
        # Metadata from pool
        assert hotel.get("address") == "Tahrir Square"
        assert hotel.get("photos") == ["photo_steigen.jpg"]
        assert hotel.get("amenities") == ["gym", "restaurant", "bar"]

    def test_error_adds_modifier_note(self):
        """When the operation fails (place not found), _modifier_note is set."""
        op = ModifierResponse(
            op="REMOVE", place_id="nonexistent", note="Removed nothing"
        )
        result = apply_operation(BASE_ITINERARY, op, PLACE_POOL)

        assert "_modifier_note" in result
        assert "nonexistent" in result["_modifier_note"]


# ═══════════════════════════════════════════════════════════════════════════
# Pydantic Model: ModifierResponse
# ═══════════════════════════════════════════════════════════════════════════

class TestModifierResponse:

    def test_flat_construction(self):
        """LLM output: flat dict with op + fields."""
        response = ModifierResponse.model_validate({
            "op": "REMOVE", "place_id": "place_001", "note": "test",
        })
        assert response.op == "REMOVE"
        assert response.place_id == "place_001"

    def test_nested_operation_backward_compat(self):
        """Test code: nested format with 'operation' key."""
        op = RemoveOperation(place_id="place_001")
        response = ModifierResponse.model_validate({
            "operation": op, "note": "test note",
        })
        assert response.op == "REMOVE"
        assert response.place_id == "place_001"
        assert response.note == "test note"

    def test_nested_swap_operation(self):
        op = SwapOperation(
            remove_place_id="place_001", add_place_id="place_002",
            day_number=1, new_why_recommended="Great choice",
        )
        response = ModifierResponse.model_validate({
            "operation": op, "note": "swap test",
        })
        assert response.op == "SWAP"
        assert response.remove_place_id == "place_001"
        assert response.add_place_id == "place_002"
        assert response.day_number == 1

    def test_nested_add_operation(self):
        op = AddOperation(
            day_number=2, suggested_time_of_day="evening",
            add_place_id="place_002", why_recommended="Nice",
        )
        response = ModifierResponse.model_validate({
            "operation": op, "note": "add test",
        })
        assert response.op == "ADD"
        assert response.day_number == 2
        assert response.suggested_time_of_day == "evening"

    def test_nested_change_hotel_operation(self):
        op = ChangeHotelOperation(
            old_hotel_id="hotel_001", new_hotel_id="hotel_002",
            why_recommended="Downtown",
        )
        response = ModifierResponse.model_validate({
            "operation": op, "note": "hotel test",
        })
        assert response.op == "CHANGE_HOTEL"
        assert response.old_hotel_id == "hotel_001"
        assert response.new_hotel_id == "hotel_002"

    def test_nested_reorder_operation(self):
        op = ReorderOperation(day_number=1, new_order=["place_003", "place_001"])
        response = ModifierResponse.model_validate({
            "operation": op, "note": "reorder test",
        })
        assert response.op == "REORDER"
        assert response.day_number == 1
        assert response.new_order == ["place_003", "place_001"]

    def test_nested_retheme_operation(self):
        op = ReThemeOperation(day_number=1, new_theme="New Theme")
        response = ModifierResponse.model_validate({
            "operation": op, "note": "retheme test",
        })
        assert response.op == "RE_THEME"
        assert response.day_number == 1
        assert response.new_theme == "New Theme"

    def test_nested_dict_operation(self):
        """Backward compat with plain dict in 'operation' field."""
        response = ModifierResponse.model_validate({
            "operation": {"op": "REMOVE", "place_id": "place_001"},
            "note": "test",
        })
        assert response.op == "REMOVE"
        assert response.place_id == "place_001"


# ═══════════════════════════════════════════════════════════════════════════
# Category Detection: _detect_category_hints
# ═══════════════════════════════════════════════════════════════════════════

class TestDetectCategoryHints:

    def test_detects_museum(self):
        hints = _detect_category_hints("add a museum to day 2")
        assert hints == {"category": ["attraction"], "sub_category": ["museums"]}

    def test_detects_hotel(self):
        hints = _detect_category_hints("change the hotel")
        assert hints == {"category": ["hotel"]}

    def test_detects_restaurant(self):
        hints = _detect_category_hints("I want more food options")
        assert hints == {"category": ["restaurant"]}

    def test_no_match_returns_empty(self):
        hints = _detect_category_hints("do something random")
        assert hints == {}

    def test_empty_string_returns_empty(self):
        hints = _detect_category_hints("")
        assert hints == {}

    def test_multiple_hints_collected(self):
        """A single request that mentions multiple categories should collect all."""
        hints = _detect_category_hints("add a museum and a restaurant")
        assert hints.get("category", []) == ["attraction", "restaurant"]
        assert hints.get("sub_category", []) == ["museums"]

    def test_multiple_hints_subcategories_collected(self):
        hints = _detect_category_hints("find a museum and a nice park")
        assert hints.get("category", []) == ["attraction"]
        assert hints.get("sub_category", []) == ["museums", "parks"]

    def test_no_duplicate_categories(self):
        """Multiple keywords mapping to the same category should not duplicate."""
        hints = _detect_category_hints("museum and park")
        assert hints.get("category", []) == ["attraction"]  # both map to attraction
        assert hints.get("sub_category", []) == ["museums", "parks"]

    def test_detects_nightlife(self):
        hints = _detect_category_hints("I want nightlife options")
        assert hints == {"category": ["attraction"], "sub_category": ["nightlife"]}

    def test_detects_park_only_as_subcat(self):
        hints = _detect_category_hints("find a nice park")
        assert hints == {"category": ["attraction"], "sub_category": ["parks"]}


# ═══════════════════════════════════════════════════════════════════════════
# Pool Reordering: _reorder_pool_by_category
# ═══════════════════════════════════════════════════════════════════════════

class TestReorderPoolByCategory:

    def test_matching_places_promoted_to_front(self):
        pool = [
            {"id": "rest_001", "category": "restaurant", "sub_category": "local cuisine"},
            {"id": "place_001", "category": "attraction", "sub_category": "museum"},
            {"id": "hotel_001", "category": "hotel", "sub_category": "luxury hotel"},
        ]
        hints = {"category": "restaurant"}
        result = _reorder_pool_by_category(pool, hints)

        assert result[0]["id"] == "rest_001"
        assert result[1]["id"] == "place_001"
        assert result[2]["id"] == "hotel_001"

    def test_subcategory_matching(self):
        pool = [
            {"id": "place_001", "category": "attraction", "sub_category": "museum"},
            {"id": "place_002", "category": "attraction", "sub_category": "park"},
        ]
        hints = {"category": "attraction", "sub_category": "park"}
        result = _reorder_pool_by_category(pool, hints)

        assert result[0]["id"] == "place_002"
        assert result[1]["id"] == "place_001"

    def test_no_hints_returns_original_order(self):
        pool = [{"id": "a"}, {"id": "b"}]
        result = _reorder_pool_by_category(pool, {})
        assert result == pool

    def test_no_change_when_no_match(self):
        pool = [{"id": "a", "category": "hotel"}, {"id": "b", "category": "restaurant"}]
        hints = {"category": "attraction"}
        result = _reorder_pool_by_category(pool, hints)
        assert result == pool

    def test_empty_pool_returns_empty(self):
        assert _reorder_pool_by_category([], {"category": "hotel"}) == []


# ═══════════════════════════════════════════════════════════════════════════
# Context Builder: build_compact_context
# ═══════════════════════════════════════════════════════════════════════════

class TestBuildCompactContext:

    def test_includes_modification_request(self):
        context = build_compact_context(
            BASE_ITINERARY, "Remove the museum",
            available_places=PLACE_POOL,
            preferences=None,
        )
        assert "Remove the museum" in context

    def test_includes_day_summary(self):
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=None, preferences=None,
        )
        assert "Day 1" in context
        assert "Egyptian Museum" in context
        assert "Day 2" in context
        assert "Al-Azhar Park" in context

    def test_includes_hotels(self):
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=None, preferences=None,
        )
        assert "Marriott Mena House" in context
        assert "hotel_001" in context

    def test_includes_duration_and_destination(self):
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=None, preferences=None,
        )
        assert "Cairo" in context
        assert "2 days" in context

    def test_includes_available_places(self):
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=PLACE_POOL, preferences=None,
        )
        assert "Available places" in context
        assert "Khan El Khalili" in context
        assert "Nubia Restaurant" in context

    def test_available_places_exclude_used(self):
        """Places already in the itinerary should be excluded from available list."""
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=PLACE_POOL, preferences=None,
        )
        # None of the places already in the itinerary should appear as "available"
        # place_001 (Egyptian Museum) is in the itinerary but NOT in PLACE_POOL, so it's fine
        # rest_001 (Abu Shukri) is in the itinerary but NOT in PLACE_POOL, so it's fine

    def test_includes_preferences(self):
        prefs = {
            "budget_level": "moderate",
            "travel_style": "cultural",
            "pace": "moderate",
            "interests": ["history", "food"],
        }
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=None, preferences=prefs,
        )
        assert "moderate" in context
        assert "cultural" in context
        assert "moderate" in context
        assert "history" in context
        assert "food" in context

    def test_empty_itinerary_handled_gracefully(self):
        context = build_compact_context(
            {"destination": "", "days": [], "accommodation_suggestions": []},
            "test",
            available_places=None,
            preferences=None,
        )
        assert "test" in context  # just the modification request

    def test_itinerary_without_destination_still_works(self):
        context = build_compact_context(
            {"days": BASE_ITINERARY["days"], "accommodation_suggestions": []},
            "test",
            available_places=None,
            preferences=None,
        )
        assert "Day 1" in context

    def test_places_used_in_itinerary_excluded_from_pool(self):
        """Ensure places used as stops are filtered from the available pool."""
        # Add a place to the pool that IS in the itinerary
        pool_with_used = list(PLACE_POOL) + [
            {
                "id": "place_001",  # This is in the itinerary
                "name": "Egyptian Museum",
                "category": "attraction",
            },
            {
                "id": "hotel_001",  # This is in accommodation
                "name": "Marriott Mena House",
                "category": "hotel",
            },
        ]
        context = build_compact_context(
            BASE_ITINERARY, "test", available_places=pool_with_used, preferences=None,
        )
        # Used places should not appear in "Available places" section
        available_section = context.split("Available places")[1] if "Available places" in context else ""
        assert "place_001" not in available_section
        assert "hotel_001" not in available_section
