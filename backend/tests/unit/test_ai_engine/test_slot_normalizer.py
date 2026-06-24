# tests/unit/test_ai_engine/test_slot_normalizer.py

"""
Unit tests for ai_engine.tools.slot_normalizer.

Tests deterministic normalization of budget, pace, style, food,
accommodation, and interests — the core of the slot-filling reliability
improvement that eliminates LLM dependency for normalization.
"""

import pytest

from ai_engine.tools.slot_normalizer import (
    normalize_budget,
    normalize_pace,
    normalize_style,
    normalize_food,
    normalize_accommodation,
    normalize_interests,
    normalize_extracted_slots,
    map_accommodation_to_type,
)


# ══════════════════════════════════════════════════════════════════════════════
# normalize_budget
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeBudget:
    def test_canonical_passthrough(self):
        assert normalize_budget("budget") == "budget"
        assert normalize_budget("moderate") == "moderate"
        assert normalize_budget("luxury") == "luxury"

    def test_budget_synonyms(self):
        assert normalize_budget("cheap") == "budget"
        assert normalize_budget("low") == "budget"
        assert normalize_budget("economy") == "budget"
        assert normalize_budget("affordable") == "budget"
        assert normalize_budget("inexpensive") == "budget"
        assert normalize_budget("low-budget") == "budget"

    def test_moderate_synonyms(self):
        assert normalize_budget("medium") == "moderate"
        assert normalize_budget("mid-range") == "moderate"
        assert normalize_budget("mid range") == "moderate"
        assert normalize_budget("average") == "moderate"
        assert normalize_budget("standard") == "moderate"
        assert normalize_budget("reasonable") == "moderate"

    def test_luxury_synonyms(self):
        assert normalize_budget("high-end") == "luxury"
        assert normalize_budget("expensive") == "luxury"
        assert normalize_budget("luxurious") == "luxury"
        assert normalize_budget("premium") == "luxury"
        assert normalize_budget("5-star") == "luxury"
        assert normalize_budget("5 star") == "luxury"
        assert normalize_budget("five star") == "luxury"
        assert normalize_budget("upscale") == "luxury"

    def test_substring_match(self):
        """Substring matching catches phrased inputs."""
        assert normalize_budget("I want something mid-range please") == "moderate"
        assert normalize_budget("something cheap") == "budget"
        assert normalize_budget("go all out, expensive!") == "luxury"

    def test_none_and_empty(self):
        assert normalize_budget(None) is None
        assert normalize_budget("") is None
        assert normalize_budget("   ") is None

    def test_non_string_returns_none(self):
        assert normalize_budget(123) is None
        assert normalize_budget(["budget"]) is None

    def test_case_insensitive(self):
        assert normalize_budget("BUDGET") == "budget"
        assert normalize_budget("Luxury") == "luxury"
        assert normalize_budget("MODERATE") == "moderate"

    def test_unknown_returns_none(self):
        assert normalize_budget("rainbow") is None
        assert normalize_budget("banana") is None


# ══════════════════════════════════════════════════════════════════════════════
# normalize_pace
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizePace:
    def test_canonical_passthrough(self):
        assert normalize_pace("relaxed") == "relaxed"
        assert normalize_pace("moderate") == "moderate"
        assert normalize_pace("balanced") == "moderate"
        assert normalize_pace("packed") == "packed"

    def test_relaxed_synonyms(self):
        assert normalize_pace("slow") == "relaxed"
        assert normalize_pace("easy") == "relaxed"
        assert normalize_pace("leisurely") == "relaxed"
        assert normalize_pace("chill") == "relaxed"
        assert normalize_pace("lazy") == "relaxed"

    def test_balanced_synonyms(self):
        assert normalize_pace("mixed") == "moderate"
        assert normalize_pace("flexible") == "moderate"
        assert normalize_pace("varied") == "moderate"
        assert normalize_pace("moderate") == "moderate"

    def test_packed_synonyms(self):
        assert normalize_pace("busy") == "packed"
        assert normalize_pace("intense") == "packed"
        assert normalize_pace("full") == "packed"
        assert normalize_pace("action-packed") == "packed"
        assert normalize_pace("non-stop") == "packed"

    def test_anything_maps_to_moderate(self):
        """The reviewer's key concern: 'anything' should map to moderate, not fail."""
        assert normalize_pace("anything") == "moderate"
        assert normalize_pace("don't care") == "moderate"
        assert normalize_pace("i don't mind") == "moderate"
        assert normalize_pace("no preference") == "moderate"
        assert normalize_pace("surprise me") == "moderate"
        assert normalize_pace("up to you") == "moderate"
        assert normalize_pace("any") == "moderate"

    def test_none_and_empty(self):
        assert normalize_pace(None) is None
        assert normalize_pace("") is None


