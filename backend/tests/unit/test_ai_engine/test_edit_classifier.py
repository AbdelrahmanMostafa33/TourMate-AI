"""Unit tests for edit classifier routing helpers."""

from ai_engine.agents.edit_classifier_agent import (
    is_preference_edit,
    is_regenerate_edit,
    is_surgical_edit,
)


class TestEditClassifierRouting:
    def test_surgical_types(self):
        for edit_type in ("REMOVE", "ADD_PLACE", "REPLACE_PLACE", "REORDER"):
            assert is_surgical_edit({"edit_type": edit_type}) is True

    def test_preference_types(self):
        assert is_preference_edit({"edit_type": "CHANGE_BUDGET"}) is True
        assert is_preference_edit({"edit_type": "CHANGE_PACE"}) is True

    def test_regenerate(self):
        assert is_regenerate_edit({"edit_type": "REGENERATE"}) is True
        assert is_regenerate_edit({"edit_type": "ADD_PLACE"}) is False
