# tests/integration/test_conversation_to_pipeline.py

"""
Integration tests for the Conversation Agent → Pipeline flow.

Tests verify that the conversation agent correctly:
  1. Collects slots through multi-turn conversation
  2. Builds a TripProfile from collected slots
  3. Invokes the full pipeline when slots are complete
  4. Handles session state across multiple turns
  5. Routes through the correct phases

All external calls (LLM, Redis, OSRM, HTTP) are mocked.
Agent logic (slot filling, profile building, phase transitions) runs for real.

Updated: Uses message_interpreter (interpret_message + InterpretationResult) instead of the
old 3-call pattern.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.conversation.message_interpreter import InterpretationResult
from ai_engine.conversation.conversation_state import ConversationPhase, ConversationState
from tests.integration.conftest import (
    MOCK_PLACES,
    build_planning_llm_response,
    build_validation_llm_response,
    make_mock_matrix,
)


# ── Mock Helpers ───────────────────────────────────────────────────────────


def _make_result(action: str, response: str = "OK", **extracted) -> InterpretationResult:
    """Build a mock InterpretationResult."""
    return InterpretationResult(action=action, extracted=extracted, response=response)


def _create_session_manager():
    """Create a mock SessionManager that stores state in-memory.

    Returns (manager, storage) so tests can inspect storage directly.
    """
    storage = {}
    manager = AsyncMock()

    async def fake_resume_or_create(user_id, session_id=None):
        key = session_id or user_id
        if key not in storage:
            storage[key] = ConversationState(user_id=user_id)
        return storage[key]

    async def fake_save(state):
        storage[state.user_id] = state
        return True

    manager.resume_or_create = fake_resume_or_create
    manager.save = fake_save
    return manager, storage


# ═══════════════════════════════════════════════════════════════════════════
# 1. Slot Filling → Profile Building → Pipeline Launch
# ═══════════════════════════════════════════════════════════════════════════


class TestSlotFillingToPipeline:
    """Slot filling collects profile fields, then pipeline runs."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_full_slot_filling_triggers_pipeline(
        self, mock_profile, mock_graph, mock_route, mock_get_manager
    ):
        """Multi-turn: destination + duration → budget + style → plan."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "destination": "Cairo",
                "duration_days": 3,
                "days": [{"day_number": 1, "theme": "Explore", "stops": []}],
                "accommodation_suggestions": [],
            },
            "is_valid": True,
        }

        from ai_engine.conversation.orchestrator import handle_chat

        # Turn 1: destination + duration → safety override with fill_defaults()
        # triggers pipeline immediately (destination+duration = complete, defaults fill rest)
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="Great choice! What's your budget and travel style?",
            destination_city="Cairo",
            duration_days=3,
        )
        result1 = await handle_chat("user1", "I want to visit Cairo for 3 days")
        # Pipeline runs immediately because destination + duration + defaults
        # satisfy is_complete().  Turn 2 below adjusts preferences.
        assert result1["response_type"] == "itinerary"
        assert mock_graph.ainvoke.called

        # Turn 2: budget + style + pace + interests + food + accommodation → complete → pipeline runs
        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating your itinerary!",
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history", "art"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        result2 = await handle_chat("user1", "Moderate budget, cultural style, moderate pace, interested in history and art, love local cuisine, prefer boutique hotels")
        assert result2["response_type"] == "itinerary"
        assert result2["phase"] == "itinerary_review"
        assert mock_graph.ainvoke.called

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_complete_info_in_first_message_skips_to_plan(
        self, mock_profile, mock_graph, mock_route, mock_get_manager
    ):
        """User gives everything in one message → pipeline runs immediately."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "destination": "Paris",
                "duration_days": 5,
                "days": [{"day_number": 1, "stops": []}],
                "accommodation_suggestions": [],
            },
            "is_valid": True,
        }

        from ai_engine.conversation.orchestrator import handle_chat

        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating your itinerary!",
            destination_city="Paris",
            duration_days=5,
            budget_level="luxury",
            travel_style="romantic",
            pace="relaxed",
            interests=["art", "food"],
            food_preferences=["fine dining"],
            accommodation_preferences=["boutique hotel"],
        )
        result = await handle_chat(
            "user1",
            "Plan me a 5-day luxury romantic trip to Paris",
        )
        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None
        assert mock_graph.ainvoke.called


