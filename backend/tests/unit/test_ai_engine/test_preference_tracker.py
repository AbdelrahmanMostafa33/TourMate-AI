"""
Unit tests for PreferenceTracker service.

Tests the ``PreferenceTracker`` class in two groups:

1. ``merge()`` — merging new TripProfile data into preference confidence counts
2. ``total_trips()`` — deriving trip count from the counts dict

Run:
    pytest tests/unit/test_ai_engine/test_preference_tracker.py -v
"""

from ai_engine.profiling.preference_tracker import PreferenceTracker, ALL_CATEGORIES


# ═════════════════════════════════════════════════════════════════════════════
# Test: merge()
# ═════════════════════════════════════════════════════════════════════════════


class TestMerge:
    """Tests for ``PreferenceTracker.merge()``."""

    # ── Basic first-time merge ──────────────────────────────────────────

    def test_first_trip_from_empty_counts(self):
        """First trip with empty old_counts → counts reflect exactly one trip."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "budget_level": "luxury",
                "travel_style": "adventure",
                "pace": "packed",
                "interests": ["hiking", "climbing"],
                "food_preferences": ["protein bars"],
                "accommodation_preferences": ["camping"],
            },
        )

        assert merged["budget_level"]["luxury"] == 1
        assert merged["travel_style"]["adventure"] == 1
        assert merged["pace"]["packed"] == 1
        assert merged["interests"]["hiking"] == 1
        assert merged["interests"]["climbing"] == 1
        assert merged["food_preferences"]["protein bars"] == 1
        assert merged["accommodation_preferences"]["camping"] == 1

    def test_first_trip_from_none(self):
        """Old_counts is None → treated as empty, counts built from scratch."""
        merged = PreferenceTracker.merge(
            old_counts=None,
            profile_data={
                "budget_level": "moderate",
                "travel_style": "cultural",
                "pace": "moderate",
                "interests": ["history"],
                "food_preferences": ["local cuisine"],
                "accommodation_preferences": ["boutique hotel"],
            },
        )

        assert merged["budget_level"]["moderate"] == 1
        assert merged["interests"]["history"] == 1

    # ── Incremental merge (accumulation) ────────────────────────────────

    def test_second_trip_same_values_increments_counts(self):
        """Same values on second trip → counts increase."""
        old = {
            "budget_level": {"moderate": 2},
            "travel_style": {"cultural": 2},
            "pace": {"moderate": 2},
            "interests": {"history": 2, "art": 1},
            "food_preferences": {"local cuisine": 2},
            "accommodation_preferences": {"boutique hotel": 2},
        }
        merged = PreferenceTracker.merge(
            old_counts=old,
            profile_data={
                "budget_level": "moderate",
                "travel_style": "cultural",
                "pace": "moderate",
                "interests": ["history", "food"],
                "food_preferences": ["local cuisine"],
                "accommodation_preferences": ["boutique hotel"],
            },
        )

        assert merged["budget_level"]["moderate"] == 3
        assert merged["interests"]["history"] == 3  # reinforced
        assert merged["interests"]["food"] == 1      # new interest
        assert merged["travel_style"]["cultural"] == 3

    def test_new_category_values_appear_without_losing_old(self):
        """New values for a category appear alongside existing ones."""
        old = {
            "travel_style": {"cultural": 3},
        }
        merged = PreferenceTracker.merge(
            old_counts=old,
            profile_data={
                "travel_style": "adventure",
            },
        )

        assert merged["travel_style"]["cultural"] == 3  # preserved
        assert merged["travel_style"]["adventure"] == 1  # new

    # ── Old counts preserved for absent categories ──────────────────────

    def test_old_counts_preserved_when_category_absent_in_new_trip(self):
        """If a category is absent from new trip data, old counts survive."""
        old = {
            "budget_level": {"luxury": 5},
            "travel_style": {"relaxation": 3},
            "interests": {"spa": 4},
        }
        merged = PreferenceTracker.merge(
            old_counts=old,
            profile_data={
                "budget_level": "luxury",  # only this category present
            },
        )

        assert merged["budget_level"]["luxury"] == 6
        # These were not in profile_data but must survive
        assert merged["travel_style"]["relaxation"] == 3
        assert merged["interests"]["spa"] == 4

    # ── Mutation safety ─────────────────────────────────────────────────

    def test_original_old_counts_not_mutated(self):
        """The original dict passed as old_counts is not modified in place."""
        original = {
            "budget_level": {"luxury": 2},
        }
        original_copy = dict(original)  # shallow reference for comparison

        PreferenceTracker.merge(
            old_counts=original,
            profile_data={
                "budget_level": "luxury",
                "travel_style": "cultural",
            },
        )

        # The original should be unchanged
        assert original == original_copy

    def test_nested_old_counts_deep_copied(self):
        """Nested dicts inside old_counts are not mutated by merge."""
        old = {
            "interests": {"history": 1, "art": 1},
        }
        old_history_ref = old["interests"]["history"]

        PreferenceTracker.merge(
            old_counts=old,
            profile_data={
                "interests": ["history", "food", "art"],
            },
        )

        # Old reference should still exist (deep copy was made)
        assert old["interests"]["history"] == old_history_ref

    def test_subsequent_merge_does_not_leak_into_previous_result(self):
        """Each merge call produces an independent result dict."""
        profile_1 = {"budget_level": "luxury"}
        profile_2 = {"budget_level": "budget"}

        r1 = PreferenceTracker.merge(old_counts={}, profile_data=profile_1)
        r2 = PreferenceTracker.merge(old_counts=r1, profile_data=profile_2)

        assert r1["budget_level"]["luxury"] == 1
        assert r2["budget_level"]["luxury"] == 1
        assert r2["budget_level"]["budget"] == 1

    # ── Empty / missing data ────────────────────────────────────────────

    def test_empty_profile_data_returns_empty_structure(self):
        """When profile_data has no recognized keys, returns old counts unchanged."""
        old = {"budget_level": {"moderate": 3}}
        merged = PreferenceTracker.merge(
            old_counts=old,
            profile_data={},
        )
        assert merged == old

    def test_none_values_in_profile_data_are_ignored(self):
        """None values for scalar categories should not create entries."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "budget_level": None,
                "travel_style": None,
                "pace": None,
            },
        )
        # No entries should be created for None values
        assert "budget_level" not in merged
        assert "travel_style" not in merged
        assert "pace" not in merged

    def test_empty_lists_in_profile_data_are_ignored(self):
        """Empty lists for list categories should not create entries."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "interests": [],
                "food_preferences": [],
                "accommodation_preferences": [],
            },
        )
        assert "interests" not in merged
        assert "food_preferences" not in merged
        assert "accommodation_preferences" not in merged

    def test_unknown_categories_are_ignored(self):
        """Categories not in SCALAR_CATEGORIES or LIST_CATEGORIES are ignored."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "budget_level": "moderate",
                "favorite_color": "blue",
                "pet_preference": "cat",
            },
        )
        assert merged["budget_level"]["moderate"] == 1
        assert "favorite_color" not in merged
        assert "pet_preference" not in merged

    # ── List category edge cases ────────────────────────────────────────

    def test_list_with_whitespace_items_handled(self):
        """Items with surrounding whitespace are stripped before counting."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "interests": ["  history  ", "art", "  food  "],
            },
        )
        assert merged["interests"]["history"] == 1
        assert merged["interests"]["art"] == 1
        assert merged["interests"]["food"] == 1

    def test_empty_string_in_list_skipped(self):
        """Empty strings in list items are not counted."""
        merged = PreferenceTracker.merge(
            old_counts={},
            profile_data={
                "interests": ["history", "", "art", "  "],
            },
        )
        assert merged["interests"]["history"] == 1
        assert merged["interests"]["art"] == 1
        assert "" not in merged["interests"]

    # ── ALL_CATEGORIES export ───────────────────────────────────────────

    def test_all_categories_contains_all_expected_categories(self):
        """ALL_CATEGORIES lists every category the tracker handles."""
        expected = {
            "budget_level", "travel_style", "pace",
            "interests", "food_preferences", "accommodation_preferences",
        }
        assert set(ALL_CATEGORIES) == expected
        assert len(ALL_CATEGORIES) == 6


# ═════════════════════════════════════════════════════════════════════════════
# Test: total_trips()
# ═════════════════════════════════════════════════════════════════════════════


class TestTotalTrips:
    """Tests for ``PreferenceTracker.total_trips()``."""

    def test_empty_counts_returns_zero(self):
        assert PreferenceTracker.total_trips({}) == 0

    def test_none_counts_returns_zero(self):
        assert PreferenceTracker.total_trips(None) == 0

    def test_single_trip_returns_one(self):
        counts = {"budget_level": {"moderate": 1}}
        assert PreferenceTracker.total_trips(counts) == 1

    def test_three_trips_reflected(self):
        counts = {
            "budget_level": {"luxury": 3},
            "travel_style": {"cultural": 2, "adventure": 1},
            "pace": {"moderate": 3},
        }
        assert PreferenceTracker.total_trips(counts) == 3

    def test_uses_highest_count_across_categories(self):
        """The highest count across all categories represents trip count."""
        counts = {
            "budget_level": {"luxury": 2},
            "interests": {"history": 5, "art": 3},  # history has highest count
        }
        assert PreferenceTracker.total_trips(counts) == 5

    def test_mixed_values_ignores_non_dict_entries(self):
        """Non-dict values in counts are ignored when computing max."""
        counts = {
            "budget_level": {"moderate": 3},
            "some_metadata": "not_a_dict",
        }
        assert PreferenceTracker.total_trips(counts) == 3

    def test_float_counts_are_handled(self):
        """Float values are cast to int."""
        counts = {
            "budget_level": {"moderate": 3.0},
        }
        result = PreferenceTracker.total_trips(counts)
        assert isinstance(result, int)
        assert result == 3

    def test_empty_category_values_skipped(self):
        """Categories with empty dict values don't affect the count."""
        counts = {
            "budget_level": {"luxury": 2},
            "interests": {},  # empty
        }
        assert PreferenceTracker.total_trips(counts) == 2