# ══════════════════════════════════════════════════════════════════════════════
# normalize_style
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeStyle:
    def test_canonical_passthrough(self):
        assert normalize_style("romantic") == "romantic"
        assert normalize_style("adventure") == "adventure"
        assert normalize_style("family") == "family"
        assert normalize_style("solo") == "solo"
        assert normalize_style("cultural") == "cultural"
        assert normalize_style("relaxation") == "relaxation"

    def test_romantic_synonyms(self):
        assert normalize_style("honeymoon") == "romantic"
        assert normalize_style("couple") == "romantic"
        assert normalize_style("anniversary") == "romantic"

    def test_adventure_synonyms(self):
        assert normalize_style("hiking") == "adventure"
        assert normalize_style("trekking") == "adventure"
        assert normalize_style("camping") == "adventure"
        assert normalize_style("backpacking") == "adventure"

    def test_family_synonyms(self):
        assert normalize_style("kids") == "family"
        assert normalize_style("children") == "family"
        assert normalize_style("family trip") == "family"

    def test_solo_synonyms(self):
        assert normalize_style("alone") == "solo"
        assert normalize_style("by myself") == "solo"
        assert normalize_style("solo trip") == "solo"

    def test_cultural_synonyms(self):
        assert normalize_style("history") == "cultural"
        assert normalize_style("museums") == "cultural"
        assert normalize_style("heritage") == "cultural"
        assert normalize_style("architecture") == "cultural"
        assert normalize_style("art") == "cultural"

    def test_relaxation_synonyms(self):
        assert normalize_style("chill") == "relaxation"
        assert normalize_style("beach") == "relaxation"
        assert normalize_style("spa") == "relaxation"
        assert normalize_style("relax") == "relaxation"
        assert normalize_style("peaceful") == "relaxation"
        assert normalize_style("getaway") == "relaxation"

    def test_none_and_empty(self):
        assert normalize_style(None) is None
        assert normalize_style("") is None

    def test_unknown_returns_none(self):
        assert normalize_style("party animal") is None


# ══════════════════════════════════════════════════════════════════════════════
# normalize_food
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeFood:
    def test_canonical_passthrough(self):
        assert normalize_food(["vegetarian"]) == ["vegetarian"]
        assert normalize_food(["vegan"]) == ["vegan"]
        assert normalize_food(["halal"]) == ["halal"]

    def test_synonym_mapping(self):
        result = normalize_food(["local food", "traditional dishes"])
        assert "local cuisine" in result
        assert result.count("local cuisine") == 1  # deduped

    def test_deduplication(self):
        result = normalize_food(["street food", "street eats", "market food"])
        assert result.count("street food") == 1

    def test_mixed_list(self):
        result = normalize_food(["vegetarian", "local food", "seafood"])
        assert "vegetarian" in result
        assert "local cuisine" in result
        assert "seafood" in result

    def test_none_and_empty(self):
        assert normalize_food(None) is None
        assert normalize_food([]) is None

    def test_preserves_order(self):
        result = normalize_food(["seafood", "vegetarian", "halal"])
        assert result == ["seafood", "vegetarian", "halal"]


