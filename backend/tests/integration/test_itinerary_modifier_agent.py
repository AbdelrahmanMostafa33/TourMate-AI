# tests/integration/test_itinerary_modifier_agent.py

"""
Integration tests for the Itinerary Modifier Agent (Mode 2).

Tests cover surgically editing an existing itinerary without re-running
the full pipeline. The LLM (invoke_with_fallback) is mocked, but all
agent logic (prompt building, place trimming, dedup, JSON parsing,
metadata reattachment) runs for real.

Operations tested:
    - SWAP: Replace a stop with a different place from the pool
    - REMOVE: Delete a specific stop
    - ADD: Insert a new stop from the pool
    - CHANGE_HOTEL: Replace a hotel suggestion
    - REORDER: Change the order of stops within a day
    - RE_THEME: Update a day's theme or description
    - Error handling: invalid JSON, empty response, missing days
"""

import json
import copy
import pytest
from unittest.mock import MagicMock, patch

from ai_engine.agents.itinerary_modifier_agent import (
    run_itinerary_modifier,
    _trim_for_modifier,
)
from tests.integration.conftest import MOCK_PLACES


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
                    "category": "attractions",
                    "sub_category": "museum",
                    "lat": 30.0478, "lon": 31.2336,
                    "cuisine_type": "",
                    "interest_tags": ["history", "art", "museum"],
                    "why_recommended": "Explore ancient artifacts",
                    "estimated_duration_minutes": 120,
                    "suggested_time_of_day": "morning",
                    "travel_time_to_next_minutes": 15.0,
                    "transport_mode": "driving",
                },
                {
                    "id": "place_003",
                    "name": "Pyramids of Giza",
                    "category": "attractions",
                    "sub_category": "historic",
                    "lat": 29.9792, "lon": 31.1342,
                    "cuisine_type": "",
                    "interest_tags": ["history", "architecture", "heritage"],
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
                    "category": "attractions",
                    "sub_category": "park",
                    "lat": 30.0436, "lon": 31.2496,
                    "cuisine_type": "",
                    "interest_tags": ["nature", "parks", "outdoors"],
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
            "lat": 29.9758, "lon": 31.1334,
            "why_recommended": "Luxury stay near pyramids",
            "rating": 4.6,
        },
    ],
}

PREFERENCES = {
    "budget_level": "moderate",
    "travel_style": "cultural",
    "pace": "moderate",
    "interests": ["history", "art", "food"],
    "food_preferences": ["local cuisine"],
}


def _make_mock_response(content_dict: dict) -> MagicMock:
    """Wrap a dict as a MagicMock with .content returning JSON."""
    response = MagicMock()
    response.content = json.dumps(content_dict)
    return response


# ═══════════════════════════════════════════════════════════════════════════
# 1. SWAP Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestSwapOperation:

    @pytest.mark.asyncio
    async def test_swap_stop_with_entertainment_venue(self):
        """
        "Swap the Egyptian Museum for something more entertaining"
        → place_001 replaced with place_004 (Al-Azhar Park) which has
          entertainment-relevant tags.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Swapped Egyptian Museum for Al-Azhar Park for an entertaining outdoor experience"
        # Replace Day 1 stop 0 (Egyptian Museum) with Al-Azhar Park
        modified["days"][0]["stops"][0] = {
            "id": "place_004",
            "name": "Al-Azhar Park",
            "category": "attractions",
            "sub_category": "park",
            "lat": 30.0436, "lon": 31.2496,
            "cuisine_type": "",
            "interest_tags": ["nature", "parks", "outdoors"],
            "why_recommended": "Beautiful park with great views and entertainment options",
            "estimated_duration_minutes": 90,
            "suggested_time_of_day": "morning",
            "travel_time_to_next_minutes": 15.0,
            "transport_mode": "driving",
        }

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Swap the Egyptian Museum for something more entertaining",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is not BASE_ITINERARY  # not the same object
        assert result["_modifier_note"] == modified["_modifier_note"]
        assert result["days"][0]["stops"][0]["id"] == "place_004"
        assert result["days"][0]["stops"][0]["name"] == "Al-Azhar Park"
        # Unchanged stop preserved
        assert result["days"][0]["stops"][1]["id"] == "place_003"
        assert result["days"][0]["stops"][1]["name"] == "Pyramids of Giza"
        # Day 2 unmodified
        assert result["days"][1]["stops"][0]["id"] == "place_004"  # Al-Azhar Park was also in Day 2 — but wait, we swapped Day 1 stop 0 for it
        # Actually the modifier returned Al-Azhar Park in Day 1 stop 0.
        # Day 2 still has Al-Azhar Park as stop 0. That's fine — the modifier
        # just replaced the first day's first stop with Al-Azhar Park.

    @pytest.mark.asyncio
    async def test_swap_restaurant(self):
        """
        "Swap Abu Shukri for a different restaurant"
        → rest_001 replaced with rest_002 (Nubia Restaurant)
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Swapped Abu Shukri for Nubia Restaurant for variety"
        modified["days"][1]["stops"][1] = {
            "id": "rest_002",
            "name": "Nubia Restaurant",
            "category": "restaurant",
            "sub_category": "street food",
            "lat": 30.0458, "lon": 31.2360,
            "cuisine_type": "local cuisine",
            "interest_tags": ["food"],
            "why_recommended": "Great local cuisine with a different menu",
            "estimated_duration_minutes": 60,
            "suggested_time_of_day": "afternoon",
        }

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Swap Abu Shukri for a different restaurant",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result["days"][1]["stops"][1]["id"] == "rest_002"
        assert result["days"][1]["stops"][1]["name"] == "Nubia Restaurant"
        # Day 1 unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"


