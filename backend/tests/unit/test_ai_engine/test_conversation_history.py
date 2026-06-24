# backend/tests/unit/test_ai_engine/test_conversation_history.py

"""
Unit tests for conversation_history.py message builders.

Tests cover:
    - build_messages_for_phase (phase-aware message construction)
    - build_clarification_messages
    - build_general_chat_messages
    - get_missing_fields_from_state
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ai_engine.memory.conversation_state import (
    ConversationPhase,
    ConversationState,
    TripSlots,
)
from ai_engine.memory.conversation_history import (
    build_clarification_messages,
    build_general_chat_messages,
    build_messages_for_phase,
    get_missing_fields_from_state,
)


# ── build_messages_for_phase Tests ────────────────────────────────────────────

class TestBuildMessagesForPhase:

    def test_greeting_phase(self):
        state = ConversationState(user_id="user1")
        messages = build_messages_for_phase(state, "Hello!")
        assert len(messages) >= 2
        # First message should be system prompt
        assert isinstance(messages[0], SystemMessage)
        assert "greet" in messages[0].content.lower() or "tourmate" in messages[0].content.lower()
        # Last message should be user input
        assert isinstance(messages[-1], HumanMessage)
        assert messages[-1].content == "Hello!"

    def test_slot_filling_includes_history(self):
        state = ConversationState(user_id="user1")
        state.transition_to(ConversationPhase.SLOT_FILLING)
        state.add_user_message("I want to go to Paris")
        state.add_assistant_message("Great! How many days?")

        messages = build_messages_for_phase(state, "5 days")
        assert isinstance(messages[0], SystemMessage)
        # Should include history messages
        contents = [m.content for m in messages]
        assert any("Paris" in c for c in contents)
        assert any("5 days" in c for c in contents)

    def test_itinerary_review_includes_itinerary(self):
        state = ConversationState(user_id="user1")
        state.set_itinerary({"days": [{"day_number": 1, "stops": []}]})

        messages = build_messages_for_phase(state, "Can we change the hotel?")
        assert isinstance(messages[0], SystemMessage)
        # System prompt should mention itinerary
        assert "itinerary" in messages[0].content.lower()

    def test_completed_phase(self):
        state = ConversationState(user_id="user1")
        state.approve_itinerary(itinerary_id="trip_123")

        messages = build_messages_for_phase(state, "Thanks!")
        assert isinstance(messages[0], SystemMessage)
        assert "approved" in messages[0].content.lower() or "great" in messages[0].content.lower()


# ── build_clarification_messages Tests ────────────────────────────────────────

class TestBuildClarificationMessages:

    def test_returns_list_of_messages(self):
        messages = build_clarification_messages(["destination", "duration"])
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_first_message_is_system(self):
        messages = build_clarification_messages(["destination"])
        assert isinstance(messages[0], SystemMessage)
        assert "destination" in messages[0].content.lower()

    def test_last_message_is_human(self):
        messages = build_clarification_messages(["duration"])
        assert isinstance(messages[-1], HumanMessage)

    def test_with_history(self):
        history = [
            {"role": "user", "content": "I want to plan a trip"},
            {"role": "assistant", "content": "Where would you like to go?"},
        ]
        messages = build_clarification_messages(["duration"], history=history)
        contents = [m.content for m in messages]
        assert any("plan a trip" in c for c in contents)


# ── build_general_chat_messages Tests ─────────────────────────────────────────

class TestBuildGeneralChatMessages:

    def test_returns_list(self):
        messages = build_general_chat_messages("Is Cairo safe?")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_user_message(self):
        messages = build_general_chat_messages("What's the best time to visit?")
        contents = [m.content for m in messages]
        assert any("best time" in c for c in contents)

    def test_with_image_context(self):
        messages = build_general_chat_messages(
            "Tell me about this place",
            image_context="[Image: beach resort, tropical]"
        )
        contents = [m.content for m in messages]
        assert any("beach resort" in c for c in contents)


# ── get_missing_fields_from_state Tests ───────────────────────────────────────

class TestGetMissingFields:

    def test_all_missing(self):
        state = ConversationState(user_id="user1")
        missing = get_missing_fields_from_state(state)
        assert "destination" in missing
        assert "duration" in missing

    def test_destination_filled(self):
        state = ConversationState(user_id="user1")
        state.slots.destination_city = "Paris"
        missing = get_missing_fields_from_state(state)
        assert "destination" not in missing
        assert "duration" in missing

    def test_all_filled(self):
        state = ConversationState(user_id="user1")
        state.slots.destination_city = "Paris"
        state.slots.duration_days = 5
        state.slots.travel_dates = "next month"
        state.slots.group_size = 2
        state.slots.traveler_group_type = "solo"
        state.slots.budget_level = "moderate"
        state.slots.travel_style = "cultural"
        state.slots.pace = "balanced"
        state.slots.interests = ["history", "food"]
        state.slots.food_preferences = ["local cuisine"]
        state.slots.accommodation_preferences = ["hotel"]
        missing = get_missing_fields_from_state(state)
        assert len(missing) == 0