# ══════════════════════════════════════════════════════════════════════════════
# normalize_accommodation
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeAccommodation:
    def test_canonical_passthrough(self):
        assert normalize_accommodation(["hostel"]) == ["hostel"]
        assert normalize_accommodation(["hotel"]) == ["hotel"]
        assert normalize_accommodation(["resort"]) == ["resort"]

    def test_luxury_keywords(self):
        assert normalize_accommodation(["boutique hotel"]) == ["luxury"]
        assert normalize_accommodation(["five star"]) == ["luxury"]
        assert normalize_accommodation(["high-end"]) == ["luxury"]
        assert normalize_accommodation(["upscale"]) == ["luxury"]
        assert normalize_accommodation(["palace"]) == ["luxury"]

    def test_hostel_keywords(self):
        assert normalize_accommodation(["backpacker"]) == ["hostel"]
        assert normalize_accommodation(["dorm"]) == ["hostel"]
        assert normalize_accommodation(["cheap place"]) == ["hostel"]
        assert normalize_accommodation(["budget stay"]) == ["hostel"]

    def test_resort_keywords(self):
        assert normalize_accommodation(["beach resort"]) == ["resort"]
        assert normalize_accommodation(["all-inclusive"]) == ["resort"]
        assert normalize_accommodation(["spa resort"]) == ["resort"]

    def test_hotel_keywords(self):
        assert normalize_accommodation(["airbnb"]) == ["hotel"]
        assert normalize_accommodation(["apartment"]) == ["hotel"]
        assert normalize_accommodation(["motel"]) == ["hotel"]
        assert normalize_accommodation(["guesthouse"]) == ["hotel"]

    def test_priority_luxury_over_hotel(self):
        """More specific types take priority over generic 'hotel'."""
        result = normalize_accommodation(["boutique hotel", "standard hotel"])
        assert result == ["luxury"]

    def test_priority_resort_over_hotel(self):
        result = normalize_accommodation(["hotel", "resort"])
        assert result == ["resort"]

    def test_single_item_return(self):
        """Always returns a list with ONE item (the dominant preference)."""
        result = normalize_accommodation(["beach resort", "spa resort"])
        assert len(result) == 1
        assert result[0] == "resort"

    def test_none_and_empty(self):
        assert normalize_accommodation(None) is None
        assert normalize_accommodation([]) is None

    def test_substring_in_sentence(self):
        result = normalize_accommodation(["I want a nice resort please"])
        assert result == ["resort"]


# ══════════════════════════════════════════════════════════════════════════════
# Consistency: normalize_accommodation vs map_accommodation_to_type
# ══════════════════════════════════════════════════════════════════════════════