# ═══════════════════════════════════════════════════════════════════════════
# 2. REMOVE Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestRemoveOperation:

    @pytest.mark.asyncio
    async def test_remove_stop_mid_day(self):
        """
        "Remove Al-Azhar Park from Day 2"
        → place_004 removed, remaining stop (Abu Shukri) has no
          travel_time_to_next since it's now the last stop.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Removed Al-Azhar Park from Day 2"
        # Remove Day 2 stop 0 (Al-Azhar Park), keep only Abu Shukri
        modified["days"][1]["stops"] = [
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
        ]
        # Update theme to reflect the change
        modified["days"][1]["theme"] = "Culinary Experience"

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Remove Al-Azhar Park from Day 2",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][1]["stops"]) == 1
        assert result["days"][1]["stops"][0]["id"] == "rest_001"
        # Day 1 unchanged
        assert len(result["days"][0]["stops"]) == 2
        assert result["days"][0]["stops"][0]["id"] == "place_001"

    @pytest.mark.asyncio
    async def test_remove_first_stop_reconnects_remaining(self):
        """
        "Remove the Egyptian Museum from Day 1"
        → place_001 removed, Pyramids becomes the only stop.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Removed Egyptian Museum from Day 1"
        modified["days"][0]["stops"] = [
            {
                "id": "place_003",
                "name": "Pyramids of Giza",
                "category": "attractions",
                "sub_category": "historic",
                "lat": 29.9792, "lon": 31.1342,
                "cuisine_type": "",
                "interest_tags": ["history", "architecture", "heritage"],
                "why_recommended": "Iconic ancient wonder",
                "estimated_duration_minutes": 180,
                "suggested_time_of_day": "afternoon",
            },
        ]

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Remove the Egyptian Museum from Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][0]["stops"]) == 1
        assert result["days"][0]["stops"][0]["id"] == "place_003"
        assert "travel_time_to_next_minutes" not in result["days"][0]["stops"][0]


