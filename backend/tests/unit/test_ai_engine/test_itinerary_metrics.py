"""
Smoke tests for the Itinerary Metrics module.

Verifies that each scoring function returns values in 0.0–1.0 range
and produces sensible relative scores for different itinerary scenarios.
"""

import pytest
from ai_engine.evaluation.itinerary_metrics import (
    score_category_diversity,
    score_interest_alignment,
    score_pacing,
    score_geographic_coverage,
    compute_all_metrics,
)


# ── Factory helpers ──────────────────────────────────────────────────────────


def _make_stop(**overrides) -> dict:
    base = {
        "id": "stop_001",
        "name": "Test Stop",
        "category": "attraction",
        "sub_category": "museum",
        "interest_tags": ["history", "art"],
        "lat": 30.0444,
        "lon": 31.2357,
        "estimated_duration_minutes": 120,
        "suggested_time_of_day": "morning",
        "cuisine_type": "",
    }
    base.update(overrides)
    return base


def _make_day(day_number: int, stops: list) -> dict:
    return {
        "day_number": day_number,
        "theme": f"Day {day_number}",
        "stops": stops,
    }


def _make_itinerary(**overrides) -> dict:
    base = {
        "destination": "Cairo",
        "duration_days": 3,
        "days": [
            _make_day(1, [
                _make_stop(name="Museum", category="attraction", sub_category="museum",
                           interest_tags=["history"]),
                _make_stop(id="stop_002", name="Restaurant", category="restaurant",
                           sub_category="local cuisine", interest_tags=["food"],
                           cuisine_type="local", suggested_time_of_day="afternoon"),
                _make_stop(id="stop_003", name="Park", category="attraction",
                           sub_category="park", interest_tags=["nature"],
                           suggested_time_of_day="evening"),
            ]),
            _make_day(2, [
                _make_stop(id="stop_004", name="Market", category="attraction",
                           sub_category="shopping", interest_tags=["shopping"]),
                _make_stop(id="stop_005", name="Cafe", category="restaurant",
                           sub_category="cafe", interest_tags=["food"],
                           cuisine_type="coffee", suggested_time_of_day="afternoon"),
                _make_stop(id="stop_006", name="Mosque", category="attraction",
                           sub_category="religious", interest_tags=["religious"],
                           suggested_time_of_day="morning"),
                _make_stop(id="stop_007", name="Nightclub", category="attraction",
                           sub_category="nightlife", interest_tags=["nightlife"],
                           suggested_time_of_day="evening"),
            ]),
            _make_day(3, [
                _make_stop(id="stop_008", name="Bazaar", category="attraction",
                           sub_category="shopping", interest_tags=["shopping"]),
                _make_stop(id="stop_009", name="Bakery", category="restaurant",
                           sub_category="bakery", interest_tags=["food"],
                           cuisine_type="pastry", suggested_time_of_day="morning"),
            ]),
        ],
        "accommodation_suggestions": [
            {"id": "hotel_001", "name": "Grand Hotel", "rating": 4.5},
            {"id": "hotel_002", "name": "Boutique Inn", "rating": 4.2},
        ],
    }
    base.update(overrides)
    return base


def _make_profile(**overrides) -> dict:
    base = {
        "interests": ["history", "food", "shopping"],
        "food_preferences": ["local cuisine", "street food"],
        "budget_level": "moderate",
        "travel_style": "cultural",
        "pace": "moderate",
    }
    base.update(overrides)
    return base


# ── Tests ────────────────────────────────────────────────────────────────────


class TestScoreCategoryDiversity:

    def test_diverse_itinerary_scores_high(self):
        """Mixture of attraction + restaurant across days should score well."""
        itin = _make_itinerary()
        score = score_category_diversity(itin)
        assert 0.0 <= score <= 1.0
        assert score > 0.5, f"Expected high diversity, got {score}"

    def test_single_category_scores_low(self):
        """All stops in one category should score poorly."""
        itin = _make_itinerary(days=[
            _make_day(1, [_make_stop(category="attraction") for _ in range(4)]),
        ])
        score = score_category_diversity(itin)
        assert score < 0.5, f"Expected low diversity, got {score}"

    def test_empty_itinerary_returns_zero(self):
        score = score_category_diversity({"days": []})
        assert score == 0.0