class TestAccommodationConsistency:
    """
    Verify that ``normalize_accommodation`` and ``map_accommodation_to_type``
    produce consistent results for the same inputs.

    ``normalize_accommodation`` returns ``["luxury"]`` (list)
    ``map_accommodation_to_type`` returns ``"luxury"`` (bare string)

    These two functions share the same ``_ACCOMMODATION_KEYWORDS`` list but use
    different matching strategies:
    - ``normalize_accommodation``: ``_contains_word()`` (regex word-boundary)
    - ``map_accommodation_to_type``: ``keyword in pref_lower`` (simple substring)

    For clean single-keyword inputs the results should always agree.
    For complex inputs with non-word characters near a keyword the word-boundary
    and substring strategies may differ — those edge cases are documented below.
    """

    # ── Tests for inputs where both functions should agree ──────────────

    def test_hotel_single_word(self):
        """Canonical type via single word."""
        assert map_accommodation_to_type(["hotel"]) == "hotel"
        assert normalize_accommodation(["hotel"]) == ["hotel"]
        assert map_accommodation_to_type(["hotel"]) == normalize_accommodation(["hotel"])[0]

    def test_luxury_single_word(self):
        assert map_accommodation_to_type(["luxury"]) == "luxury"
        assert normalize_accommodation(["luxury"]) == ["luxury"]
        assert map_accommodation_to_type(["luxury"]) == normalize_accommodation(["luxury"])[0]

    def test_hostel_single_word(self):
        assert map_accommodation_to_type(["hostel"]) == "hostel"
        assert normalize_accommodation(["hostel"]) == ["hostel"]

    def test_resort_single_word(self):
        assert map_accommodation_to_type(["resort"]) == "resort"
        assert normalize_accommodation(["resort"]) == ["resort"]

    def test_boutique_hotel_phrase(self):
        """Multi-word phrase mapping to luxury."""
        assert map_accommodation_to_type(["boutique hotel"]) == "luxury"
        assert normalize_accommodation(["boutique hotel"]) == ["luxury"]

    def test_beach_resort_phrase(self):
        """Multi-word phrase mapping to resort."""
        assert map_accommodation_to_type(["beach resort"]) == "resort"
        assert normalize_accommodation(["beach resort"]) == ["resort"]

    def test_backpacker_hostel(self):
        assert map_accommodation_to_type(["backpacker hostel"]) == "hostel"
        assert normalize_accommodation(["backpacker hostel"]) == ["hostel"]

    def test_airbnb(self):
        assert map_accommodation_to_type(["airbnb"]) == "hotel"
        assert normalize_accommodation(["airbnb"]) == ["hotel"]

    def test_all_inclusive_resort(self):
        assert map_accommodation_to_type(["all-inclusive"]) == "resort"
        assert normalize_accommodation(["all-inclusive"]) == ["resort"]

    def test_five_star_luxury(self):
        assert map_accommodation_to_type(["5-star"]) == "luxury"
        assert normalize_accommodation(["5-star"]) == ["luxury"]

    def test_premium_hotel(self):
        assert map_accommodation_to_type(["premium hotel"]) == "luxury"
        assert normalize_accommodation(["premium hotel"]) == ["luxury"]

    def test_sentence_input(self):
        """Both functions handle full-sentence inputs."""
        assert map_accommodation_to_type(["I want a nice boutique hotel"]) == "luxury"
        assert normalize_accommodation(["I want a nice boutique hotel"]) == ["luxury"]

    def test_guest_house(self):
        assert map_accommodation_to_type(["guesthouse"]) == "hotel"
        assert normalize_accommodation(["guesthouse"]) == ["hotel"]

    def test_bed_and_breakfast(self):
        assert map_accommodation_to_type(["bed and breakfast"]) == "hotel"
        assert normalize_accommodation(["bed and breakfast"]) == ["hotel"]

    def test_multiple_prefs_dominant_wins(self):
        """Both functions return the dominant (highest-priority) type."""
        inputs = [["hotel", "resort"], ["standard hotel", "beach resort"], ["hostel", "villa"]]
        for inp in inputs:
            map_result = map_accommodation_to_type(inp)
            norm_result = normalize_accommodation(inp)
            assert norm_result is not None, f"normalize_accommodation returned None for {inp}"
            assert map_result == norm_result[0], (
                f"Mismatch for {inp}: map={map_result!r}, norm={norm_result!r}"
            )

    def test_no_match_empty_list(self):
        """No matching keywords: map returns empty, norm returns None."""
        assert map_accommodation_to_type(["camping"]) == ""
        assert normalize_accommodation(["camping"]) is None

    def test_empty_input(self):
        assert map_accommodation_to_type([]) == ""
        assert normalize_accommodation([]) is None

    def test_villa_edge_case(self):
        """'villa' maps to luxury in both functions."""
        assert map_accommodation_to_type(["villa"]) == "luxury"
        assert normalize_accommodation(["villa"]) == ["luxury"]

    def test_dormitory_edge_case(self):
        """'dormitory' maps to hostel."""
        assert map_accommodation_to_type(["dormitory"]) == "hostel"
        assert normalize_accommodation(["dormitory"]) == ["hostel"]

    def test_motel(self):
        assert map_accommodation_to_type(["motel"]) == "hotel"
        assert normalize_accommodation(["motel"]) == ["hotel"]

    def test_executive_suite(self):
        """'executive' maps to luxury."""
        assert map_accommodation_to_type(["executive suite"]) == "luxury"
        assert normalize_accommodation(["executive suite"]) == ["luxury"]

    def test_high_end(self):
        assert map_accommodation_to_type(["high end"]) == "luxury"
        assert normalize_accommodation(["high end"]) == ["luxury"]

    def test_standard_hotel(self):
        """'standard' maps to hotel, not 'standard' as a canonical type."""
        assert map_accommodation_to_type(["standard"]) == "hotel"
        assert normalize_accommodation(["standard"]) == ["hotel"]

    # ── Documented divergence cases ────────────────────────────────────

    def test_apartment_hotel(self):
        """Both agree on 'apartment' → hotel."""
        assert map_accommodation_to_type(["apartment"]) == "hotel"
        assert normalize_accommodation(["apartment"]) == ["hotel"]

    def test_waterpark_resort(self):
        """Both map 'water park' → resort."""
        assert map_accommodation_to_type(["water park"]) == "resort"
        assert normalize_accommodation(["water park"]) == ["resort"]

    def test_private_villa(self):
        """'private villa' maps to luxury."""
        assert map_accommodation_to_type(["private villa"]) == "luxury"
        assert normalize_accommodation(["private villa"]) == ["luxury"]

    def test_bnb(self):
        """'bnb' maps to hotel."""
        assert map_accommodation_to_type(["bnb"]) == "hotel"
        assert normalize_accommodation(["bnb"]) == ["hotel"]

    def test_budget_accommodation(self):
        """'budget accommodation' maps to hostel."""
        assert map_accommodation_to_type(["budget accommodation"]) == "hostel"
        assert normalize_accommodation(["budget accommodation"]) == ["hostel"]