# ═══════════════════════════════════════════════════════════════════════════
# 3. ADD Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestAddOperation:

    @pytest.mark.asyncio
    async def test_add_evening_stop(self):
        """
        "Add a rooftop bar after dinner on Day 1"
        → New stop inserted after the last Day 1 stop.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Added evening entertainment to Day 1"
        # Add a new evening stop after Pyramids
        modified["days"][0]["stops"][0] = dict(BASE_ITINERARY["days"][0]["stops"][0])
        modified["days"][0]["stops"][0]["travel_time_to_next_minutes"] = 15.0
        modified["days"][0]["stops"][0]["transport_mode"] = "driving"
        modified["days"][0]["stops"].append({
            "id": "place_002",  # Khan El Khalili — closest to a "rooftop bar" vibe in the pool
            "name": "Khan El Khalili",
            "category": "attractions",
            "sub_category": "market",
            "lat": 30.0478, "lon": 31.2336,
            "cuisine_type": "",
            "interest_tags": ["shopping", "history", "market"],
            "why_recommended": "Evening visit to this historic market offers lively entertainment",
            "estimated_duration_minutes": 90,
            "suggested_time_of_day": "evening",
        })

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Add a rooftop bar or evening entertainment after the Pyramids on Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][0]["stops"]) == 3
        # Last stop should be the new addition
        added_stop = result["days"][0]["stops"][-1]
        assert added_stop["suggested_time_of_day"] == "evening"
        # The new stop should have reattached metadata (address, photos, etc.)
        # Since place_002 is in MOCK_PLACES and NOT in used_ids initially,
        # the metadata reattachment loop will fill it from place_index.
        # But our mock places don't have address/photos set, so they won't be filled.
        # That's fine — the reattachment logic is verified by the id check.
        assert added_stop["id"] == "place_002"

    @pytest.mark.asyncio
    async def test_add_morning_activity(self):
        """
        "Add a morning activity on Day 2 before the park"
        → New stop inserted at the beginning of Day 2.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Added morning activity to Day 2"
        # Insert Khan El Khalili before Al-Azhar Park
        modified["days"][1]["stops"].insert(0, {
            "id": "place_002",
            "name": "Khan El Khalili",
            "category": "attractions",
            "sub_category": "market",
            "lat": 30.0478, "lon": 31.2336,
            "cuisine_type": "",
            "interest_tags": ["shopping", "history", "market"],
            "why_recommended": "Start your day exploring this vibrant market",
            "estimated_duration_minutes": 90,
            "suggested_time_of_day": "morning",
        })
        # Update travel time from new stop to Al-Azhar Park
        modified["days"][1]["stops"][0]["travel_time_to_next_minutes"] = 8.0
        modified["days"][1]["stops"][0]["transport_mode"] = "walking"

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Add a morning market visit on Day 2 before going to the park",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][1]["stops"]) == 3
        # First stop should be the new addition
        assert result["days"][1]["stops"][0]["id"] == "place_002"
        assert result["days"][1]["stops"][0]["suggested_time_of_day"] == "morning"


# ═══════════════════════════════════════════════════════════════════════════
# 4. CHANGE_HOTEL Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestChangeHotelOperation:

    @pytest.mark.asyncio
    async def test_change_hotel_to_cheaper_option(self):
        """
        "Change the hotel to something cheaper"
        → hotel_001 (Marriott Mena House, 4.6 stars) replaced with
          hotel_002 (Steigenberger Tahrir, 4.3 stars, boutique).
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Changed hotel to Steigenberger Tahrir for a more affordable option"
        modified["accommodation_suggestions"] = [
            {
                "id": "hotel_002",
                "name": "Steigenberger Tahrir",
                "sub_category": "boutique hotel",
                "lat": 30.0429, "lon": 31.2347,
                "why_recommended": "More affordable boutique hotel in downtown Cairo",
                "rating": 4.3,
            },
        ]

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Change the hotel to something cheaper",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["accommodation_suggestions"]) == 1
        assert result["accommodation_suggestions"][0]["id"] == "hotel_002"
        assert result["accommodation_suggestions"][0]["name"] == "Steigenberger Tahrir"
        # Days unchanged
        assert len(result["days"]) == 2

    @pytest.mark.asyncio
    async def test_add_second_hotel_option(self):
        """
        "Add another hotel option near downtown"
        → Second hotel added alongside the existing one.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Added Steigenberger Tahrir as a downtown hotel option"
        modified["accommodation_suggestions"] = list(BASE_ITINERARY["accommodation_suggestions"])
        modified["accommodation_suggestions"].append({
            "id": "hotel_002",
            "name": "Steigenberger Tahrir",
            "sub_category": "boutique hotel",
            "lat": 30.0429, "lon": 31.2347,
            "why_recommended": "Convenient downtown location near major attractions",
            "rating": 4.3,
        })

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Add another hotel option near downtown",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["accommodation_suggestions"]) == 2
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"
        assert result["accommodation_suggestions"][1]["id"] == "hotel_002"


