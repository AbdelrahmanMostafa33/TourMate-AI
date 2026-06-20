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
        assert normalize_pace("packed") == "packed"

    def test_relaxed_synonyms(self):
        assert normalize_pace("slow") == "relaxed"
        assert normalize_pace("easy") == "relaxed"
        assert normalize_pace("leisurely") == "relaxed"
        assert normalize_pace("chill") == "relaxed"
        assert normalize_pace("lazy") == "relaxed"

    def test_moderate_synonyms(self):
        assert normalize_pace("mixed") == "moderate"
        assert normalize_pace("flexible") == "moderate"
        assert normalize_pace("varied") == "moderate"
        assert normalize_pace("balanced") == "moderate"

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
        assert normalize_accommodation(["boutique hotel"]) == ["luxury hotel"]
        assert normalize_accommodation(["five star"]) == ["luxury hotel"]
        assert normalize_accommodation(["high-end"]) == ["luxury hotel"]
        assert normalize_accommodation(["upscale"]) == ["luxury hotel"]
        assert normalize_accommodation(["palace"]) == ["luxury hotel"]

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
        assert result == ["luxury hotel"]

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
        assert result["accommodation_preferences"] == ["luxury hotel"]
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