# ═══════════════════════════════════════════════════════════════════════════
# 2. Profile Building from Slots
# ═══════════════════════════════════════════════════════════════════════════


class TestProfileBuildingFromSlots:
    """_build_profile_from_slots correctly maps slots to TripProfile."""

    def test_build_profile_from_slots_maps_all_fields(self):
        """All slot fields map to the correct TripProfile keys."""
        from ai_engine.conversation.orchestrator import _build_profile_from_slots
        from ai_engine.conversation.conversation_state import TripSlots

        slots = TripSlots()
        slots.destination_city = "Cairo"
        slots.duration_days = 3
        slots.budget_level = "moderate"
        slots.travel_style = "cultural"
        slots.pace = "moderate"
        slots.interests = ["history", "art"]
        slots.food_preferences = ["local cuisine"]
        slots.accommodation_preferences = ["boutique hotel"]

        profile = _build_profile_from_slots(slots, trip_id="trip_001")

        assert profile["trip_id"] == "trip_001"
        assert profile["budget_level"] == "moderate"
        assert profile["travel_style"] == "cultural"
        assert profile["pace"] == "moderate"
        assert profile["interests"] == ["history", "art"]
        assert profile["food_preferences"] == ["local cuisine"]
        assert profile["accommodation_preferences"] == ["boutique hotel"]

    def test_build_profile_from_slots_defaults_empty_lists(self):
        """Missing list fields default to empty lists, not None."""
        from ai_engine.conversation.orchestrator import _build_profile_from_slots
        from ai_engine.conversation.conversation_state import TripSlots

        slots = TripSlots()
        slots.destination_city = "Tokyo"
        slots.budget_level = "budget"

        profile = _build_profile_from_slots(slots, trip_id="trip_002")

        assert profile["interests"] == []
        assert profile["food_preferences"] == []
        assert profile["accommodation_preferences"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. Session State Across Multiple Turns
# ═══════════════════════════════════════════════════════════════════════════


class TestSessionStateAcrossTurns:
    """Session state persists and accumulates across conversation turns."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_slots_accumulate_across_turns(
        self, mock_route, mock_get_manager
    ):
        """Each turn adds slots without overwriting previous ones."""
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager

        from ai_engine.conversation.orchestrator import handle_chat

        # Turn 1: destination
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="How many days?",
            destination_city="Cairo",
        )
        await handle_chat("user1", "I want to go to Cairo")

        # Turn 2: duration
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="What's your budget?",
            duration_days=5,
        )
        await handle_chat("user1", "For 5 days")

        # Verify both slots are present
        state = storage["user1"]
        assert state.slots.destination_city == "Cairo"
        assert state.slots.duration_days == 5

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_general_chat_does_not_affect_slots(
        self, mock_route, mock_get_manager
    ):
        """General chat questions don't overwrite collected slots."""
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager

        from ai_engine.conversation.orchestrator import handle_chat

        # Turn 1: set destination
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="How many days?",
            destination_city="Paris",
        )
        await handle_chat("user1", "I want to visit Paris")

        # Turn 2: general question (no slot extraction)
        mock_route.return_value = _make_result(
            "answer_question",
            response="Paris is beautiful in spring!",
        )
        await handle_chat("user1", "Is Paris safe?")

        # Turn 3: set duration
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="What's your budget?",
            duration_days=3,
        )
        await handle_chat("user1", "3 days")

        state = storage["user1"]
        assert state.slots.destination_city == "Paris"
        assert state.slots.duration_days == 3

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_session_id_consistent_across_turns(
        self, mock_route, mock_get_manager
    ):
        """All responses from the same session share the same session_id."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager

        from ai_engine.conversation.orchestrator import handle_chat

        mock_route.return_value = _make_result("answer_question", response="Hi!")
        result1 = await handle_chat("user1", "Hello")
        mock_route.return_value = _make_result("answer_question", response="Welcome back!")
        result2 = await handle_chat("user1", "Hi again")

        assert result1["session_id"] == result2["session_id"]


# ═══════════════════════════════════════════════════════════════════════════
# 4. Itinerary Review Phase
# ═══════════════════════════════════════════════════════════════════════════


class TestItineraryReviewPhase:
    """After pipeline runs, user reviews the itinerary."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_approve_transitions_to_completed(
        self, mock_profile, mock_graph, mock_route, mock_get_manager
    ):
        """User approves itinerary → COMPLETED phase."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "days": [{"day_number": 1, "stops": []}],
                "accommodation_suggestions": [],
            },
            "is_valid": True,
        }

        from ai_engine.conversation.orchestrator import handle_chat

        # Generate itinerary (all 8 required slots filled)
        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating your itinerary!",
            destination_city="Cairo",
            duration_days=2,
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        result1 = await handle_chat("user1", "Plan me a 2-day trip to Cairo")
        assert result1["phase"] == "itinerary_review"

        # Approve
        mock_route.return_value = _make_result(
            "approve_itinerary",
            response="Looks great, approved!",
        )
        result2 = await handle_chat("user1", "Looks good, approve!")
        assert result2["phase"] == "completed"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_modification_re_runs_pipeline(
        self, mock_profile, mock_graph, mock_route, mock_get_manager
    ):
        """User requests change → pipeline re-runs."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "days": [{"day_number": 1, "stops": []}],
                "accommodation_suggestions": [],
            },
            "is_valid": True,
        }

        from ai_engine.conversation.orchestrator import handle_chat

        # Generate itinerary (all 8 required slots filled)
        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating your itinerary!",
            destination_city="Cairo",
            duration_days=2,
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user1", "Plan me a 2-day trip to Cairo")

        # Request modification
        mock_route.return_value = _make_result(
            "modify_itinerary",
            response="Updating your itinerary!",
        )
        result = await handle_chat("user1", "Change the hotel to something cheaper")
        assert result["response_type"] == "itinerary"
        assert result["phase"] == "itinerary_review"
        # Pipeline was re-invoked
        assert mock_graph.ainvoke.call_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# 5. New Trip After Completion