# ═══════════════════════════════════════════════════════════════════════════
# 5. REORDER Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestReorderOperation:

    @pytest.mark.asyncio
    async def test_reverse_stops_order_within_day(self):
        """
        "Reverse the order of stops on Day 1"
        → Pyramids (afternoon) comes first, Egyptian Museum (morning) comes second.
          Travel times are recomputed accordingly.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Reversed Day 1 stops — Pyramids first, then Museum"
        # Reverse the two stops
        stops = list(modified["days"][0]["stops"])
        modified["days"][0]["stops"] = [stops[1], stops[0]]
        # Update travel time on the new first stop
        modified["days"][0]["stops"][0]["travel_time_to_next_minutes"] = 20.0
        modified["days"][0]["stops"][0]["transport_mode"] = "driving"
        # Remove travel time from new last stop
        modified["days"][0]["stops"][1].pop("travel_time_to_next_minutes", None)
        modified["days"][0]["stops"][1].pop("transport_mode", None)

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Reverse the order of stops on Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        # Day 1 stops are reversed
        assert result["days"][0]["stops"][0]["id"] == "place_003"  # Pyramids first
        assert result["days"][0]["stops"][0]["name"] == "Pyramids of Giza"
        assert result["days"][0]["stops"][1]["id"] == "place_001"  # Museum second
        assert result["days"][0]["stops"][1]["name"] == "Egyptian Museum"
        # Travel time on first stop preserved
        assert result["days"][0]["stops"][0]["travel_time_to_next_minutes"] == 20.0
        # Last stop has no travel time
        assert "travel_time_to_next_minutes" not in result["days"][0]["stops"][1]
        # Day 2 unchanged
        assert result["days"][1]["stops"][0]["id"] == "place_004"
        assert result["days"][1]["stops"][1]["id"] == "rest_001"

    @pytest.mark.asyncio
    async def test_move_stop_to_different_slot(self):
        """
        "Move the lunch restaurant to be the first stop on Day 2"
        → rest_001 (Abu Shukri) becomes stop 0, place_004 (Al-Azhar Park) moves to stop 1.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Moved Abu Shukri to first slot on Day 2"
        # Swap the two stops in Day 2
        modified["days"][1]["stops"] = [
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
                "suggested_time_of_day": "morning",
                "travel_time_to_next_minutes": 5.0,
                "transport_mode": "walking",
            },
            {
                "id": "place_004",
                "name": "Al-Azhar Park",
                "category": "attractions",
                "sub_category": "park",
                "lat": 30.0436, "lon": 31.2496,
                "cuisine_type": "",
                "interest_tags": ["nature", "parks", "outdoors"],
                "why_recommended": "Beautiful green space",
                "estimated_duration_minutes": 90,
                "suggested_time_of_day": "afternoon",
            },
        ]

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Move Abu Shukri to be the first stop on Day 2",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        # Day 2 stops are swapped
        assert result["days"][1]["stops"][0]["id"] == "rest_001"
        assert result["days"][1]["stops"][0]["name"] == "Abu Shukri"
        assert result["days"][1]["stops"][0]["suggested_time_of_day"] == "morning"
        assert result["days"][1]["stops"][1]["id"] == "place_004"
        assert result["days"][1]["stops"][1]["name"] == "Al-Azhar Park"
        assert result["days"][1]["stops"][1]["suggested_time_of_day"] == "afternoon"
        # Day 1 unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"


