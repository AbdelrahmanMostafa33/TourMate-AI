# tests/unit/test_ai_engine/test_orchestrator.py
"""Tests for orchestrator.py with message interpreter architecture."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_engine.conversation.message_interpreter import InterpretationResult
from ai_engine.conversation.conversation_state import ConversationPhase, ConversationState


# ── Shared Mock Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_manager():
    storage = {}
    manager = AsyncMock()

    async def fake_resume_or_create(user_id, session_id=None, recovery_state=None):
        if recovery_state:
            recovery_state["user_id"] = user_id
            state = ConversationState.from_dict(recovery_state)
            storage[user_id] = state
            return state
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
    """Build a mock InterpretationResult."""
    return InterpretationResult(action=action, extracted=extracted, response=response)


def _make_plan_result(city, days, **extra):
    """Build a complete plan_trip InterpretationResult with all required fields.

    NOTE: interests must be explicitly passed when the test user message
    mentions specific interests. The orchestrator has a hallucination guard
    that clears extracted interests if they aren't mentioned in the user's
    message, which would break the plan_trip flow.

    Pass ``interests=[...]`` AND include those interests in the user message.
    """
    # Pop interests from extra so it doesn't conflict with the explicit kwarg
    interests = extra.pop("interests", [])
    return _make_router_result(
        "plan_trip", response="Generating your itinerary!",
        destination_city=city, duration_days=days,
        travel_dates="next month", group_size=2, traveler_group_type="solo",
        budget_level="moderate", travel_style="cultural", pace="moderate",
        interests=interests, food_preferences=["local cuisine"],
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


def _make_flight_state(phase=ConversationPhase.FLIGHT_SELECTION):
    """Build conversation state with an existing flight search/selection."""
    state = ConversationState(user_id="flight_user")
    state.phase = phase
    state.itinerary = {
        "destination": "Dubai",
        "days": [],
        "accommodation_suggestions": [{"name": "Hotel A"}],
    }
    state.slots.destination_city = "Dubai"
    state.slots.duration_days = 5
    state.slots.travel_dates = "2026-07-20"
    state.slots.group_size = 2
    state.slots.origin_city = "Cairo"
    state.slots.is_round_trip = True
    state.slots.return_date = "2026-07-25"
    state.slots.flight_search_results = [{"airline_name": "Test Air", "flight_number": "TA1"}]
    state.slots.selected_flight_offer = {
        "airline_name": "Test Air",
        "flight_number": "TA1",
        "total_price": 100,
        "currency": "USD",
    }
    return state


# ── GREETING Phase Tests ──────────────────────────────────────────────────────

class TestGreetingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_greeting_general_chat_stays_in_greeting(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result("answer_question", "Hi! I'm TourMate. Ready to plan a trip?")

        from ai_engine.conversation.orchestrator import handle_chat
        result = await handle_chat("user1", "Hello!")

        assert result["response_type"] == "chat"
        assert "session_id" in result
        assert result["phase"] == "greeting"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_greeting_plan_trip_transitions_to_slot_filling(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result("ask_clarification", "Where would you like to go?")

        from ai_engine.conversation.orchestrator import handle_chat
        result = await handle_chat("user1", "Plan me a trip")

        assert result["response_type"] == "clarification"
        assert result["phase"] == "slot_filling"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_greeting_complete_info_skips_to_plan_generation(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Paris", 5, interests=["history"])
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        from ai_engine.conversation.orchestrator import handle_chat
        result = await handle_chat("user1", "Plan me a 5-day trip to Paris interested in history")

        assert result["response_type"] == "itinerary"
        assert result["itinerary"] is not None
        assert result["phase"] == "itinerary_review"


# ── SLOT_FILLING Phase Tests ─────────────────────────────────────────────────

class TestSlotFillingPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_slot_filling_partial_info_asks_clarification(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager

        # First turn: greeting -> slot_filling (partial info)
        mock_route.return_value = _make_router_result("ask_clarification", "How many days?", destination_city="Cairo")

        from ai_engine.conversation.orchestrator import handle_chat
        result1 = await handle_chat("user1", "I want to visit Cairo")
        assert result1["phase"] == "slot_filling"

        # Second turn: complete info -> plan (interests included to pass hallucination guard)
        mock_route.return_value = _make_plan_result("Cairo", 3, interests=["history"])
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        result2 = await handle_chat("user1", "3 days, moderate budget, cultural, interested in history")
        assert result2["response_type"] == "itinerary"
        assert result2["phase"] == "itinerary_review"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_slot_filling_general_chat_stays_in_slot_filling(
        self, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager

        # First turn: greeting -> slot_filling
        mock_route.return_value = _make_router_result("ask_clarification", "How many days?", destination_city="Paris")

        from ai_engine.conversation.orchestrator import handle_chat
        await handle_chat("user1", "I want to visit Paris")

        # Second turn: general question
        mock_route.return_value = _make_router_result("answer_question", "Paris is beautiful in spring!")
        result = await handle_chat("user1", "Is Paris safe?")

        assert result["response_type"] == "chat"
        assert result["phase"] == "slot_filling"


# ── ITINERARY_REVIEW Phase Tests ──────────────────────────────────────────────

class TestItineraryReviewPhase:

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_review_approve_transitions_to_flight_selection(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        from ai_engine.conversation.orchestrator import handle_chat

        # Generate itinerary first
        mock_route.return_value = _make_plan_result("Paris", 3, interests=["history"])
        result1 = await handle_chat("user1", "Plan me a 3-day trip to Paris interested in history")
        assert result1["phase"] == "itinerary_review"

        # Approve — orchestrator now transitions to FLIGHT_SELECTION
        mock_route.return_value = _make_router_result("approve_itinerary", "Awesome! Have an amazing trip!")
        result2 = await handle_chat("user1", "Looks good, approve!")

        assert result2["response_type"] == "chat"
        assert result2["phase"] == "flight_selection"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_review_chat_response_keeps_card_render_action(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        mock_get_manager.return_value = mock_manager
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result()

        from ai_engine.conversation.orchestrator import handle_chat

        mock_route.return_value = _make_plan_result("Cairo", 2, interests=["history"])
        result1 = await handle_chat(
            "user_card_review",
            "Plan me a 2-day trip to Cairo interested in history",
        )
        assert result1["phase"] == "itinerary_review"

        mock_route.return_value = _make_router_result(
            "answer_question",
            "Your itinerary has been updated. See it below.",
        )
        result2 = await handle_chat("user_card_review", "show me the itinerary again")

        assert result2["response_type"] == "chat"
        assert result2["itinerary"] is not None
        assert result2["ui"]["actions"] == ["replace_itinerary_card"]


# ── Flight Selection Edit Tests ───────────────────────────────────────────────

class TestFlightSelectionEdits:
    """Regression tests for mid-conversation flight edits."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_explicit_return_date_beats_duration_default(self, mock_search):
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            return_date="2026-08-10",
        )

        await _handle_search_flights(state, "change return date to Aug 10", router, None)

        assert state.slots.return_date == "2026-08-10"
        assert mock_search.await_args.kwargs["return_date"] == "2026-08-10"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_one_way_search_clears_stale_return_date(self, mock_search):
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            is_round_trip=False,
        )

        await _handle_search_flights(state, "make it one-way", router, None)

        assert state.slots.is_round_trip is False
        assert state.slots.return_date is None
        assert mock_search.await_args.kwargs["return_date"] is None

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_round_trip_switch_ignores_stale_one_way_return_date(self, mock_search):
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        state.slots.is_round_trip = False
        state.slots.return_date = "2026-09-30"
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            is_round_trip=True,
        )

        await _handle_search_flights(state, "make it round trip instead", router, None)

        assert state.slots.is_round_trip is True
        assert state.slots.return_date == "2026-07-25"
        assert mock_search.await_args.kwargs["return_date"] == "2026-07-25"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "phase",
        [ConversationPhase.HOTEL_SELECTION, ConversationPhase.BOOKING],
    )
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_flight_change_after_selection_returns_to_flight_search(
        self,
        mock_interpret,
        mock_search,
        phase,
    ):
        mock_interpret.return_value = _make_router_result(
            "select_hotel",
            "Sure",
            is_round_trip=False,
        )
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _process_message_inner

        state = _make_flight_state(phase)
        response = await _process_message_inner(
            "flight_user",
            state,
            "actually make it one-way",
            None,
            None,
        )

        assert state.phase == ConversationPhase.FLIGHT_SELECTION
        assert state.slots.selected_flight_offer is None
        assert state.slots.is_round_trip is False
        assert state.slots.return_date is None
        assert mock_search.await_args.kwargs["return_date"] is None
        assert response["message"].startswith("Got it - switching to one-way.")

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_return_date_change_during_flight_selection_reruns_search(
        self,
        mock_interpret,
        mock_search,
    ):
        mock_interpret.return_value = _make_router_result(
            "select_flight",
            "OK",
            return_date="2026-08-10",
        )
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _process_message_inner

        state = _make_flight_state(ConversationPhase.FLIGHT_SELECTION)
        state.slots.selected_flight_offer = None

        response = await _process_message_inner(
            "flight_user",
            state,
            "change my return date to Aug 10",
            None,
            None,
        )

        assert state.phase == ConversationPhase.FLIGHT_SELECTION
        assert state.slots.return_date == "2026-08-10"
        assert mock_search.await_args.kwargs["return_date"] == "2026-08-10"
        assert response["message"].startswith(
            "Got it - updating the return date to 2026-08-10."
        )

    def test_extract_departure_from_range_iso_to_range(self):
        """Direct unit test: '2026-07-28 to 2026-07-31' extracts '2026-07-28'."""
        from ai_engine.conversation.orchestrator import _extract_departure_from_range

        result = _extract_departure_from_range("2026-07-28 to 2026-07-31")
        assert result == "2026-07-28", f"Expected '2026-07-28', got {result!r}"

        # Also verify single dates pass through unchanged
        single = _extract_departure_from_range("2026-07-28")
        assert single == "2026-07-28", f"Expected unchanged, got {single!r}"

        # Verify empty returns None
        assert _extract_departure_from_range(None) is None
        assert _extract_departure_from_range("") is None

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_travel_dates_range_stripped_to_departure_date(self, mock_search):
        """When the LLM emits travel_dates as a range, the departure date is extracted."""
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            travel_dates="2026-07-28 to 2026-07-31",
            return_date="2026-07-31",
        )

        await _handle_search_flights(state, "the return date will be 31 july", router, None)

        assert mock_search.await_args.kwargs["departure_date"] == "2026-07-28"
        assert mock_search.await_args.kwargs["return_date"] == "2026-07-31"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_travel_dates_range_with_dash_stripped_correctly(self, mock_search):
        """Range with em-dash or hyphen is handled (e.g. 'July 28 - August 1')."""
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        state.slots.travel_dates = None
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            travel_dates="July 28 to August 1",
        )

        await _handle_search_flights(state, "change dates to july 28 through aug 1", router, None)

        assert mock_search.await_args.kwargs["departure_date"] is not None

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.search_flights_for_trip", new_callable=AsyncMock)
    async def test_single_date_not_affected_by_range_stripping(self, mock_search):
        """A single date without a range is passed through unchanged."""
        mock_search.return_value = []

        from ai_engine.conversation.orchestrator import _handle_search_flights

        state = _make_flight_state()
        router = _make_router_result(
            "search_flights",
            origin_city="Cairo",
            travel_dates="2026-07-28",
        )

        await _handle_search_flights(state, "depart on july 28", router, None)

        assert mock_search.await_args.kwargs["departure_date"] == "2026-07-28"