# ══════════════════════════════════════════════════════════════════════════════
# normalize_interests
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeInterests:
    def test_canonical_passthrough(self):
        assert normalize_interests(["history"]) == ["history"]
        assert normalize_interests(["food"]) == ["food"]
        assert normalize_interests(["shopping"]) == ["shopping"]

    def test_synonym_mapping(self):
        result = normalize_interests(["museums", "art galleries", "heritage"])
        assert "museums" in result
        assert "art" in result
        assert "history" in result

    def test_deduplication(self):
        result = normalize_interests(["museum", "museums", "museum visits"])
        assert result.count("museums") == 1

    def test_none_and_empty(self):
        assert normalize_interests(None) is None
        assert normalize_interests([]) is None


class TestNormalizeInterestsNoiseFilter:
    """
    Tests for the noise filtering added to normalize_interests().

    Verifies that command verbs (remove, swap, add, etc.) and long
    phrases (> 5 words) are filtered out, while valid interest keywords
    pass through unchanged.
    """

    def test_filters_remove_command(self):
        """'remove abo tarek restaurant from the itinerary' → filtered out."""
        result = normalize_interests([
            "remove abo tarek restaurant from the itinerary",
            "museums",
        ])
        assert result == ["museums"]

    def test_filters_swap_command(self):
        """'swap galaxy cinema with el azhar mosque' → filtered out."""
        result = normalize_interests([
            "swap galaxy cinema with el azhar mosque",
            "history",
        ])
        assert result == ["history"]

    def test_filters_add_command(self):
        """'add a rooftop bar to day 2' → filtered out."""
        result = normalize_interests([
            "add a rooftop bar to day 2",
        ])
        assert result is None or result == []

    def test_filters_delete_command(self):
        """'delete the last stop' → filtered out, other interests preserved."""
        result = normalize_interests([
            "delete the last stop",
            "food",
            "shopping",
        ])
        assert "food" in result
        assert "shopping" in result
        assert "delete" not in str(result)

    def test_filters_all_major_command_verbs(self):
        """Each command verb is filtered: remove, swap, add, delete, change, etc."""
        for verb in ["remove", "swap", "add", "delete", "change", "insert",
                     "replace", "drop", "update", "modify", "edit", "reorder",
                     "move", "shift", "switch", "exchange"]:
            result = normalize_interests([f"{verb} the museum from day 1"])
            assert result is None or result == [], (
                f"Command verb '{verb}' should be filtered out, got: {result}"
            )

    def test_filters_long_phrase(self):
        """Phrases > 5 words (instructions, not keywords) are filtered."""
        result = normalize_interests([
            "I would like to see the pyramids in the morning",  # 11 words
            "parks",
        ])
        assert result == ["parks"]

    def test_short_valid_phrases_preserved(self):
        """Short phrases ≤ 5 words that aren't commands pass through."""
        result = normalize_interests([
            "historic sites",        # 2 words
            "art galleries",         # 2 words
            "water sports",          # 2 words
            "religious sites",       # 2 words
            "outdoor activities",    # 2 words
            "local culture",         # 2 words
        ])
        assert "history" in result  # historic sites → history
        assert "art" in result      # art galleries → art
        assert "water sports" in result
        assert "religion" in result  # religious sites → religion
        assert "adventure" in result  # outdoor activities → adventure
        assert "local culture" in result

    def test_mixed_list_filters_noise_preserves_interests(self):
        """Realistic scenario: commands + place names + valid interests → only valid interests."""
        result = normalize_interests([
            "remove abo tarek restaurant from the itinerary",  # command + long
            "museums",                                          # valid
            "el azhar mosque",                                  # 3 words, no command verb → passes through
        ])
        # "remove abo tarek..." should be filtered (contains command verb AND > 5 words)
        # "museums" should be preserved
        # "el azhar mosque" (3 words, no command verb) → passes through as-is
        assert "museums" in result
        assert len(result) == 2  # museums + el azhar mosque

    def test_command_verb_in_middle_of_phrase(self):
        """Command verb anywhere in the phrase triggers filtering."""
        result = normalize_interests([
            "please remove the last stop from day one",  # contains 'remove'
        ])
        assert result is None or result == []

    def test_short_clean_interests_unaffected(self):
        """Normal valid interests pass through unchanged."""
        result = normalize_interests(["history", "museums", "food", "shopping"])
        assert result == ["history", "museums", "food", "shopping"]

    def test_exactly_5_words_preserved(self):
        """Exactly 5 words is ≤ 5 threshold, so preserved."""
        result = normalize_interests(["one two three four five"])
        # This is not a recognizable interest keyword, so it passes through as-is
        assert result == ["one two three four five"]

    def test_6_words_filtered(self):
        """6 words is > 5 threshold, so filtered."""
        result = normalize_interests(["one two three four five six"])
        assert result is None or result == []

    def test_case_insensitive_command_detection(self):
        """Command detection is case-insensitive."""
        result = normalize_interests(["Remove the museum", "SWAP the cinema", "ADD a stop"])
        assert result is None or result == []

    def test_substring_word_boundary(self):
        """Command detection uses word boundaries (e.g. 'removed' contains 'remove' but as part of a word)."""
        # Note: 'removed' does contain the word 'remove' via word-boundary matching
        # because \bremove\b matches 'remove' within 'removed'? Let me check:
        # \bremove\b — \b before r requires a word boundary (non-word char or start),
        # \b after e requires a word boundary. In 'removed', after 'e' comes 'd' (word char)
        # so \b does NOT match. So 'removed' would NOT match 'remove'.
        # But 'remove' as a standalone word WILL match.
        result = normalize_interests(["removed", "removes", "removing"])
        # None of these should match 'remove' with word boundary
        assert result == ["removed", "removes", "removing"]

    def test_normalize_extracted_slots_integration(self):
        """Integration test: full normalization pipeline filters noise from interests."""
        raw = {
            "destination_city": "Cairo",
            "duration_days": 2,
            "budget_level": "moderate",
            "interests": [
                "remove abo tarek restaurant from the itinerary",
                "museums",
                "swap galaxy cinema with el azhar mosque",
                "history",
            ],
        }
        result = normalize_extracted_slots(raw)
        assert "museums" in result["interests"]
        assert "history" in result["interests"]
        # Noise should be filtered
        assert "remove" not in str(result["interests"]), "Filtered interests should not contain 'remove'"
        assert "swap" not in str(result["interests"]), "Filtered interests should not contain 'swap'"


