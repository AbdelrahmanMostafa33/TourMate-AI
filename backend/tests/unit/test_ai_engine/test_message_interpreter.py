# tests/unit/test_ai_engine/test_message_interpreter.py
"""Tests for the message interpreter module — helpers, models, and routing logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from ai_engine.conversation.message_interpreter import (
    _coerce_int,
    _build_extracted_dict,
    _build_itinerary_summary,
    _normalize_action,
    ExtractedSlots,
    InterpreterOutput,
    InterpretationResult,
    interpret_message,
)
from ai_engine.conversation.conversation_state import (
    ConversationState,
    ConversationPhase,
    TripSlots,
)


# ═══════════════════════════════════════════════════════════════════════════════
# _coerce_int tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoerceInt:
    def test_string_digit_returns_int(self):
        assert _coerce_int("3") == 3

    def test_int_returns_int(self):
        assert _coerce_int(5) == 5

    def test_string_non_digit_returns_none(self):
        assert _coerce_int("three") is None

    def test_none_returns_none(self):
        assert _coerce_int(None) is None

    def test_empty_string_returns_none(self):
        assert _coerce_int("") is None

    def test_float_string_returns_none(self):
        assert _coerce_int("3.5") is None

    def test_negative_string_returns_int(self):
        assert _coerce_int("-2") == -2

    def test_zero_string_returns_int(self):
        assert _coerce_int("0") == 0

    def test_float_returns_int(self):
        assert _coerce_int(3.7) == 3

    def test_bool_returns_int(self):
        # bool is subclass of int in Python
        assert _coerce_int(True) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _normalize_action tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalizeAction:
    def test_direct_aliases(self):
        assert _normalize_action("plan_trip") == "plan_trip"
        assert _normalize_action("ask_clarification") == "ask_clarification"
        assert _normalize_action("answer_question") == "answer_question"
        assert _normalize_action("approve_itinerary") == "approve_itinerary"
        assert _normalize_action("modify_itinerary") == "modify_itinerary"

    def test_action_aliases(self):
        assert _normalize_action("general_chat") == "answer_question"
        assert _normalize_action("clarify") == "ask_clarification"
        assert _normalize_action("confirm") == "approve_itinerary"
        assert _normalize_action("change") == "modify_itinerary"
        assert _normalize_action("approve") == "approve_itinerary"

    def test_flight_action_aliases(self):
        assert _normalize_action("search_flight") == "search_flights"
        assert _normalize_action("show_flights") == "search_flights"
        assert _normalize_action("find_flights") == "search_flights"
        assert _normalize_action("pick_flight") == "select_flight"
        assert _normalize_action("choose_flight") == "select_flight"
        assert _normalize_action("book_flight") == "select_flight"

    def test_hotel_action_aliases(self):
        assert _normalize_action("hotel_selection") == "select_hotel"
        assert _normalize_action("pick_hotel") == "select_hotel"
        assert _normalize_action("choose_hotel") == "select_hotel"

    def test_update_and_modify_aliases(self):
        assert _normalize_action("update") == "modify_itinerary"
        assert _normalize_action("modify") == "modify_itinerary"

    def test_unknown_defaults_to_answer_question(self):
        assert _normalize_action("something_unknown") == "answer_question"

    def test_case_insensitive(self):
        assert _normalize_action("Plan_Trip") == "plan_trip"
        assert _normalize_action("GENERAL_CHAT") == "answer_question"
        assert _normalize_action("Confirm") == "approve_itinerary"

    def test_whitespace_stripped(self):
        assert _normalize_action("  plan_trip  ") == "plan_trip"


# ═══════════════════════════════════════════════════════════════════════════════
# ExtractedSlots Pydantic model tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtractedSlots:
    def test_all_none_by_default(self):
        slots = ExtractedSlots()
        assert slots.destination_city is None
        assert slots.duration_days is None
        assert slots.budget_level is None
        assert slots.interests is None
        assert slots.origin_city is None
        assert slots.cabin_class is None

    def test_accepts_string_for_duration(self):
        slots = ExtractedSlots(duration_days="3")
        assert slots.duration_days == "3"

    def test_accepts_list_interests(self):
        slots = ExtractedSlots(interests=["history", "food"])
        assert slots.interests == ["history", "food"]

    def test_accepts_flight_fields(self):
        """selected_flight_number is coerced to int by BeforeValidator."""
        slots = ExtractedSlots(
            origin_city="Cairo",
            selected_flight_number="2",
            cabin_class="BUSINESS",
            is_round_trip=True,
            return_date="2026-07-30",
        )
        assert slots.origin_city == "Cairo"
        assert slots.selected_flight_number == 2  # coerced to int
        assert slots.cabin_class == "BUSINESS"
        assert slots.is_round_trip is True
        assert slots.return_date == "2026-07-30"

    def test_accepts_hotel_fields(self):
        """selected_hotel_number is coerced to int by BeforeValidator."""
        slots = ExtractedSlots(
            selected_hotel_name="Marriott",
            selected_hotel_number="1",
        )
        assert slots.selected_hotel_name == "Marriott"
        assert slots.selected_hotel_number == 1  # coerced to int

    def test_model_dump_excludes_none(self):
        slots = ExtractedSlots(destination_city="Cairo")
        d = slots.model_dump()
        assert d["destination_city"] == "Cairo"
        assert d["duration_days"] is None
        assert d["budget_level"] is None

    def test_invalid_action_rejected(self):
        """The action field is a Literal with specific values."""
        with pytest.raises(ValidationError):
            InterpreterOutput(
                action="invalid_action",
                extracted=ExtractedSlots(),
                response="test",
            )

    def test_valid_actions_accepted(self):
        """All valid actions should create InterpreterOutput successfully."""
        for action in [
            "plan_trip", "ask_clarification", "answer_question",
            "approve_itinerary", "modify_itinerary", "select_hotel",
            "search_flights", "select_flight",
        ]:
            output = InterpreterOutput(action=action, extracted=ExtractedSlots(), response="OK")
            assert output.action == action


# ═══════════════════════════════════════════════════════════════════════════════
# InterpretationResult tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpretationResult:
    def test_creates_with_all_fields(self):
        result = InterpretationResult(
            action="plan_trip",
            extracted={"destination_city": "Cairo", "duration_days": 3},
            response="Generating your itinerary!",
        )
        assert result.action == "plan_trip"
        assert result.extracted == {"destination_city": "Cairo", "duration_days": 3}
        assert result.response == "Generating your itinerary!"

    def test_empty_extracted(self):
        result = InterpretationResult(
            action="ask_clarification",
            extracted={},
            response="Where would you like to go?",
        )
        assert result.extracted == {}

    def test_has_slots_attribute(self):
        result = InterpretationResult(
            action="answer_question",
            extracted={"interests": ["history"]},
            response="Great choice!",
        )
        assert hasattr(result, "action")
        assert hasattr(result, "extracted")
        assert hasattr(result, "response")


# ═══════════════════════════════════════════════════════════════════════════════
# _build_extracted_dict tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildExtractedDict:
    def test_coerces_string_duration(self):
        slots = ExtractedSlots(duration_days="5")
        result = _build_extracted_dict(slots)
        assert result["duration_days"] == 5
        assert isinstance(result["duration_days"], int)

    def test_coerces_string_group_size(self):
        slots = ExtractedSlots(group_size="4")
        result = _build_extracted_dict(slots)
        assert result["group_size"] == 4
        assert isinstance(result["group_size"], int)

    def test_drops_none_values(self):
        slots = ExtractedSlots(destination_city="Paris")
        result = _build_extracted_dict(slots)
        assert "duration_days" not in result
        assert "budget_level" not in result

    def test_non_numeric_string_dropped(self):
        slots = ExtractedSlots(duration_days="three")
        result = _build_extracted_dict(slots)
        assert "duration_days" not in result

    def test_preserves_selected_hotel_name(self):
        slots = ExtractedSlots(selected_hotel_name="Marriott", selected_hotel_number=2)
        result = _build_extracted_dict(slots)
        assert result["selected_hotel_name"] == "Marriott"
        assert result["selected_hotel_number"] == 2

    def test_selected_hotel_number_as_string(self):
        slots = ExtractedSlots(selected_hotel_number="3")
        result = _build_extracted_dict(slots)
        assert result["selected_hotel_number"] == 3

    def test_preserves_origin_city(self):
        slots = ExtractedSlots(origin_city="London")
        result = _build_extracted_dict(slots)
        assert result["origin_city"] == "London"

    def test_preserves_selected_flight_number(self):
        slots = ExtractedSlots(selected_flight_number="1")
        result = _build_extracted_dict(slots)
        assert result["selected_flight_number"] == 1
        assert isinstance(result["selected_flight_number"], int)

    def test_preserves_cabin_class(self):
        slots = ExtractedSlots(cabin_class="FIRST")
        result = _build_extracted_dict(slots)
        assert result["cabin_class"] == "FIRST"

    def test_preserves_is_round_trip(self):
        slots = ExtractedSlots(is_round_trip=True)
        result = _build_extracted_dict(slots)
        assert result["is_round_trip"] is True

    def test_preserves_return_date(self):
        slots = ExtractedSlots(return_date="2026-07-30")
        result = _build_extracted_dict(slots)
        assert result["return_date"] == "2026-07-30"

    def test_both_hotel_and_flight_fields(self):
        slots = ExtractedSlots(
            destination_city="Cairo",
            duration_days="3",
            origin_city="London",
            selected_hotel_name="Mena House",
            selected_flight_number="2",
            cabin_class="BUSINESS",
            is_round_trip=False,
        )
        result = _build_extracted_dict(slots)
        assert result["destination_city"] == "Cairo"
        assert result["duration_days"] == 3
        assert result["origin_city"] == "London"
        assert result["selected_hotel_name"] == "Mena House"
        assert result["selected_flight_number"] == 2
        assert result["cabin_class"] == "BUSINESS"
        assert result["is_round_trip"] is False

    def test_coerces_selected_flight_number_as_string(self):
        slots = ExtractedSlots(selected_flight_number="2")
        result = _build_extracted_dict(slots)
        assert result["selected_flight_number"] == 2
        assert isinstance(result["selected_flight_number"], int)


# ═══════════════════════════════════════════════════════════════════════════════
# _build_itinerary_summary tests
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_DAYS = [
    {"day_number": 1, "theme": "History", "stops": [
        {"name": "Egyptian Museum"},
        {"name": "Pyramids"},
    ]},
    {"day_number": 2, "theme": "Markets", "stops": [
        {"name": "Khan El Khalili"},
    ]},
]


def _make_state(**overrides) -> ConversationState:
    """Helper to create a ConversationState with sensible defaults for testing."""
    state = ConversationState(user_id="test_user")
    for k, v in overrides.items():
        if k == "phase":
            state.phase = ConversationPhase(v) if isinstance(v, str) else v
        elif k == "slots":
            if isinstance(v, dict):
                for sk, sv in v.items():
                    setattr(state.slots, sk, sv)
            else:
                state.slots = v
        elif k == "itinerary":
            state.itinerary = v
        elif k == "history":
            state.history = v
        else:
            setattr(state, k, v)
    return state


def _make_itinerary(days=None, hotels=None) -> dict:
    """Build a mock itinerary dict."""
    itinerary = {
        "destination": "Cairo",
        "duration_days": 2,
        "days": days if days is not None else [dict(d) for d in _DEFAULT_DAYS],
    }
    if hotels:
        itinerary["accommodation_suggestions"] = hotels
    return itinerary


class TestBuildItinerarySummary:
    def test_no_itinerary_returns_empty(self):
        state = _make_state(itinerary=None)
        result = _build_itinerary_summary(state)
        assert result == ""

    def test_includes_day_count(self):
        itinerary = _make_itinerary()
        state = _make_state(itinerary=itinerary)
        result = _build_itinerary_summary(state)
        assert "2 days planned" in result
        assert "Day 1: History" in result
        assert "Day 2: Markets" in result

    def test_includes_stop_names(self):
        itinerary = _make_itinerary()
        state = _make_state(itinerary=itinerary)
        result = _build_itinerary_summary(state)
        assert "Egyptian Museum" in result
        assert "Pyramids" in result
        assert "Khan El Khalili" in result

    def test_single_day_itinerary(self):
        itinerary = _make_itinerary(days=[
            {"day_number": 1, "theme": "Culture", "stops": [
                {"name": "Museum"},
            ]},
        ])
        state = _make_state(itinerary=itinerary)
        result = _build_itinerary_summary(state)
        assert "1 days planned" in result
        assert "Day 1: Culture" in result

    def test_limits_stops_to_4_in_summary(self):
        stops = [{"name": f"Stop {i}"} for i in range(6)]
        itinerary = _make_itinerary(days=[
            {"day_number": 1, "theme": "Busy Day", "stops": stops},
        ])
        state = _make_state(itinerary=itinerary)
        result = _build_itinerary_summary(state)
        # Should show at most 4 stop names
        for i in range(4):
            assert f"Stop {i}" in result
        # Stop 4 might or might not appear depending on truncation
        assert "Stop 0" in result  # first one always included

    def test_shows_hotels_during_hotel_selection_phase(self):
        hotels = [
            {"name": "Mena House", "rating": 4.6, "accommodation_type": "luxury"},
            {"name": "Marriott", "rating": 4.3, "accommodation_type": "hotel"},
        ]
        itinerary = _make_itinerary(hotels=hotels)
        state = _make_state(itinerary=itinerary, phase="hotel_selection")
        result = _build_itinerary_summary(state)
        assert "Available Hotels" in result
        assert "1. Mena House" in result
        assert "2. Marriott" in result
        assert "rating=4.6" in result
        assert "looks good" in result

    def test_shows_hotel_names_outside_hotel_selection(self):
        hotels = [
            {"name": "Mena House", "rating": 4.6, "accommodation_type": "luxury"},
        ]
        itinerary = _make_itinerary(hotels=hotels)
        state = _make_state(itinerary=itinerary, phase="itinerary_review")
        result = _build_itinerary_summary(state)
        assert "Hotels:" in result
        assert "Mena House" in result
        assert "Available Hotels" not in result

    def test_no_flight_results_shows_origin_prompt(self):
        itinerary = _make_itinerary()
        state = _make_state(
            itinerary=itinerary,
            phase="flight_selection",
            slots={"flight_search_results": None, "selected_flight_offer": None, "origin_city": None},
        )
        result = _build_itinerary_summary(state)
        assert "Ask the user where they will be flying FROM" in result

    def test_no_flights_searched_shows_search_prompt(self):
        itinerary = _make_itinerary()
        state = _make_state(
            itinerary=itinerary,
            phase="flight_selection",
            slots={"flight_search_results": None, "selected_flight_offer": None, "origin_city": "Cairo"},
        )
        result = _build_itinerary_summary(state)
        assert "ask the user if they want to search for flights" in result.lower()

    def test_flight_selected_shows_proceed_prompt(self):
        itinerary = _make_itinerary()
        state = _make_state(
            itinerary=itinerary,
            phase="flight_selection",
            slots={
                "flight_search_results": [{"airline_name": "EgyptAir"}],
                "selected_flight_offer": {"airline_name": "EgyptAir"},
                "origin_city": "Cairo",
            },
        )
        result = _build_itinerary_summary(state)
        assert "A flight has been selected" in result
        assert "proceed" in result

    def test_shows_flight_search_results_with_numbers(self):
        flights = [
            {"airline_name": "EgyptAir", "flight_number": "MS123",
             "departure_at_formatted": "09:00", "arrival_at_formatted": "11:00",
             "total_price": 250, "currency": "USD",
             "origin_iata": "CAI", "destination_iata": "LUX"},
            {"airline_code": "SWISS", "flight_number": "LX456",
             "departure_at_formatted": "14:00", "arrival_at_formatted": "16:00",
             "total_price": 350, "currency": "EUR",
             "origin_iata": "CAI", "destination_iata": "LUX"},
        ]
        itinerary = _make_itinerary()
        state = _make_state(
            itinerary=itinerary,
            phase="flight_selection",
            slots={
                "flight_search_results": flights,
                "selected_flight_offer": None,
                "origin_city": "Cairo",
            },
        )
        result = _build_itinerary_summary(state)
        assert "Available Flights" in result
        assert "1. EgyptAir MS123" in result
        assert "2. SWISS LX456" in result
        assert "CAI→LUX" in result
        assert "250 USD" in result
        assert "pick a flight by number" in result

    def test_flight_without_airline_name_uses_code(self):
        flights = [{"airline_code": "MS", "flight_number": "777"}]
        itinerary = _make_itinerary()
        state = _make_state(
            itinerary=itinerary,
            phase="flight_selection",
            slots={
                "flight_search_results": flights,
                "selected_flight_offer": None,
                "origin_city": "Cairo",
            },
        )
        result = _build_itinerary_summary(state)
        assert "MS 777" in result

    def test_no_hotels_in_itinerary(self):
        itinerary = _make_itinerary()
        state = _make_state(itinerary=itinerary, phase="itinerary_review")
        result = _build_itinerary_summary(state)
        assert "Hotels:" not in result

    def test_empty_days(self):
        itinerary = _make_itinerary(days=[])
        state = _make_state(itinerary=itinerary, phase="itinerary_review")
        result = _build_itinerary_summary(state)
        assert "0 days planned" in result

    def test_accommodation_suggestions_not_present(self):
        itinerary = _make_itinerary(days=[
            {"day_number": 1, "theme": "History", "stops": [
                {"name": "Museum"},
            ]},
        ])
        state = _make_state(itinerary=itinerary, phase="itinerary_review")
        result = _build_itinerary_summary(state)
        assert "Hotels:" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# Fake LLM output helper for interpret_message tests
# ═══════════════════════════════════════════════════════════════════════════════

class FakeInterpreterOutput:
    """Create a mock LLM response for interpret_message tests.

    Uses a dict-backed object instead of MagicMock to avoid
    MagicMock's truthy default values for boolean/int fields.
    """

    @staticmethod
    def make(action: str, response: str = "OK", **extracted) -> MagicMock:
        mock = MagicMock()
        mock.action = action
        mock.response = response

        # Create a dict-backed object for extracted fields
        # to avoid MagicMock defaults (e.g. is_round_trip returning
        # a MagicMock that is != None)
        class _ExtractedProxy:
            def __init__(self, fields: dict):
                self._fields = {
                    "destination_city": None, "destination_country": None,
                    "duration_days": None, "travel_dates": None,
                    "group_size": None, "traveler_group_type": None,
                    "special_requests": None, "budget_level": None,
                    "travel_style": None, "pace": None,
                    "interests": None, "food_preferences": None,
                    "accommodation_preferences": None,
                    "selected_hotel_name": None, "selected_hotel_number": None,
                    "origin_city": None, "selected_flight_number": None,
                    "cabin_class": None, "is_round_trip": None, "return_date": None,
                    "preferred_hotel_star_class": None,
                }
                self._fields.update(fields)
                for k, v in self._fields.items():
                    setattr(self, k, v)

            def model_dump(self):
                return {k: v for k, v in self._fields.items() if v is not None}

        mock.extracted = _ExtractedProxy(extracted)
        return mock


# ═══════════════════════════════════════════════════════════════════════════════
# interpret_message tests — Safety Overrides & Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpretMessageSafetyOverrides:
    """Test the deterministic safety override logic (no real LLM calls)."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_hotel_selection_override_activates(self, mock_llm):
        """When in HOTEL_SELECTION phase and user mentions a hotel, override to select_hotel."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "I see you want a hotel")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}])

        result = await interpret_message(state, "I want the Mena House")
        assert result.action == "select_hotel", (
            f"Expected select_hotel, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_hotel_selection_override_with_number(self, mock_llm):
        """When in HOTEL_SELECTION phase and user says 'number 2', override to select_hotel."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "You want number 2")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}, {"name": "Marriott"}])

        result = await interpret_message(state, "I'll take number 2")
        assert result.action == "select_hotel"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_hotel_selection_looks_good_triggers_override(self, mock_llm):
        """'looks good' IS in hotel_keywords, so the safety override fires."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "approve_itinerary", "Looks good!"
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}])

        result = await interpret_message(state, "Looks good!")
        assert result.action == "select_hotel"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_hotel_selection_approve_not_overridden(self, mock_llm):
        """In HOTEL_SELECTION, 'Approve' alone does NOT match hotel_keywords."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "approve_itinerary", "Looks good!"
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}])

        result = await interpret_message(state, "Approve")
        assert result.action == "approve_itinerary", (
            f"'Approve' should NOT trigger hotel override, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_hotel_selection_no_override_for_unrelated_questions(self, mock_llm):
        """If the LLM returns a non-select_hotel action but no hotel keywords, don't override."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "answer_question", "What would you like to do?"
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}])

        result = await interpret_message(state, "What else can I do in Cairo?")
        assert result.action == "answer_question"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_search_override(self, mock_llm):
        """When in FLIGHT_SELECTION and user mentions flights, override to search_flights."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "Tell me more")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Show me flights from Cairo")
        assert result.action == "search_flights", (
            f"Expected search_flights override, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_select_override_by_number(self, mock_llm):
        """When in FLIGHT_SELECTION and user picks a flight by number, override to select_flight."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I'll take the first one")
        assert result.action == "select_flight", (
            f"Expected select_flight override, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_select_override_2nd(self, mock_llm):
        """Picking the second option overrides to select_flight."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I want the second option")
        assert result.action == "select_flight"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_approve_not_overridden(self, mock_llm):
        """When in FLIGHT_SELECTION, approve should stay as-is."""
        mock_llm.return_value = FakeInterpreterOutput.make("approve_itinerary", "Looks good!")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I don't need flights, proceed")
        assert result.action == "approve_itinerary"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_travel_dates_override_to_search(self, mock_llm):
        """When flight_selection and user provides travel_dates, override to search_flights."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK", travel_dates="July 28")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I want to fly on July 28")
        assert result.action == "search_flights", (
            f"Travel dates should trigger search_flights override, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_return_date_override_to_search(self, mock_llm):
        """When flight_selection and user provides return_date, override to search_flights."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK", return_date="August 1")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I want a round trip returning August 1")
        assert result.action == "search_flights"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_flight_selection_is_round_trip_override(self, mock_llm):
        """When flight_selection and user sets is_round_trip, override to search_flights."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK", is_round_trip=True)

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I want a round trip")
        assert result.action == "search_flights"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_itinerary_review_modify_override(self, mock_llm):
        """When in ITINERARY_REVIEW and user asks to add/remove, override to modify_itinerary."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Add the Grand Egyptian Museum to day 1")
        assert result.action == "modify_itinerary", (
            f"Expected modify_itinerary override, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_itinerary_review_remove_override(self, mock_llm):
        """Remove/delete keywords trigger modify override in itinerary_review."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Remove the Pyramids from day 1")
        assert result.action == "modify_itinerary"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_itinerary_review_swap_override(self, mock_llm):
        """Swap/switch keywords trigger modify override in itinerary_review."""
        mock_llm.return_value = FakeInterpreterOutput.make("answer_question", "OK")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Swap the Museum with the Pyramids")
        assert result.action == "modify_itinerary"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_itinerary_review_approve_not_overridden(self, mock_llm):
        """When in ITINERARY_REVIEW and user approves, don't override to modify."""
        mock_llm.return_value = FakeInterpreterOutput.make("approve_itinerary", "Looks great!")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Looks great, approve!")
        assert result.action == "approve_itinerary"


class TestInterpretMessageLLMFailure:
    """Test the LLM failure fallback path."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_llm_failure_returns_answer_question(self, mock_llm):
        """When the LLM call fails entirely, default to answer_question."""
        mock_llm.side_effect = Exception("LLM API error")

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "Hello")

        assert result.action == "answer_question"
        assert result.extracted == {}
        assert "rephrase" in result.response.lower()

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_llm_failure_logs_error(self, mock_llm, caplog):
        """When the LLM call fails, an error should be logged."""
        import logging
        caplog.set_level(logging.ERROR)
        mock_llm.side_effect = Exception("LLM API error")

        state = ConversationState(user_id="test")
        await interpret_message(state, "Hello")

        assert any("LLM" in rec.message for rec in caplog.records), (
            "Expected error log about LLM failure"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_llm_returns_none_defaults_to_answer_question(self, mock_llm):
        """When invoke_with_fallback returns None, should handle gracefully."""
        mock_llm.return_value = None

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "Hello")

        assert result.action == "answer_question"
        assert "rephrase" in result.response.lower()

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_llm_failure_with_hotel_phase(self, mock_llm):
        """Even in HOTEL_SELECTION, LLM failure should return safe fallback."""
        mock_llm.side_effect = Exception("LLM API error")

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}])

        result = await interpret_message(state, "What should I do today?")

        assert result.action == "answer_question"
        assert "rephrase" in result.response.lower()


class TestInterpretMessagePlanTripGuard:
    """Test the plan_trip safety guard during specialized phases."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_no_plan_trip_in_specialized_phases(self, mock_llm):
        """plan_trip from LLM should be preserved during specialized phases (not forced)."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "plan_trip",
            "Will do!",
            destination_city="Cairo",
            duration_days="3",
            budget_level="moderate",
            travel_style="cultural",
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "What can you tell me about this trip?")
        # During FLIGHT_SELECTION, the plan_trip guard does NOT force plan_trip.
        # The LLM returned plan_trip, which is preserved because the message
        # doesn't trigger any flight safety override (no flight/number keywords).
        assert result.action == "plan_trip"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_plan_trip_during_greeting_with_complete_info(self, mock_llm):
        """plan_trip should be forced when all info is provided during non-specialized phase."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "I'll plan that for you!",
            destination_city="Cairo",
            duration_days="3",
            interests=["history"],
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.GREETING

        result = await interpret_message(
            state,
            "Plan me a 3-day trip to Cairo interested in history",
        )
        assert result.action == "plan_trip", (
            f"Expected plan_trip with complete info, got {result.action}"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_plan_trip_not_forced_without_duration(self, mock_llm):
        """plan_trip should NOT be forced when duration is missing."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "What city?",
            destination_city="Cairo",
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.GREETING

        result = await interpret_message(state, "I want to visit Cairo")
        assert result.action != "plan_trip", (
            "Should not force plan_trip when duration is missing"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_plan_trip_not_forced_with_approve_or_modify(self, mock_llm):
        """plan_trip should NOT override approve_itinerary or modify_itinerary."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "approve_itinerary",
            "Looks good!",
            destination_city="Cairo",
            duration_days="3",
            interests=["history"],
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Looks good, approve!")
        assert result.action == "approve_itinerary", (
            "plan_trip should not override approve"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_plan_trip_not_forced_with_empty_interests(self, mock_llm):
        """plan_trip should NOT be forced when LLM returns empty interests list (default)."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "What are you interested in?",
            destination_city="Cairo",
            duration_days="3",
            interests=[],  # Empty list — LLM default
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.GREETING

        result = await interpret_message(state, "3 days in Cairo")
        assert result.action != "plan_trip", (
            "Should not force plan_trip when interests is empty list"
        )

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_plan_trip_forced_when_state_has_interests(self, mock_llm):
        """plan_trip should be forced when state already has interests from a previous turn."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "Generating!",
            destination_city="Cairo",
            duration_days="3",
        )

        state = ConversationState(user_id="test")
        state.slots.interests = ["history"]  # Already set in state

        result = await interpret_message(state, "3 days in Cairo")
        assert result.action == "plan_trip", (
            "Should force plan_trip when state has interests"
        )


class TestInterpretMessageExtractedData:
    """Test that extracted data flows correctly through interpret_message."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_extracted_data_passed_through(self, mock_llm):
        """Extracted slots from the LLM should appear in the result."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "What city?",
            destination_city="Cairo",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "I want to visit Cairo")

        assert result.extracted.get("destination_city") == "Cairo"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_extracted_duration_days_coerced(self, mock_llm):
        """Duration days string should be coerced to int."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "3 days, got it!",
            duration_days="3",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "3 days")

        assert result.extracted.get("duration_days") == 3
        assert isinstance(result.extracted["duration_days"], int)

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_response_text_preserved(self, mock_llm):
        """The LLM response text should be passed through to the result."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "Paris is a wonderful choice! How many days are you planning to stay?",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "I want to visit Paris")

        assert "Paris is a wonderful choice" in result.response

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_extracted_interests_list(self, mock_llm):
        """Interest lists from LLM should be passed through."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "Great interests!",
            interests=["history", "food", "art"],
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "I love history, food, and art")

        assert result.extracted.get("interests") == ["history", "food", "art"]


class TestInterpretMessageGreetingPhase:
    """Test interpret_message behavior specifically during GREETING phase."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_greeting_without_slots_no_plan_trip(self, mock_llm):
        """During GREETING with no info, should not force plan_trip."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "Welcome! Where would you like to travel?",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "Hello!")

        assert result.action != "plan_trip"
        assert result.action == "ask_clarification"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_greeting_city_only_no_plan_trip(self, mock_llm):
        """During GREETING with just a city, no plan_trip without duration + interests."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "Great choice! How many days?",
            destination_city="Cairo",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "I want to go to Cairo")

        assert result.action != "plan_trip"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_greeting_city_and_duration_no_interests_no_plan(self, mock_llm):
        """With city+duration but no interests (empty), plan_trip should NOT be forced."""
        mock_llm.return_value = FakeInterpreterOutput.make(
            "ask_clarification",
            "What are you interested in?",
            destination_city="Cairo",
            duration_days="3",
            interests=[],
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "3 days in Cairo")

        assert result.action != "plan_trip", (
            "Should not force plan_trip when interests is empty list"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Full flow: interpret_message with real InterpreterOutput return values
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpretMessageFullFlow:
    """Test the full flow of interpret_message with InterpreterOutput returns."""

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_full_flow_plan_trip(self, mock_llm):
        """LLM returns a valid InterpreterOutput with plan_trip action."""
        mock_llm.return_value = InterpreterOutput(
            action="plan_trip",
            extracted=ExtractedSlots(
                destination_city="Cairo",
                duration_days="3",
                interests=["history"],
            ),
            response="Generating your itinerary for Cairo!",
        )

        state = ConversationState(user_id="test")
        result = await interpret_message(state, "Plan me a 3-day trip to Cairo interested in history")

        assert result.action == "plan_trip"
        assert result.extracted["destination_city"] == "Cairo"
        assert result.extracted["duration_days"] == 3
        assert result.extracted["interests"] == ["history"]
        assert "Generating" in result.response

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_full_flow_modify_itinerary(self, mock_llm):
        """LLM returns modify_itinerary action."""
        mock_llm.return_value = InterpreterOutput(
            action="modify_itinerary",
            extracted=ExtractedSlots(),
            response="Let me update that!",
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.ITINERARY_REVIEW
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "Make it more entertaining")
        assert result.action == "modify_itinerary"

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_full_flow_select_hotel(self, mock_llm):
        """LLM returns select_hotel during hotel selection."""
        mock_llm.return_value = InterpreterOutput(
            action="select_hotel",
            extracted=ExtractedSlots(
                selected_hotel_name="Mena House",
                selected_hotel_number=1,
            ),
            response="Great choice!",
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.HOTEL_SELECTION
        state.itinerary = _make_itinerary(hotels=[{"name": "Mena House"}, {"name": "Marriott"}])

        result = await interpret_message(state, "I'll take the Mena House")
        assert result.action == "select_hotel"
        assert result.extracted["selected_hotel_name"] == "Mena House"
        assert result.extracted["selected_hotel_number"] == 1

    @pytest.mark.asyncio
    @patch("ai_engine.conversation.message_interpreter.invoke_with_fallback")
    async def test_full_flow_search_flights(self, mock_llm):
        """LLM returns search_flights action."""
        mock_llm.return_value = InterpreterOutput(
            action="search_flights",
            extracted=ExtractedSlots(
                origin_city="Cairo",
                is_round_trip=True,
            ),
            response="Let me find flights from Cairo!",
        )

        state = ConversationState(user_id="test")
        state.phase = ConversationPhase.FLIGHT_SELECTION
        state.itinerary = _make_itinerary()

        result = await interpret_message(state, "I want to fly from Cairo")
        assert result.action == "search_flights"
        assert result.extracted["origin_city"] == "Cairo"
        assert result.extracted["is_round_trip"] is True