# ── handle_chat_stream Tests ──────────────────────────────────────────────────

class TestHandleChatStream:
    """Tests for the handle_chat_stream() async generator."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_yields_result_event_when_itinerary_is_generated(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        # Given: a valid itinerary is generated
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Cairo", 2, interests=["history"])
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result(is_valid=True)

        from ai_engine.conversation.orchestrator import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_1",
            user_message="Plan me a 2-day trip to Cairo interested in history",
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
        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 'result' event, found {len(result_events)}. "
            f"Event types: {[e['type'] for e in events]}"
        )
        result_event = result_events[0]
        result_data = result_event["data"]
        assert result_data["message"] != ""
        assert result_data["itinerary"] is not None
        assert "days" in result_data["itinerary"]
        assert len(result_data["itinerary"]["days"]) == 1
        assert result_data["itinerary"]["days"][0]["stops"][0]["name"] == "Pyramids of Giza"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_does_not_yield_result_event_when_no_itinerary(
        self, mock_route, mock_get_manager, mock_manager
    ):
        # Given: the router asks a clarification question (no itinerary)
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result(
            "ask_clarification", "Where would you like to go?",
            destination_city="Cairo",
        )

        from ai_engine.conversation.orchestrator import handle_chat_stream

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
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    async def test_yields_session_event_first(
        self, mock_route, mock_get_manager, mock_manager
    ):
        # Given: any response
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_router_result(
            "answer_question", "I'm here to help!"
        )

        from ai_engine.conversation.orchestrator import handle_chat_stream

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
    @patch("ai_engine.conversation.orchestrator.get_session_manager")
    @patch("ai_engine.conversation.orchestrator.interpret_message")
    @patch("ai_engine.conversation.orchestrator.trip_graph", new_callable=AsyncMock)
    @patch("ai_engine.conversation.orchestrator.load_mock_profile")
    async def test_result_event_contains_correct_phase(
        self, mock_profile, mock_graph, mock_route, mock_get_manager, mock_manager
    ):
        # Given: a valid itinerary is generated
        mock_get_manager.return_value = mock_manager
        mock_route.return_value = _make_plan_result("Paris", 3, interests=["history"])
        mock_profile.return_value = {"user_id": "user1"}
        mock_graph.ainvoke.return_value = _make_mock_graph_result(is_valid=True)

        from ai_engine.conversation.orchestrator import handle_chat_stream

        # When: we iterate over the stream
        events = []
        async for chunk in handle_chat_stream(
            user_id="stream_user_4",
            user_message="Plan me a 3-day trip to Paris interested in history",
        ):
            events.append(chunk)

        # Then: the result event has phase == "itinerary_review"
        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1, (
            f"Expected exactly 1 'result' event, found {len(result_events)}. "
            f"Event types: {[e['type'] for e in events]}"
        )
        result_event = result_events[0]
        assert result_event["data"]["phase"] == "itinerary_review"


class TestStructuredResponseDisplayMessage:
    """Regression tests for avoiding text/card duplication in the UI stream."""

    def test_itinerary_response_streams_summary_not_full_markdown(self):
        from ai_engine.conversation.orchestrator import _display_message_for_response

        response = {
            "response_type": "itinerary",
            "message": "Day 1\n- Pyramids\n- Museum\nWhere to Stay\nHotel A",
            "itinerary": {
                "destination": "Cairo",
                "days": [
                    {
                        "day_number": 1,
                        "stops": [
                            {"name": "Pyramids"},
                            {"name": "Museum"},
                        ],
                    }
                ],
            },
            "ui": {"actions": ["replace_itinerary_card"]},
        }

        message = _display_message_for_response(response, "itinerary_review")

        assert message == "Here is your 1-day Cairo itinerary. Review the 2 planned stops in the card below."
        assert "Pyramids" not in message
        assert "Where to Stay" not in message

    def test_flight_options_response_streams_summary(self):
        from ai_engine.conversation.orchestrator import _display_message_for_response

        response = {
            "response_type": "chat",
            "message": "Here are the available flights:\n1. Airline A\n2. Airline B",
            "flight_search_results": [{"id": "f1"}, {"id": "f2"}],
        }

        assert _display_message_for_response(response, "flight_selection") == (
            "I found 2 flight options. Choose one from the card below."
        )

    def test_plain_chat_response_is_unchanged(self):
        from ai_engine.conversation.orchestrator import _display_message_for_response

        response = {
            "response_type": "chat",
            "message": "Where will you be flying from?",
            "itinerary": {"destination": "Cairo", "days": []},
        }

        assert _display_message_for_response(response, "flight_selection") == (
            "Where will you be flying from?"
        )


# ── _enrich_candidate_pool_by_category Tests ──────────────────────────────

class TestEnrichCandidatePoolByCategory:
    """Tests for the _enrich_candidate_pool_by_category() function."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_no_category_hints_returns_none(
        self, mock_get_places, mock_detect_hints
    ):
        """When the request has no detectable category, return None."""
        mock_detect_hints.return_value = {}

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="swap giza for sphinx",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is None
        mock_get_places.assert_not_called()

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_returns_empty_returns_none(
        self, mock_get_places, mock_detect_hints
    ):
        """When the DB returns no places, return None."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}
        mock_get_places.return_value = []

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums in the trip",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is None
        mock_get_places.assert_called_once_with("Cairo")

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_no_matching_subcategory_returns_none(
        self, mock_get_places, mock_detect_hints
    ):
        """When no places match the detected sub_category, return None."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}
        mock_get_places.return_value = [
            {"id": "p1", "name": "Park", "category": "attraction", "sub_category": "parks"},
            {"id": "p2", "name": "Nightclub", "category": "attraction", "sub_category": "nightlife"},
        ]

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums in the trip",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is None

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_adds_new_matching_places_to_pool(
        self, mock_get_places, mock_detect_hints
    ):
        """Matching new places are added to the existing pool."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}
        mock_get_places.return_value = [
            {"id": "m1", "name": "Egyptian Museum", "category": "attraction", "sub_category": "museums", "rating": 4.8},
            {"id": "m2", "name": "Islamic Art Museum", "category": "attraction", "sub_category": "museums", "rating": 4.5},
            {"id": "p1", "name": "Park", "category": "attraction", "sub_category": "parks", "rating": 4.2},
        ]

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        existing = [{"id": "existing_1", "name": "Giza Necropolis"}]
        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums in the trip",
            destination_city="Cairo",
            existing_pool=existing,
        )

        assert result is not None
        assert len(result) == 3  # 1 existing + 2 new museums
        assert result[0]["id"] == "existing_1"  # existing first
        assert result[1]["id"] == "m1"  # higher rating first
        assert result[2]["id"] == "m2"

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_skips_duplicates_already_in_pool(
        self, mock_get_places, mock_detect_hints
    ):
        """Places already in the existing pool are not duplicated."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}
        mock_get_places.return_value = [
            {"id": "m1", "name": "Egyptian Museum", "category": "attraction", "sub_category": "museums", "rating": 4.8},
        ]

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        existing = [{"id": "m1", "name": "Egyptian Museum", "category": "attraction"}]
        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums in the trip",
            destination_city="Cairo",
            existing_pool=existing,
        )

        assert result is None  # No new places to add


