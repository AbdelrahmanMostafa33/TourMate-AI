"""
Trace test: verify that hotel type modifications during HOTEL_SELECTION
return response_type="chat" (not "itinerary") and don't include
replace_itinerary_card actions.

This is a focused diagnostic test to trace exactly where an itinerary
card might be leaking through during hotel modifications.
"""

import pytest
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Test 1: Direct unit test of _run_hotel_selection_and_present
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_hotel_type_change_returns_chat():
    """Directly call _run_hotel_selection_and_present with acc_type_change.

    This bypasses the LLM and tests the internal function directly.
    """
    from ai_engine.conversation.orchestrator import _run_hotel_selection_and_present
    from ai_engine.conversation.conversation_state import (
        ConversationState, ConversationPhase, TripSlots,
    )

    state = ConversationState()
    # Set up minimal state to look like we're during HOTEL_SELECTION
    state.phase = ConversationPhase.HOTEL_SELECTION
    state.itinerary = {
        "destination": "Cairo",
        "days": [
            {
                "day_number": 1,
                "theme": "Test",
                "stops": [{"id": "place1", "name": "Pyramids"}],
            }
        ],
        "accommodation_suggestions": [
            {
                "id": "hotel1",
                "name": "Test Hotel",
                "accommodation_type": "hotel",
                "lat": 30.0,
                "lon": 31.0,
                "rating": 4.0,
            }
        ],
    }
    state.slots.destination_city = "Cairo"
    state.slots.accommodation_preferences = ["hotel"]
    state.slots.budget_level = "moderate"

    # Override search_hotels_for_trip to avoid DB call
    import ai_engine.conversation.orchestrator as orch
    original_search = orch.hs_search_hotels
    orch.hs_search_hotels = _mock_search_hotels

    try:
        response = await _run_hotel_selection_and_present(
            state, "provide resorts", None,
            acc_type_change="resort",
        )
    finally:
        orch.hs_search_hotels = original_search

    logger.info("=== TEST 1: Direct _run_hotel_selection_and_present ===")
    logger.info("response_type: %s", response.get("response_type"))
    logger.info("has itinerary: %s", "itinerary" in response and response["itinerary"] is not None)
    logger.info("has accommodation_preferences: %s", response.get("accommodation_preferences"))
    logger.info("ui actions: %s", response.get("ui", {}).get("actions", []))

    assert response.get("response_type") == "chat", (
        f"Expected response_type='chat' but got '{response.get('response_type')}'"
    )
    # Unlike the original issue, we want itinerary data to be present for Flutter
    # to silently update accommodation_suggestions, but NOT as a card refresh
    assert response.get("itinerary") is not None, (
        "Itinerary data should still be present for Flutter to update silently"
    )
    # Should NOT have replace_itinerary_card action
    ui = response.get("ui") or {}
    actions = ui.get("actions", []) if isinstance(ui, dict) else []
    assert "replace_itinerary_card" not in actions, (
        "Should NOT have replace_itinerary_card action"
    )


async def _mock_search_hotels(
    city=None, accommodation_type=None, preferred_star_class=None,
    budget_level=None, max_results=10,
):
    """Mock that returns a 'resort' type hotel."""
    return [
        {
            "id": "resort1",
            "name": "Mock Resort",
            "category": "hotel",
            "accommodation_type": "resort",
            "sub_category": "resort",
            "lat": 30.1,
            "lon": 31.1,
            "rating": 4.5,
            "nightly_rate": 150,
            "price_level": 3,
            "address": "Mock Address",
            "photos": [],
        }
    ]


# ═════════════════════════════════════════════════════════════════════════════
# Test 2: Trace through all possible routes in _process_message_inner
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_all_three_routes_return_chat():
    """Trace each of the 3 code paths that handle hotel type changes.

    Path A: action='modify_itinerary' → _handle_select_hotel
    Path B: action='select_hotel' → _handle_select_hotel
    Path C: action='approve_itinerary' → HOTEL_SELECTION branch

    All three should return response_type='chat' with no itinerary card.
    """
    from ai_engine.conversation.orchestrator import (
        _handle_select_hotel, _run_hotel_selection_and_present,
    )
    from ai_engine.conversation.conversation_state import (
        ConversationState, ConversationPhase,
    )

    # Patch the search function — must patch orchestrator's local reference
    import ai_engine.conversation.orchestrator as orch

    original_search = orch.hs_search_hotels

    class MockRouterResult:
        """Minimal mock for router_result."""
        extracted = {}
        response = "Mock response"
        action = "select_hotel"

    try:
        orch.hs_search_hotels = _mock_search_hotels

        # ── Path A: simulate modify_itinerary action → _handle_select_hotel ──
        state_a = ConversationState()
        state_a.phase = ConversationPhase.HOTEL_SELECTION
        state_a.itinerary = _make_dummy_itinerary()
        state_a.slots.destination_city = "Cairo"
        state_a.slots.accommodation_preferences = ["hotel"]
        state_a.slots.budget_level = "moderate"

        msg = "provide resorts"
        router_result = MockRouterResult()
        response_a = await _handle_select_hotel(
            state_a, msg, router_result, None,
        )
        logger.info("=== PATH A: modify_itinerary → _handle_select_hotel ===")
        logger.info("  response_type: %s", response_a.get("response_type"))
        assert response_a.get("response_type") == "chat", (
            f"Path A: Expected 'chat' got '{response_a.get('response_type')}'"
        )

        # ── Path B: simulate select_hotel action → _handle_select_hotel ──
        state_b = ConversationState()
        state_b.phase = ConversationPhase.HOTEL_SELECTION
        state_b.itinerary = _make_dummy_itinerary()
        state_b.slots.destination_city = "Cairo"
        state_b.slots.accommodation_preferences = ["hotel"]
        state_b.slots.budget_level = "moderate"

        msg = "let it be resorts"
        router_result = MockRouterResult()
        response_b = await _handle_select_hotel(
            state_b, msg, router_result, None,
        )
        logger.info("=== PATH B: select_hotel → _handle_select_hotel ===")
        logger.info("  response_type: %s", response_b.get("response_type"))
        assert response_b.get("response_type") == "chat", (
            f"Path B: Expected 'chat' got '{response_b.get('response_type')}'"
        )

        # ── Path C: simulate approve_itinerary action during HOTEL_SELECTION ──
        state_c = ConversationState()
        state_c.phase = ConversationPhase.HOTEL_SELECTION
        state_c.itinerary = _make_dummy_itinerary()
        state_c.slots.destination_city = "Cairo"
        state_c.slots.accommodation_preferences = ["hotel"]
        state_c.slots.budget_level = "moderate"

        response_c = await _run_hotel_selection_and_present(
            state_c, "let it be resorts", None,
            acc_type_change="resort",
        )
        logger.info("=== PATH C: approve_itinerary → _run_hotel_selection ===")
        logger.info("  response_type: %s", response_c.get("response_type"))
        assert response_c.get("response_type") == "chat", (
            f"Path C: Expected 'chat' got '{response_c.get('response_type')}'"
        )

    finally:
        orch.hs_search_hotels = original_search


