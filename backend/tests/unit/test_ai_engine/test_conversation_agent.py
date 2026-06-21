# tests/unit/test_ai_engine/test_conversation_agent.py
"""Tests for conversation_agent.py with unified router architecture."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.chat.unified_router import RouterResult
from ai_engine.memory.conversation_state import ConversationPhase, ConversationState


# ── Shared Mock Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_manager():
    storage = {}
    manager = AsyncMock()

    async def fake_resume_or_create(user_id, session_id=None):
        if session_id and session_id in storage:
            return storage[session_id]
        if user_id in storage:
            return storage[user_id]
        state = ConversationState(user_id=user_id)
        storage[user_id] = state
        return state

    async def fake_save(state):
        storage[state.user_id] = state
        return True

    manager.resume_or_create = fake_resume_or_create
    manager.save = fake_save
    return manager


def _make_router_result(action, response="OK", **extracted):
    """Build a mock RouterResult."""
    return RouterResult(action=action, extracted=extracted, response=response)


def _make_plan_result(city, days, **extra):
    """Build a complete plan_trip RouterResult."""
    return _make_router_result(
        "plan_trip", response="Generating your itinerary!",
        destination_city=city, duration_days=days,
        budget_level="moderate", travel_style="cultural", pace="moderate",
        interests=["history", "food"], food_preferences=["local cuisine"],
        accommodation_preferences=["hotel"], **extra,
    )


def _make_mock_graph_result(is_valid=True):
    """Build a mock LangGraph pipeline result.

    Args:
        is_valid: If True, the itinerary passed validation (normal success).
                  If False, simulates stale state from a retry loop.
    """
    return {
        "optimized_itinerary": {
            "days": [{"day_number": 1, "stops": [
                {"name": "Pyramids of Giza", "start_time": "09:00"},
                {"name": "Egyptian Museum", "start_time": "14:00"},
            ]}]
        },
        "is_valid": is_valid,
    }


# ── GREETING Phase Tests ──────────────────────────────────────────────────────

class TestGreetingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    async def test_greeting_general_chat_stays_in_greeting(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result("answer_question", "Hi! I'm TourMate. Ready to plan a trip?")

        from ai_engine.chat.conversation_agent import handle_chat
        result = await handle_chat("user1", "Hello!")

        assert result["response_type"] == "chat"
        assert "session_id" in result
        assert result["phase"] == "greeting"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    async def test_greeting_plan_trip_transitions_to_slot_filling(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result("ask_clarification", "Where would you like to go?")

        from ai_engine.chat.conversation_agent import handle_chat
        result = await handle_chat("user1", "Plan me a trip")

        assert result["response_type"] == "clarification"
        assert result["phase"] == "slot_filling"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    async def test_greeting_complete_info_skips_to_plan_generation(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Paris", 5)
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        from ai_engine.chat.conversation_agent import handle_chat
        result = await handle_chat("user1", "Plan me a 5-day trip to Paris")

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None
        assert result["phase"] == "itinerary_review"


# ── SLOT_FILLING Phase Tests ─────────────────────────────────────────────────

class TestSlotFillingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    async def test_slot_filling_partial_info_asks_clarification(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager

        # First turn: greeting -> slot_filling (partial info)
        mock_route.return_value = _make_router_result("ask_clarification", "How many days?", destination_city="Cairo")

        from ai_engine.chat.conversation_agent import handle_chat
        result1 = await handle_chat("user1", "I want to visit Cairo")
        assert result1["phase"] == "slot_filling"

        # Second turn: complete info -> plan
        mock_route.return_value = _make_plan_result("Cairo", 3)
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        result2 = await handle_chat("user1", "3 days, moderate budget, cultural")
        assert result2["response_type"] == "itinerary"
        assert result2["phase"] == "itinerary_review"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    async def test_slot_filling_general_chat_stays_in_slot_filling(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager

        # First turn: greeting -> slot_filling
        mock_route.return_value = _make_router_result("ask_clarification", "How many days?", destination_city="Paris")

        from ai_engine.chat.conversation_agent import handle_chat
        await handle_chat("user1", "I want to visit Paris")

        # Second turn: general question
        mock_route.return_value = _make_router_result("answer_question", "Paris is beautiful in spring!")
        result = await handle_chat("user1", "Is Paris safe?")

        assert result["response_type"] == "chat"
        assert result["phase"] == "slot_filling"


# ── ITINERARY_REVIEW Phase Tests ──────────────────────────────────────────────

class TestItineraryReviewPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    async def test_review_approve_transitions_to_completed(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        from ai_engine.chat.conversation_agent import handle_chat

        # Generate itinerary first
        mock_route.return_value = _make_plan_result("Paris", 3)
        result1 = await handle_chat("user1", "Plan me a 3-day trip to Paris")
        assert result1["phase"] == "itinerary_review"

        # Approve
        mock_route.return_value = _make_router_result("approve_itinerary", "Awesome! Have an amazing trip!")
        result2 = await handle_chat("user1", "Looks good, approve!")

        assert result2["response_type"] == "chat"
        