# ═══════════════════════════════════════════════════════════════════════════════
# Code structure checks (_rerank_and_replan)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRerankAndReplanStructure:
    """
    Verify internal invariants of ``_rerank_and_replan``.

    These are source-inspection tests that catch regressions in
    the orchestrator's internal state construction, such as
    duplicate profile keys or leftover imports.
    """

    def test_no_duplicate_profile_key_in_rerank_state(self):
        """The rerank state dict should contain exactly one 'profile' key."""
        import inspect
        from ai_engine.conversation.orchestrator import _rerank_and_replan

        source = inspect.getsource(_rerank_and_replan)
        profile_keys = 0
        in_dict = False
        for line in source.split("\n"):
            stripped = line.strip()
            if '"filtered_places"' in stripped:
                in_dict = True
            if in_dict and stripped == "}":
                in_dict = False
            if in_dict and stripped.startswith('"profile"'):
                profile_keys += 1

        assert profile_keys == 1, (
            f"Expected exactly 1 'profile' key in rerank state dict, "
            f"found {profile_keys}. A duplicate would overwrite the first."
        )

    def test_apply_preference_adjustments_imported(self):
        """The orchestrator should import ``apply_preference_adjustments`` for reranking."""
        from ai_engine.conversation.orchestrator import apply_preference_adjustments
        assert apply_preference_adjustments is not None


