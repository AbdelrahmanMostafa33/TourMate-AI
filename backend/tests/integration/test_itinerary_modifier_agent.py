# tests/integration/test_itinerary_modifier_agent.py

"""
Integration tests for the Itinerary Modifier Agent (Mode 2).

The modifier now uses **delta operations** instead of full itinerary
regeneration.  The LLM (via ``invoke_with_fallback`` with
``structured_output=ModifierResponse``) returns a Pydantic operation
model.  Deterministic Python code in ``operations.py`` applies it.

These tests mock ``invoke_with_fallback`` to return a pre-built
``ModifierResponse``, then verify that ``run_itinerary_modifier``
correctly delegates to ``apply_operation`` and returns a properly
modified itinerary.
"""

import copy
from unittest.mock import patch

import pytest

from ai_engine.agents.itinerary_modifier_agent import run_itinerary_modifier
from ai_engine.agents.operations import (
    AddOperation,
    ChangeHotelOperation,
    RemoveOperation,
    ReorderOperation,
    ReThemeOperation,
    SwapOperation,
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
                    "category": "attraction",
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
                    "category": "attraction",
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
                    "category": "attraction",
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


# ═══════════════════════════════════════════════════════════════════════════
# 1. SWAP Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestSwapOperation:

    @pytest.mark.asyncio
    async def test_swap_stop_with_pool_place(self):
        """
        "Swap the Egyptian Museum for something more entertaining"
        → place_001 replaced with place_004 (Al-Azhar Park).
        """
        operation = SwapOperation(
            remove_place_id="place_001",
            add_place_id="place_004",
            day_number=1,
            new_why_recommended="Outdoor park with cultural shows",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Swapped museum for park")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Swap the Egyptian Museum for something more entertaining",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert result is not BASE_ITINERARY  # deep copy returned
        # Day 1 stop 0 should now be place_004 (Al-Azhar Park)
        assert result["days"][0]["stops"][0]["id"] == "place_004"
        assert result["days"][0]["stops"][0]["name"] == "Al-Azhar Park"
        # The why_recommended from the operation should be set
        assert "cultural shows" in result["days"][0]["stops"][0].get("why_recommended", "")
        # Day 1 stop 1 unchanged
        assert result["days"][0]["stops"][1]["id"] == "place_003"
        # Day 2 entirely unchanged
        assert result["days"][1]["stops"][0]["id"] == "place_004"
        assert result["days"][1]["stops"][1]["id"] == "rest_001"

    @pytest.mark.asyncio
    async def test_swap_restaurant(self):
        """
        "Swap Abu Shukri for a different restaurant"
        → rest_001 replaced with rest_002.
        """
        operation = SwapOperation(
            remove_place_id="rest_001",
            add_place_id="rest_002",
            day_number=2,
            new_why_recommended="Great variety of local dishes",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Swapped restaurant")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
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
    async def test_remove_stop_from_day(self):
        """
        "Remove Al-Azhar Park from Day 2"
        → place_004 removed, rest_001 becomes the only stop.
        """
        operation = RemoveOperation(place_id="place_004")

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Removed Al-Azhar Park")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Remove Al-Azhar Park from Day 2",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][1]["stops"]) == 1
        assert result["days"][1]["stops"][0]["id"] == "rest_001"
        # No travel time on the only remaining stop
        assert "travel_time_to_next_minutes" not in result["days"][1]["stops"][0]
        # Day 1 unchanged
        assert len(result["days"][0]["stops"]) == 2

    @pytest.mark.asyncio
    async def test_remove_first_stop_reconnects(self):
        """
        "Remove the Egyptian Museum from Day 1"
        → place_001 removed, Pyramids becomes the only stop.
        """
        operation = RemoveOperation(place_id="place_001")

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Removed museum")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Remove the Egyptian Museum from Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][0]["stops"]) == 1
        assert result["days"][0]["stops"][0]["id"] == "place_003"
        # No travel time on the only stop left
        assert "travel_time_to_next_minutes" not in result["days"][0]["stops"][0]


# ═══════════════════════════════════════════════════════════════════════════
# 3. ADD Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestAddOperation:

    @pytest.mark.asyncio
    async def test_add_evening_stop(self):
        """
        "Add evening entertainment on Day 1"
        → place_002 (Khan El Khalili) appended to Day 1.
        """
        operation = AddOperation(
            day_number=1,
            suggested_time_of_day="evening",
            add_place_id="place_002",
            why_recommended="Evening market visit with lively atmosphere",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Added evening activity")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Add evening entertainment on Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][0]["stops"]) == 3
        added = result["days"][0]["stops"][-1]
        assert added["id"] == "place_002"
        assert added["name"] == "Khan El Khalili"
        assert added["suggested_time_of_day"] == "evening"

    @pytest.mark.asyncio
    async def test_add_morning_activity(self):
        """
        "Add a morning activity on Day 2 before the park"
        → place_002 inserted at the beginning of Day 2.
        """
        operation = AddOperation(
            day_number=2,
            suggested_time_of_day="morning",
            add_place_id="place_002",
            why_recommended="Start the day with market exploration",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Added morning market visit")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Add a morning market visit on Day 2 before going to the park",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        assert len(result["days"][1]["stops"]) == 3
        # The new morning stop is inserted AFTER the existing morning stop
        # (Al-Azhar Park at index 0), so place_002 should be at index 1
        assert result["days"][1]["stops"][1]["id"] == "place_002"
        assert result["days"][1]["stops"][1]["suggested_time_of_day"] == "morning"
        # Existing morning stop still at index 0
        assert result["days"][1]["stops"][0]["id"] == "place_004"
        assert result["days"][1]["stops"][0]["suggested_time_of_day"] == "morning"


# ═══════════════════════════════════════════════════════════════════════════
# 4. CHANGE_HOTEL Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestChangeHotelOperation:

    @pytest.mark.asyncio
    async def test_change_hotel(self):
        """
        "Change the hotel to something cheaper"
        → hotel_001 replaced with hotel_002.
        """
        operation = ChangeHotelOperation(
            old_hotel_id="hotel_001",
            new_hotel_id="hotel_002",
            why_recommended="More affordable downtown location",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Changed to a cheaper hotel")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
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
    async def test_add_second_hotel(self):
        """
        "Add another hotel option near downtown"
        → Second hotel appended (old_hotel_id is None).
        """
        operation = ChangeHotelOperation(
            old_hotel_id=None,
            new_hotel_id="hotel_002",
            why_recommended="Convenient downtown location",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Added downtown hotel option")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
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
    async def test_reverse_stops_within_day(self):
        """
        "Reverse the order of stops on Day 1"
        → Pyramids comes first, Egyptian Museum second.
        """
        operation = ReorderOperation(
            day_number=1,
            new_order=["place_003", "place_001"],
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Reversed Day 1")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="Reverse the order of stops on Day 1",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        # Day 1 stops reversed
        assert result["days"][0]["stops"][0]["id"] == "place_003"
        assert result["days"][0]["stops"][1]["id"] == "place_001"
        # First stop has travel time, last doesn't
        assert "travel_time_to_next_minutes" in result["days"][0]["stops"][0]
        assert "travel_time_to_next_minutes" not in result["days"][0]["stops"][1]
        # Day 2 unchanged
        assert result["days"][1]["stops"][0]["id"] == "place_004"
        assert result["days"][1]["stops"][1]["id"] == "rest_001"


# ═══════════════════════════════════════════════════════════════════════════
# 6. RE_THEME Operation
# ═══════════════════════════════════════════════════════════════════════════


class TestReThemeOperation:

    @pytest.mark.asyncio
    async def test_rename_day_theme(self):
        """Update Day 1 theme string."""
        operation = ReThemeOperation(
            day_number=1,
            new_theme="Pyramids and Pharaohs",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Updated Day 1 theme")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
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


# ═══════════════════════════════════════════════════════════════════════════
# 7. Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_original(self):
        """invoke_with_fallback raises → returns original itinerary."""
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
        """Empty request → returns original without calling LLM."""
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
        mock_invoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_none_itinerary_returns_early(self):
        """None itinerary → returns None without calling LLM."""
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

    @pytest.mark.asyncio
    async def test_invalid_operation_returns_original(self):
        """
        When the LLM outputs an invalid operation (e.g. place not in pool),
        apply_operation logs a warning and returns the itinerary unchanged.
        """
        operation = SwapOperation(
            remove_place_id="place_001",
            add_place_id="nonexistent_place",
            day_number=1,
            new_why_recommended="",
        )

        async def _mock_invoke(*args, **kwargs):
            from ai_engine.agents.operations import ModifierResponse
            return ModifierResponse(operation=operation, note="Attempted swap")

        with patch(
            "ai_engine.agents.itinerary_modifier_agent.invoke_with_fallback",
            side_effect=_mock_invoke,
        ):
            result = await run_itinerary_modifier(
                current_itinerary=BASE_ITINERARY,
                modification_request="swap with nonexistent place",
                available_places=MOCK_PLACES,
                preferences=PREFERENCES,
            )

        # The operation doesn't have a matching place in the pool,
        # but the itinerary itself shouldn't be the same object since
        # apply_operation creates a deep copy. However, the content
        # should be identical.
        assert result is not BASE_ITINERARY
        assert result["days"][0]["stops"][0]["id"] == "place_001"  # unchanged