def _make_dummy_itinerary():
    return {
        "destination": "Cairo",
        "days": [
            {
                "day_number": 1,
                "theme": "Test",
                "stops": [{"id": "p1", "name": "Place 1"}],
            }
        ],
        "accommodation_suggestions": [
            {
                "id": "h1",
                "name": "Test Hotel",
                "accommodation_type": "hotel",
                "lat": 30.0, "lon": 31.0, "rating": 4.0,
            }
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# Test 3: Simulate the full _process_message_inner flow with mocked LLM
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_flow_with_mocked_interpreter():
    """Simulate the actual _process_message_inner with mocked interpreter.

    This is the closest we can get to production without running the LLM.
    We mock interpret_message to return a known action and verify the response.
    """
    import ai_engine.conversation.orchestrator as orch

    original_search = orch.hs_search_hotels
    original_interpreter = orch.interpret_message

    # Create a mock interpreter that returns specific actions
    call_count = {"n": 0}

    async def mock_interpret_message(state, message):
        call_count["n"] += 1
        action = "modify_itinerary"

        class MockResult:
            action = action
            response = f"Simulating: {action}"
            extracted = {
                "accommodation_preferences": ["hotel"],
            }

        return MockResult()

    try:
        orch.hs_search_hotels = _mock_search_hotels
        orch.interpret_message = mock_interpret_message

        from ai_engine.conversation.conversation_state import (
            ConversationState, ConversationPhase,
        )

        # Test simulate: user in HOTEL_SELECTION says "provide resorts"
        state = ConversationState()
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_dummy_itinerary()
        state.slots.destination_city = "Cairo"
        state.slots.accommodation_preferences = ["hotel"]
        state.slots.budget_level = "moderate"

        response = await orch._process_message(
            "test_user", state, "provide resorts", None, None,
        )

        logger.info("=== TEST 3: Full _process_message flow ===")
        logger.info("  response_type: %s", response.get("response_type"))
        logger.info("  has itinerary: %s", "itinerary" in response)
        logger.info("  ui actions: %s", response.get("ui", {}).get("actions", []))

        # This should be "chat" after our fixes
        assert response.get("response_type") == "chat", (
            f"Full flow: Expected 'chat' got '{response.get('response_type')}'"
        )

    finally:
        orch.hs_search_hotels = original_search
        orch.interpret_message = original_interpreter


# ═════════════════════════════════════════════════════════════════════════════
# Test 4: Trace handle_chat_stream result building
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_display_message_for_hotel_modification():
    """Check what _display_message_for_response returns for hotel modifications.

    This function determines the text streamed during a hotel modification.
    It should return a compact hotel count message, not an itinerary summary.
    """
    from ai_engine.conversation.orchestrator import _display_message_for_response
    from ai_engine.conversation.conversation_state import ConversationPhase

    response = {
        "response_type": "chat",
        "message": "Updated your accommodation options.\n\n1️⃣ Mock Resort ...",
        "itinerary": {
            "destination": "Cairo",
            "accommodation_suggestions": [
                {
                    "id": "resort1",
                    "name": "Mock Resort",
                    "accommodation_type": "resort",
                }
            ],
        },
        "accommodation_preferences": ["resort"],
    }

    streamed = _display_message_for_response(
        response, ConversationPhase.HOTEL_SELECTION.value,
    )
    logger.info("=== TEST 4: _display_message_for_response ===")
    logger.info("  streamed text: %s", streamed)

    # Should say "I found 1 hotel option" since we're in HOTEL_SELECTION phase
    assert "hotel option" in streamed, (
        f"Should say 'hotel option', got: {streamed}"
    )
    assert "itinerary" not in streamed.lower(), (
        "Streamed text should not mention 'itinerary'"
    )