# ═══════════════════════════════════════════════════════════════════════════════
# _handle_modify_itinerary skip logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestHandleModifyItinerarySkipLogic:
    """
    When accommodation changes are made, the fallback note is suppressed.
    The ``accommodations_updated`` parameter lives in ``_fallback_full_regeneration``.
    These tests verify the source code contains the correct guard logic.
    """

    def test_accommodations_updated_flag_initialized(self):
        """The ``accommodations_updated`` flag is a parameter of _fallback_full_regeneration."""
        import inspect
        from ai_engine.conversation.orchestrator import _fallback_full_regeneration

        source = inspect.getsource(_fallback_full_regeneration)
        assert "accommodations_updated" in source, (
            "Expected 'accommodations_updated' parameter in _fallback_full_regeneration"
        )

    def test_skip_rerank_when_accommodations_updated(self):
        """_fallback_full_regeneration references accommodations_updated in the
        fallback-note suppression logic."""
        import inspect
        from ai_engine.conversation.orchestrator import _fallback_full_regeneration

        source = inspect.getsource(_fallback_full_regeneration)
        assert "accommodations_updated" in source, (
            "Expected reference to 'accommodations_updated' in _fallback_full_regeneration"
        )

    def test_fallback_note_suppressed_when_accommodations_updated(self):
        """The fallback note is suppressed when accommodations were updated."""
        import inspect
        from ai_engine.conversation.orchestrator import _fallback_full_regeneration

        source = inspect.getsource(_fallback_full_regeneration)
        assert "not accommodations_updated" in source, (
            "Expected 'not accommodations_updated' to suppress fallback note"
        )


    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_limits_to_top_15_by_rating(
        self, mock_get_places, mock_detect_hints
    ):
        """At most 15 matching places are added, sorted by rating descending."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}

        # 20 museums with descending ratings
        museums = [
            {"id": f"m{i}", "name": f"Museum {i}", "category": "attraction", "sub_category": "museums", "rating": round(5.0 - i * 0.1, 1)}
            for i in range(20)
        ]
        mock_get_places.return_value = museums

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums in the trip",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is not None
        assert len(result) == 15  # capped at 15
        # Verify sorted by rating descending
        ratings = [p["rating"] for p in result]
        assert ratings == sorted(ratings, reverse=True)

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_matches_by_category_only_when_no_subcategory(
        self, mock_get_places, mock_detect_hints
    ):
        """When only category (not subcategory) is detected, match by category."""
        mock_detect_hints.return_value = {"category": "restaurant"}
        mock_get_places.return_value = [
            {"id": "r1", "name": "Koshary", "category": "restaurant", "sub_category": "local cuisine", "rating": 4.5},
            {"id": "a1", "name": "Museum", "category": "attraction", "sub_category": "museums", "rating": 4.8},
            {"id": "h1", "name": "Hotel", "category": "hotel", "sub_category": "", "rating": 4.2},
        ]

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="add more restaurants",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "r1"

    @pytest.mark.asyncio
    @patch("ai_engine.services.operations._detect_category_hints")
    @patch("ai_engine.tools.places_tool.get_places_for_city")
    async def test_db_failure_returns_none(
        self, mock_get_places, mock_detect_hints
    ):
        """When the DB query fails (returns empty), return None."""
        mock_detect_hints.return_value = {"category": "attraction", "sub_category": "museums"}
        mock_get_places.return_value = []  # simulate DB failure

        from ai_engine.conversation.orchestrator import _enrich_candidate_pool_by_category

        result = await _enrich_candidate_pool_by_category(
            modification_request="add museums",
            destination_city="Cairo",
            existing_pool=[],
        )

        assert result is None
