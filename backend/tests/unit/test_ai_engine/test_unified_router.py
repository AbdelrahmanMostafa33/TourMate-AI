# tests/unit/test_ai_engine/test_unified_router.py
"""Tests for the unified router module."""

import pytest
from ai_engine.chat.unified_router import (
    _coerce_int,
    _build_extracted_dict,
    _normalize_action,
    ExtractedSlots,
    RouterOutput,
    RouterResult,
)


# -- _coerce_int tests --

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


# -- _normalize_action tests --

class TestNormalizeAction:
    def test_direct_aliases(self):
        assert _normalize_action("plan_trip") == "plan_trip"
        assert _normalize_action("ask_clarification") == "ask_clarification"
        assert _normalize_action("answer_question") == "answer_question"
        assert _normalize_action("approve_itinerary") == "approve_itinerary"
        assert _normalize_action("modify_itinerary") == "modify_itinerary"

    def test_aliases(self):
        assert _normalize_action("general_chat") == "answer_question"
        assert _normalize_action("clarify") == "ask_clarification"
        assert _normalize_action("confirm") == "approve_itinerary"
        assert _normalize_action("change") == "modify_itinerary"

    def test_unknown_defaults_to_answer_question(self):
        assert _normalize_action("something_unknown") == "answer_question"

    def test_case_insensitive(self):
        assert _normalize_action("Plan_Trip") == "plan_trip"
        assert _normalize_action("GENERAL_CHAT") == "answer_question"


# -- ExtractedSlots Pydantic model tests --

class TestExtractedSlots:
    def test_all_none_by_default(self):
        slots = ExtractedSlots()
        assert slots.destination_city is None
        assert slots.duration_days is None
        assert slots.budget_level is None

    def test_accepts_string_for_duration(self):
        slots = ExtractedSlots(duration_days="3")
        assert slots.duration_days == "3"

    def test_model_dump_excludes_none(self):
        slots = ExtractedSlots(destination_city="Cairo")
        d = slots.model_dump()
        assert d["destination_city"] == "Cairo"
        assert d["duration_days"] is None


# -- _build_extracted_dict tests --

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

    def test_already_string_coerced(self):
        slots = ExtractedSlots(duration_days="7")
        result = _build_extracted_dict(slots)
        assert result["duration_days"] == 7
        assert isinstance(result["duration_days"], int)
