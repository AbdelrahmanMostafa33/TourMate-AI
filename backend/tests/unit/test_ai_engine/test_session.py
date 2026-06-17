# backend/tests/unit/test_ai_engine/test_session.py

"""
Unit tests for the ConversationState session manager components.

Tests cover:
    - ConversationPhase enum values
    - TripSlots: missing_required, is_complete, to_dict/from_dict, merge
    - ChatMessage: serialization, timestamp auto-generation
    - ConversationState: serialization round-trip, phase transitions, mutations
"""

import pytest
from ai_engine.memory.conversation_state import (
    ChatMessage,
    ConversationPhase,
    ConversationState,
    TripSlots,
)


# ── ConversationPhase Tests ───────────────────────────────────────────────────

class TestConversationPhase:
    """Verify the phase enum has all expected values."""

    def test_all_phases_exist(self):
        assert ConversationPhase.GREETING.value == "greeting"
        assert ConversationPhase.SLOT_FILLING.value == "slot_filling"
        assert ConversationPhase.PLAN_GENERATION.value == "plan_generation"
        assert ConversationPhase.ITINERARY_REVIEW.value == "itinerary_review"
        assert ConversationPhase.COMPLETED.value == "completed"

    def test_phase_count(self):
        assert len(ConversationPhase) == 5


# ── TripSlots Tests ───────────────────────────────────────────────────────────

class TestTripSlots:

    def test_defaults_are_none(self):
        slots = TripSlots()
        assert slots.destination_city is None
        assert slots.duration_days is None
        assert slots.group_size is None
        assert slots.special_requests is None

    def test_missing_required_both_missing(self):
        slots = TripSlots()
        missing = slots.missing_required()
        assert "destination" in missing
        assert "duration" in missing

    def test_missing_required_only_duration(self):
        slots = TripSlots(destination_city="Paris")
        missing = slots.missing_required()
        assert "destination" not in missing
        assert "duration" in missing

    def test_missing_required_only_destination(self):
        slots = TripSlots(duration_days=5)
        missing = slots.missing_required()
        assert "destination" in missing
        assert "duration" not in missing

    def test_is_complete_when_both_filled(self):
        slots = TripSlots(destination_city="Paris", duration_days=5)
        assert slots.is_complete() is True

    def test_is_complete_when_partial(self):
        slots = TripSlots(destination_city="Paris")
        assert slots.is_complete() is False

    def test_to_dict_round_trip(self):
        slots = TripSlots(
            destination_city="Cairo",
            destination_country="Egypt",
            duration_days=3,
            travel_dates="2026-07-01 to 2026-07-03",
            group_size=2,
            special_requests="museums and food",
        )
        d = slots.to_dict()
        restored = TripSlots.from_dict(d)
        assert restored.destination_city == "Cairo"
        assert restored.destination_country == "Egypt"
        assert restored.duration_days == 3
        assert restored.group_size == 2
        assert restored.special_requests == "museums and food"

    def test_merge_overwrites_none_fields(self):
        slots = TripSlots()
        intent = {
            "destination_city": "Paris",
            "duration_days": 4,
            "group_size": 2,
        }
        slots.merge(intent)
        assert slots.destination_city == "Paris"
        assert slots.duration_days == 4
        assert slots.group_size == 2

    def test_merge_overwrites_existing_non_none_fields(self):
        slots = TripSlots(destination_city="London", duration_days=7)
        intent = {"destination_city": "Paris", "duration_days": 3}
        slots.merge(intent)
        assert slots.destination_city == "Paris"
        assert slots.duration_days == 3

    def test_merge_ignores_none_values(self):
        slots = TripSlots(destination_city="London")
        intent = {"destination_city": None, "duration_days": None}
        slots.merge(intent)
        assert slots.destination_city == "London"
        assert slots.duration_days is None

    def test_merge_accumulates_interests(self):
        slots = TripSlots()
        slots.merge({"special_requests": "museums"})
        assert slots.interests == ["museums"]
        # Second merge should not overwrite interests (already set)
        slots.merge({"special_requests": "food"})
        assert slots.interests == ["museums"]  # unchanged


# ── ChatMessage Tests ─────────────────────────────────────────────────────────

