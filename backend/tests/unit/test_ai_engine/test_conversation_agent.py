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
    """Build a complete plan_trip RouterResult with all required fields."""
    return _make_router_result(
        "plan_trip", response="Generating your itinerary!",
        destination_city=city, duration_days=days,
        travel_dates="next month", group_size=2, traveler_group_type="solo",
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


# ── handle_chat_stream Tests ──────────────────────────────────────────────────

class TestHandleChatStream:
    """Tests for the handle_chat_stream() async generator."""

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    async def test_yields_result_event_when_itinerary_is_generated(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        # Given: a valid itinerary is generated
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Cairo", 2)
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result(is_valid=True)

        from ai_engine.chat.conversation_agent import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_1",
            user_message="Plan me a 2-day trip to Cairo",
        ):
            events.append(chunk)

        # Then: events should be in correct order:
        #   session → phase → text... → result → done
        event_types = [e["type"] for e in events]
        assert event_types[0] == "session", f"First event should be 'session', got {event_types[0]}"
        assert event_types[1] == "phase", f"Second event should be 'phase', got {event_types[1]}"
        # All events between phase and result should be "text" tokens
        text_events = event_types[2:-2]
        assert all(t == "text" for t in text_events), (
            f"Expected only 'text' events between phase and result, got {event_types[2:-2]}"
        )
        assert event_types[-2] == "result", f"Second-to-last should be 'result', got {event_types[-2]}"
        assert event_types[-1] == "done", f"Last event should be 'done', got {event_types[-1]}"

        # And: the "result" event has the itinerary data
        result_event = next(e for e in events if e["type"] == "result")
        result_data = result_event["data"]
        assert result_data["message"] != ""
        assert result_data["itinerary"] is not None
        assert "days" in result_data["itinerary"]
        assert len(result_data["itinerary"]["days"]) == 1
        assert result_data["itinerary"]["days"][0]["stops"][0]["name"] == "Pyramids of Giza"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    async def test_does_not_yield_result_event_when_no_itinerary(
        self, mock_route, mock_get_manager, mock_manager
    ):
        # Given: the router asks a clarification question (no itinerary)
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result(
            "ask_clarification", "Where would you like to go?",
            destination_city="Cairo",
        )

        from ai_engine.chat.conversation_agent import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_2",
            user_message="I want to visit Cairo",
        ):
            events.append(chunk)

        # Then: no "result" event should be present
        event_types = [e["type"] for e in events]
        assert "result" not in event_types, (
            f"Unexpected 'result' event in clarification response: {event_types}"
        )

        # And: the last event should be "done"
        assert event_types[-1] == "done"

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    async def test_yields_session_event_first(
        self, mock_route, mock_get_manager, mock_manager
    ):
        # Given: any response
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result(
            "answer_question", "I'm here to help!"
        )

        from ai_engine.chat.conversation_agent import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_3",
            user_message="Hello",
        ):
            events.append(chunk)

        # Then: the first event is always "session" with session_id
        first = events[0]
        assert first["type"] == "session"
        assert "session_id" in first["data"]
        assert first["data"]["phase"] is not None

    @pytest.mark.asyncio
    @patch("ai_engine.chat.conversation_agent.get_session_manager")
    @patch("ai_engine.chat.conversation_agent.route_message")
    @patch("ai_engine.chat.conversation_agent.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.chat.conversation_agent.load_mock_profile")
    async def test_result_event_contains_correct_phase(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        # Given: a valid itinerary is generated
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Paris", 3)
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result(is_valid=True)

        from ai_engine.chat.conversation_agent import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_4",
            user_message="Plan me a 3-day trip to Paris",
        ):
            events.append(chunk)

        # Then: the result event has phase == "itinerary_review"
        result_event = next(e for e in events if e["type"] == "result")
        assert result_event["data"]["phase"] == "itinerary_review"