class TestScoreInterestAlignment:

    def test_good_alignment(self):
        """Itinerary that matches user interests should score well."""
        itin = _make_itinerary()
        profile = _make_profile()
        score = score_interest_alignment(itin, profile)
        assert 0.0 <= score <= 1.0
        # shopping stores (market, bazaar) match 'shopping' interest
        # restaurant with cuisine_type 'local' partially matches 'local cuisine' food preference
        # cafe/restaurant with cuisine_type 'coffee'/'pastry' don't directly match
        assert score > 0.1, f"Expected some alignment, got {score}"

    def test_no_profile_returns_neutral(self):
        score = score_interest_alignment({}, None)
        assert score == 0.5

    def test_empty_interests_returns_neutral(self):
        itin = _make_itinerary()
        score = score_interest_alignment(itin, {})
        assert score == 0.5

    def test_no_matching_interests_scores_low(self):
        """Itinerary that doesn't match any user interest should score low."""
        itin = _make_itinerary(days=[
            _make_day(1, [_make_stop(interest_tags=["sports"], sub_category="sports")]),
        ])
        profile = _make_profile(interests=["history", "art"])
        score = score_interest_alignment(itin, profile)
        assert score < 0.5, f"Expected low alignment, got {score}"


class TestScorePacing:

    def test_balanced_itinerary_scores_well(self):
        """3-4 stops per day, mixed time slots, reasonable durations."""
        itin = _make_itinerary()
        score = score_pacing(itin)
        assert 0.0 <= score <= 1.0
        assert score > 0.5, f"Expected decent pacing, got {score}"

    def test_single_day_linerary_is_consistent(self):
        """Single day is always consistent."""
        itin = _make_itinerary(days=[
            _make_day(1, [_make_stop() for _ in range(4)]),
        ])
        score = score_pacing(itin)
        assert score > 0.6, f"Expected good pacing for single day, got {score}"

    def test_empty_days_returns_zero(self):
        score = score_pacing({"days": []})
        assert score == 0.0


class TestScoreGeographicCoverage:

    def test_two_close_stops_scores_low(self):
        """Stops in almost the same location should score low."""
        itin = _make_itinerary(days=[
            _make_day(1, [
                _make_stop(lat=30.0444, lon=31.2357),
                _make_stop(id="s2", lat=30.0445, lon=31.2358),
            ]),
        ])
        score = score_geographic_coverage(itin)
        assert 0.0 <= score <= 1.0
        assert score < 0.5, f"Expected low coverage, got {score}"

    def test_wide_spread_scores_higher(self):
        """Stops spread across the city should score better."""
        itin = _make_itinerary(days=[
            _make_day(1, [
                _make_stop(lat=30.00, lon=31.20),  # downtown
                _make_stop(id="s2", lat=30.10, lon=31.30),  # ~15km away
                _make_stop(id="s3", lat=29.95, lon=31.15),  # another area
            ]),
        ])
        score = score_geographic_coverage(itin)
        assert score > 0.5, f"Expected decent coverage for spread stops, got {score}"

    def test_single_stop_returns_zero(self):
        itin = _make_itinerary(days=[_make_day(1, [_make_stop()])])
        score = score_geographic_coverage(itin)
        assert score == 0.0


class TestComputeAllMetrics:

    def test_returns_all_keys(self):
        itin = _make_itinerary()
        profile = _make_profile()
        metrics = compute_all_metrics(itin, profile)

        expected_keys = {
            "category_diversity",
            "interest_alignment",
            "pacing",
            "geographic_coverage",
            "travel_style_alignment",
            "pace_alignment",
            "overall",
        }
        assert set(metrics.keys()) == expected_keys

    def test_all_scores_in_range(self):
        itin = _make_itinerary()
        profile = _make_profile()
        metrics = compute_all_metrics(itin, profile)

        for key, value in metrics.items():
            assert 0.0 <= value <= 1.0, f"{key} = {value} out of range"

    def test_overall_is_combination(self):
        itin = _make_itinerary()
        profile = _make_profile()
        metrics = compute_all_metrics(itin, profile)

        # Overall should be between min and max of individual scores
        individual = [v for k, v in metrics.items() if k != "overall"]
        assert min(individual) <= metrics["overall"] <= max(individual)