class TestChatMessage:

    def test_auto_timestamp(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.timestamp != ""
        # Should be an ISO format string
        assert "T" in msg.timestamp

    def test_explicit_timestamp(self):
        msg = ChatMessage(role="user", content="Hello", timestamp="2026-01-01T00:00:00")
        assert msg.timestamp == "2026-01-01T00:00:00"

    def test_to_dict_round_trip(self):
        msg = ChatMessage(role="assistant", content="Hi there!", metadata={"intent_type": "greeting"})
        d = msg.to_dict()
        restored = ChatMessage.from_dict(d)
        assert restored.role == "assistant"
        assert restored.content == "Hi there!"
        assert restored.metadata == {"intent_type": "greeting"}

    def test_to_dict_strips_none_metadata(self):
        msg = ChatMessage(role="user", content="Hello")
        d = msg.to_dict()
        assert "metadata" not in d

    def test_from_dict_without_metadata(self):
        d = {"role": "user", "content": "Hello", "timestamp": "2026-01-01T00:00:00"}
        msg = ChatMessage.from_dict(d)
        assert msg.metadata is None


# ── ConversationState Tests ───────────────────────────────────────────────────

class TestConversationState:

    def test_default_state(self):
        state = ConversationState(user_id="user123")
        assert state.user_id == "user123"
        assert state.phase == ConversationPhase.GREETING
        assert state.turn_count == 0
        assert state.itinerary is None
        assert len(state.history) == 0

    def test_to_dict_from_dict_round_trip(self):
        state = ConversationState(user_id="user123")
        state.slots.merge({"destination_city": "Paris", "duration_days": 5})
        state.add_user_message("Hello!")
        state.add_user_message("Where should I go?")

        d = state.to_dict()
        restored = ConversationState.from_dict(d)

        assert restored.session_id == state.session_id
        assert restored.user_id == "user123"
        assert restored.phase == ConversationPhase.GREETING
        assert restored.slots.destination_city == "Paris"
        assert restored.slots.duration_days == 5
        assert len(restored.history) == 2
        assert restored.turn_count == 2

    def test_add_user_message_increments_turn_count(self):
        state = ConversationState(user_id="user1")
        assert state.turn_count == 0
        state.add_user_message("Hello")
        assert state.turn_count == 1
        state.add_user_message("World")
        assert state.turn_count == 2

    def test_add_assistant_message_does_not_increment_turn_count(self):
        state = ConversationState(user_id="user1")
        state.add_user_message("Hello")
        state.add_assistant_message("Hi!")
        assert state.turn_count == 1  # only user messages count

    def test_transition_to(self):
        state = ConversationState(user_id="user1")
        assert state.phase == ConversationPhase.GREETING
        state.transition_to(ConversationPhase.SLOT_FILLING)
        assert state.phase == ConversationPhase.SLOT_FILLING

    def test_set_itinerary_transitions_to_review(self):
        state = ConversationState(user_id="user1")
        state.transition_to(ConversationPhase.PLAN_GENERATION)
        state.set_itinerary({"days": [{"day_number": 1}]})
        assert state.phase == ConversationPhase.ITINERARY_REVIEW
        assert state.itinerary == {"days": [{"day_number": 1}]}

    def test_approve_itinerary_transitions_to_completed(self):
        state = ConversationState(user_id="user1")
        state.set_itinerary({"days": []})
        state.approve_itinerary(itinerary_id="trip_abc")
        assert state.phase == ConversationPhase.COMPLETED
        assert state.itinerary_id == "trip_abc"

    def test_reset_for_new_trip(self):
        state = ConversationState(user_id="user1")
        state.set_itinerary({"days": []})
        state.add_user_message("Hello")
        state.approve_itinerary(itinerary_id="trip_abc")

        session_id_before = state.session_id
        state.reset_for_new_trip()

        # Session ID preserved
        assert state.session_id == session_id_before
        # But state is reset
        assert state.phase == ConversationPhase.SLOT_FILLING
        assert state.itinerary is None
        assert state.itinerary_id is None
        assert state.turn_count == 0
        assert len(state.history) == 0

    def test_history_trimming(self):
        state = ConversationState(user_id="user1", max_history=5)
        for i in range(10):
            state.add_user_message(f"Message {i}")
        assert len(state.history) == 5
        # Should keep the last 5
        assert state.history[0].content == "Message 5"
        assert state.history[4].content == "Message 9"

    def test_get_system_context(self):
        state = ConversationState(user_id="user1")
        state.transition_to(ConversationPhase.SLOT_FILLING)
        state.slots.merge({"destination_city": "Paris", "duration_days": 5})
        state.add_user_message("I want to visit Paris")

        context = state.get_system_context()
        assert "slot_filling" in context
        assert "Paris" in context
        assert "5 days" in context

    def test_full_lifecycle(self):
        """Test the complete conversation lifecycle from greeting to completion."""
        state = ConversationState(user_id="user1")

        # Greeting
        assert state.phase == ConversationPhase.GREETING
        state.transition_to(ConversationPhase.SLOT_FILLING)

        # Slot filling
        state.slots.merge({"destination_city": "Cairo"})
        assert not state.slots.is_complete()
        state.slots.merge({"duration_days": 3})
        assert state.slots.is_complete()

        # Plan generation
        state.transition_to(ConversationPhase.PLAN_GENERATION)
        assert state.phase == ConversationPhase.PLAN_GENERATION

        # Itinerary review
        state.set_itinerary({"days": [{"day_number": 1, "stops": []}]})
        assert state.phase == ConversationPhase.ITINERARY_REVIEW

        # Approval
        state.approve_itinerary(itinerary_id="trip_456")
        assert state.phase == ConversationPhase.COMPLETED