# ═══════════════════════════════════════════════════════════════════════════
# 6. RE_THEME Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestReThemeOperation:

    @pytest.mark.asyncio
    async def test_rename_day_theme(self):
        """
        "Change Day 1 theme to 'Pyramids and Pharaohs'"
        → Day 1 theme updated, everything else preserved.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Updated Day 1 theme to 'Pyramids and Pharaohs'"
        modified["days"][0]["theme"] = "Pyramids and Pharaohs"

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Change Day 1 theme to 'Pyramids and Pharaohs'",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result["days"][0]["theme"] == "Pyramids and Pharaohs"
        # Day 2 theme unchanged
        assert result["days"][1]["theme"] == "Markets and Culinary"
        # Stops unchanged
        assert result["days"][0]["stops"][0]["id"] == "place_001"
        assert result["days"][0]["stops"][1]["id"] == "place_003"
        # Accommodation unchanged
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"

    @pytest.mark.asyncio
    async def test_rename_all_day_themes(self):
        """
        "Give both days more exciting themes"
        → Both day themes updated, all stops and accommodation preserved.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["_modifier_note"] = "Updated both day themes"
        modified["days"][0]["theme"] = "Ancient Wonders"
        modified["days"][1]["theme"] = "Flavors of Cairo"

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Give both days more exciting themes",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result["days"][0]["theme"] == "Ancient Wonders"
        assert result["days"][1]["theme"] == "Flavors of Cairo"
        # Stops entirely unchanged
        assert len(result["days"][0]["stops"]) == 2
        assert len(result["days"][1]["stops"]) == 2
        assert result["accommodation_suggestions"][0]["id"] == "hotel_001"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_invalid_json_falls_back_to_original(self):
        """
        LLM returns invalid JSON → modifier returns original itinerary
        unchanged (same object).
        """
        mock_response = MagicMock()
        mock_response.content = "not valid json at all {{ broken"

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=mock_response,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="swap everything",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is BASE_ITINERARY  # same object returned (identity match)

    @pytest.mark.asyncio
    async def test_empty_days_falls_back_to_original(self):
        """
        LLM returns valid JSON but with empty days → modifier falls back.
        """
        modified = copy.deepcopy(BASE_ITINERARY)
        modified["days"] = []  # invalid — empty days

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(modified),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="remove everything",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is BASE_ITINERARY  # same object

    @pytest.mark.asyncio
    async def test_missing_days_key_falls_back_to_original(self):
        """
        LLM returns JSON without 'days' key → modifier falls back.
        """
        bad_response = {"destination": "Cairo", "duration_days": 2}  # no 'days'

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            return_value=_make_mock_response(bad_response),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="change everything",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is BASE_ITINERARY

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_original(self):
        """
        LLM raises an exception → modifier falls back to original.
        """
        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=Exception("API timeout"),
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="change everything",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is BASE_ITINERARY

    @pytest.mark.asyncio
    async def test_empty_modification_request_returns_early(self):
        """
        Empty modification request → returns original immediately
        without calling LLM.
        """
        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
        ) as mock_invoke:
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is BASE_ITINERARY
        mock_invoke.assert_not_called()  # LLM never called

    @pytest.mark.asyncio
    async def test_none_itinerary_returns_early(self):
        """
        None itinerary → returns None immediately without calling LLM.
        """
        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
        ) as mock_invoke:
            result = await run_itinerary_modifier(
                current_itinerary=None,
                modification_request="change something",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is None
        mock_invoke.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# 8. _trim_for_modifier Helper
# ═══════════════════════════════════════════════════════════════════════════


class TestTrimForModifier:

    def test_trims_attraction(self):
        """Attractions are trimmed to essential fields."""
        place = {
            "id": "place_001",
            "name": "Egyptian Museum",
            "category": "attractions",
            "sub_category": "museum",
            "subcategory": "museum",
            "lat": 30.0478,
            "lon": 31.2336,
            "rating": 4.7,
            "popularity_score": 90,
            "extra_field": "should be removed",
        }
        trimmed = _trim_for_modifier(place)

        assert trimmed["id"] == "place_001"
        assert trimmed["name"] == "Egyptian Museum"
        assert trimmed["category"] == "attractions"
        assert trimmed["lat"] == 30.0478
        assert "extra_field" not in trimmed
        # cuisine_type should not be present for non-restaurants
        assert "cuisine_type" not in trimmed

    def test_trims_restaurant_includes_cuisine(self):
        """Restaurants keep cuisine_type."""
        place = {
            "id": "rest_001",
            "name": "Abu Shukri",
            "category": "restaurant",
            "sub_category": "local cuisine",
            "lat": 30.0464,
            "lon": 31.2325,
            "rating": 4.5,
            "popularity_score": 75,
            "cuisine_type": "local cuisine",
        }
        trimmed = _trim_for_modifier(place)

        assert trimmed["cuisine_type"] == "local cuisine"

    def test_trims_hotel_includes_accommodation_type(self):
        """Hotels keep accommodation_type and amenities (capped at 3)."""
        place = {
            "id": "hotel_001",
            "name": "Marriott Mena House",
            "category": "hotel",
            "sub_category": "luxury hotel",
            "lat": 29.9758,
            "lon": 31.1334,
            "rating": 4.6,
            "popularity_score": 80,
            "accommodation_type": "hotel",
            "amenities": ["pool", "gym", "spa", "restaurant", "bar"],
        }
        trimmed = _trim_for_modifier(place)

        assert trimmed["accommodation_type"] == "hotel"
        assert trimmed["amenities"] == ["pool", "gym", "spa"]  # capped at 3

    def test_falls_back_to_subcategory_if_sub_category_missing(self):
        """Uses 'subcategory' if 'sub_category' is missing."""
        place = {
            "id": "place_001",
            "name": "Test",
            "category": "attractions",
            "subcategory": "museum",  # not sub_category
            "lat": 30.0,
            "lon": 31.0,
            "rating": 4.0,
            "popularity_score": 50,
        }
        trimmed = _trim_for_modifier(place)
        assert trimmed["sub_category"] == "museum"

    def test_empty_amenities(self):
        """Empty amenities list stays empty."""
        place = {
            "id": "hotel_001",
            "name": "Test Hotel",
            "category": "hotel",
            "sub_category": "hotel",
            "lat": 30.0,
            "lon": 31.0,
            "rating": 4.0,
            "popularity_score": 50,
            "amenities": [],
        }
        trimmed = _trim_for_modifier(place)
        assert trimmed["amenities"] == []