# ══════════════════════════════════════════════════════════════════════════════
# normalize_extracted_slots (integration)
# ══════════════════════════════════════════════════════════════════════════════

class TestNormalizeExtractedSlots:
    def test_full_normalization(self):
        raw = {
            "destination_city": "Cairo",
            "duration_days": 5,
            "budget_level": "mid-range",
            "pace": "anything",
            "travel_style": "honeymoon",
            "food_preferences": ["local food", "street food"],
            "accommodation_preferences": ["boutique hotel"],
            "interests": ["museums", "art galleries"],
        }
        result = normalize_extracted_slots(raw)

        # City and duration pass through unchanged
        assert result["destination_city"] == "Cairo"
        assert result["duration_days"] == 5

        # Scalar normalizations applied
        assert result["budget_level"] == "moderate"
        assert result["pace"] == "moderate"
        assert result["travel_style"] == "romantic"

        # List normalizations applied
        assert "local cuisine" in result["food_preferences"]
        assert "street food" in result["food_preferences"]
        assert result["accommodation_preferences"] == ["luxury"]
        assert "museums" in result["interests"]
        assert "art" in result["interests"]

    def test_empty_input(self):
        assert normalize_extracted_slots({}) == {}

    def test_none_values_dropped(self):
        raw = {"budget_level": None, "destination_city": None}
        result = normalize_extracted_slots(raw)
        assert "budget_level" not in result
        assert "destination_city" not in result

    def test_already_canonical(self):
        raw = {
            "budget_level": "moderate",
            "pace": "relaxed",
            "travel_style": "adventure",
        }
        result = normalize_extracted_slots(raw)
        assert result["budget_level"] == "moderate"
        assert result["pace"] == "relaxed"
        assert result["travel_style"] == "adventure"

    def test_the_reviewers_bug_is_fixed(self):
        """
        The reviewer flagged: user says 'anything' → TourMate says
        "I'm not sure..." This test verifies the fix.
        """
        raw = {"pace": "anything"}
        result = normalize_extracted_slots(raw)
        assert result["pace"] == "moderate"

        raw2 = {"budget_level": "cheap", "travel_style": "chill"}
        result2 = normalize_extracted_slots(raw2)
        assert result2["budget_level"] == "budget"
        assert result2["travel_style"] == "relaxation"

    def test_unknown_values_pass_through(self):
        """Values the normalizer doesn't recognize pass through as-is."""
        raw = {"destination_city": "New Destination", "special_requests": "surprise me"}
        result = normalize_extracted_slots(raw)
        assert result["destination_city"] == "New Destination"
        assert result["special_requests"] == "surprise me"