# ═══════════════════════════════════════════════════════════════════════════


class TestNewTripAfterCompletion:
    """After approving one trip, user can start a new one."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_new_trip_resets_slots(
        self, mock_profile, mock_graph, mock_route, mock_get_manager
    ):
        """After completing one trip, starting a new one resets slots."""
        manager, storage = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = {
            "optimized_itinerary": {
                "days": [{"day_number": 1, "stops": []}],
                "accommodation_suggestions": [],
            },
            "is_valid": True,
        }

        from ai_engine.conversation.orchestrator import handle_chat

        # Complete first trip (all 8 required slots filled)
        mock_route.return_value = _make_result(
            "plan_trip",
            response="Generating!",
            destination_city="Cairo",
            duration_days=2,
            budget_level="moderate",
            travel_style="cultural",
            pace="moderate",
            interests=["history"],
            food_preferences=["local cuisine"],
            accommodation_preferences=["boutique hotel"],
        )
        await handle_chat("user1", "Plan me a 2-day trip to Cairo")

        # Approve
        mock_route.return_value = _make_result(
            "approve_itinerary",
            response="Approved!",
        )
        await handle_chat("user1", "Approve!")

        # Start new trip — slots should be reset after approval
        mock_route.return_value = _make_result(
            "ask_clarification",
            response="How many days for Tokyo?",
            destination_city="Tokyo",
        )
        result = await handle_chat("user1", "Now plan me a trip to Tokyo")

        assert result["phase"] == "slot_filling"

        state = storage["user1"]
        assert state.slots.destination_city == "Tokyo"
        assert state.slots.duration_days is None


# ═══════════════════════════════════════════════════════════════════════════
# 6. Image Processing Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestImageProcessingIntegration:
    """Image analysis integrates with the pipeline flow."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.analyze_travel_image")
    async def test_image_features_passed_to_general_chat(
        self, mock_analyze, mock_route, mock_get_manager
    ):
        """Image features from analyze_travel_image are included in response."""
        manager, _ = _create_session_manager()
        mock_get_manager.return_value = manager
        mock_route.return_value = _make_result(
            "answer_question",
            response="Nice beach photo!",
        )

        mock_analyze.return_value = {
            "vibe": "sunny beach",
            "confidence": "high",
            "inferred_interests": ["beach", "relaxation"],
        }

        from ai_engine.conversation.orchestrator import handle_chat
        result = await handle_chat("user1", "", image_bytes=b"fake_image_bytes")

        assert result["image_features"] is not None
        assert result["image_features"]["vibe"] == "sunny beach"
