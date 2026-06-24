"""
Unit tests for the Explainability module.

Tests cover:
    - explain_validation_decision()
    - explain_metric_scores()
    - explain_stop_placement()
    - explain_preference_change()
    - explain_profile()
    - format_full_explanation()
    - quick_summary()
"""

import pytest
from ai_engine.evaluation.explainability import (
    explain_validation_decision,
    explain_metric_scores,
    explain_stop_placement,
    explain_preference_change,
    explain_profile,
    format_full_explanation,
    quick_summary,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_stop(**overrides) -> dict:
    base = {
        "id": "stop_001",
        "name": "Egyptian Museum",
        "category": "attraction",
        "sub_category": "museum",
        "interest_tags": ["history", "art"],
        "lat": 30.04,
        "lon": 31.23,
        "estimated_duration_minutes": 120,
        "suggested_time_of_day": "morning",
        "why_recommended": "One of the world's greatest museums, perfect for history lovers.",
        "rating": 4.5,
    }
    base.update(overrides)
    return base


def _make_day(day_number: int, stops: list) -> dict:
    return {
        "day_number": day_number,
        "theme": "Ancient Wonders",
        "stops": stops,
    }


def _make_itinerary(**overrides) -> dict:
    base = {
        "destination": "Cairo",
        "duration_days": 3,
        "days": [
            _make_day(1, [
                _make_stop(),
                _make_stop(id="s2", name="Khan El Khalili", sub_category="shopping",
                           suggested_time_of_day="afternoon",
                           interest_tags=["shopping"]),
            ]),
            _make_day(2, [
                _make_stop(id="s3", name="Al-Azhar Mosque", sub_category="religious",
                           suggested_time_of_day="morning",
                           interest_tags=["religious", "history"]),
            ]),
        ],
        "accommodation_suggestions": [{"name": "Grand Hotel"}],
    }
    base.update(overrides)
    return base


def _make_validation(**overrides) -> dict:
    base = {
        "is_valid": True,
        "score": 85,
        "issues": ["Day 2: only 2 stop(s), add more activities"],
        "suggestions": ["Consider adding a local food tour"],
        "metrics": {
            "category_diversity": 0.72,
            "interest_alignment": 0.88,
            "pacing": 0.65,
            "geographic_coverage": 0.55,
            "overall": 0.75,
        },
    }
    base.update(overrides)
    return base


def _make_profile(**overrides) -> dict:
    base = {
        "interests": ["history", "food"],
        "food_preferences": ["local cuisine"],
        "budget_level": "moderate",
        "travel_style": "cultural",
        "pace": "moderate",
    }
    base.update(overrides)
    return base


# ── Test: explain_validation_decision ──────────────────────────────────────


class TestExplainValidationDecision:

    def test_valid_itinerary(self):
        result = explain_validation_decision(_make_validation())
        assert any("passed" in r.lower() for r in result)
        assert any("85/100" in r for r in result)

    def test_invalid_itinerary(self):
        result = explain_validation_decision(_make_validation(
            is_valid=False, score=30,
        ))
        assert any("not pass" in r or "did not" in r for r in result)
        assert any("30" in r for r in result)

    def test_none_validation(self):
        result = explain_validation_decision(None)
        assert len(result) == 1
        assert "not performed" in result[0]

    def test_includes_suggestions(self):
        result = explain_validation_decision(_make_validation())
        suggestions = [r for r in result if "local food tour" in r]
        assert len(suggestions) > 0

    def test_includes_metric_context(self):
        result = explain_validation_decision(_make_validation())
        quality_lines = [r for r in result if "good" in r.lower()]
        assert len(quality_lines) > 0

    def test_feasibility_issues_separated(self):
        validation = _make_validation(issues=[
            "Day 1: 10 stops exceeds max of 8",
            "Pacing could be improved",
        ])
        result = explain_validation_decision(validation)
        assert any("Feasibility" in r for r in result)
        assert any("Pacing" in r for r in result)


# ── Test: explain_metric_scores ────────────────────────────────────────────


class TestExplainMetricScores:

    def test_returns_all_metrics(self):
        metrics = {
            "category_diversity": 0.85,
            "interest_alignment": 0.70,
            "pacing": 0.50,
            "geographic_coverage": 0.30,
            "overall": 0.65,
        }
        result = explain_metric_scores(metrics)
        assert any("Category Diversity" in r for r in result)
        assert any("Interest Match" in r for r in result)
        assert any("Pacing" in r for r in result)
        assert any("Spread" in r for r in result)

    def test_none_metrics(self):
        result = explain_metric_scores(None)
        assert len(result) == 1
        assert "No quality metrics" in result[0]

    def test_includes_qualitative_labels(self):
        metrics = {
            "category_diversity": 0.90,
            "interest_alignment": 0.75,
            "pacing": 0.50,
            "geographic_coverage": 0.30,
            "overall": 0.65,
        }
        result = explain_metric_scores(metrics)
        combined = " ".join(result)
        assert "excellent" in combined or "good" in combined or "fair" in combined

    def test_includes_comments(self):
        metrics = {
            "category_diversity": 0.90,
            "interest_alignment": 0.90,
            "pacing": 0.90,
            "geographic_coverage": 0.90,
            "overall": 0.90,
        }
        result = explain_metric_scores(metrics)
        result_str = " ".join(result)
        assert "Great mix" in result_str


# ── Test: explain_stop_placement ───────────────────────────────────────────


class TestExplainStopPlacement:

    def test_returns_stop_name(self):
        stop = _make_stop()
        result = explain_stop_placement(stop)
        assert any("Egyptian Museum" in r for r in result)

    def test_includes_time_reason(self):
        stop = _make_stop(suggested_time_of_day="morning")
        result = explain_stop_placement(stop)
        assert any("morning" in r for r in result)

    def test_includes_duration(self):
        stop = _make_stop(estimated_duration_minutes=120)
        result = explain_stop_placement(stop)
        assert any("120" in r for r in result)

    def test_includes_why_recommended(self):
        stop = _make_stop()
        result = explain_stop_placement(stop)
        assert any("One of the world" in r for r in result)

    def test_includes_day_context(self):
        stop = _make_stop()
        day = _make_day(1, [stop])
        result = explain_stop_placement(stop, day_context=day)
        assert any("Day 1" in r for r in result)
        assert any("Ancient Wonders" in r for r in result)

    def test_interest_match_with_profile(self):
        stop = _make_stop(interest_tags=["history"])
        profile = _make_profile()
        result = explain_stop_placement(stop, profile=profile)
        assert any("history" in r.lower() for r in result)

    def test_fallback_when_no_why(self):
        stop = _make_stop(why_recommended="", interest_tags=["history"])
        result = explain_stop_placement(stop)
        combined = " ".join(result)
        assert "history" in combined

    def test_indoor_stop_in_afternoon(self):
        stop = _make_stop(category="attraction", sub_category="shopping",
                          suggested_time_of_day="afternoon")
        result = explain_stop_placement(stop)
        combined = " ".join(result)
        assert "afternoon" in combined


# ── Test: explain_preference_change ────────────────────────────────────────


class TestExplainPreferenceChange:

    def test_no_changes_when_no_input(self):
        result = explain_preference_change(None, None)
        assert any("No preference changes" in r for r in result)

    def test_detects_budget_change(self):
        old = {"budget_level": "budget"}
        new = {"budget_level": "luxury"}
        result = explain_preference_change(old, new)
        combined = " ".join(result)
        assert "Budget" in combined or "budget" in combined

    def test_detects_added_interests(self):
        old = {"interests": ["history"]}
        new = {"interests": ["history", "nightlife"]}
        result = explain_preference_change(old, new)
        combined = " ".join(result)
        assert "Added" in combined

    def test_detects_removed_interests(self):
        old = {"interests": ["history", "nightlife"]}
        new = {"interests": ["history"]}
        result = explain_preference_change(old, new)
        combined = " ".join(result)
        assert "Removed" in combined

    def test_includes_rerank_reason(self):
        adjustments = {"rerank_reason": "Adding nightlife venues to the ranking"}
        result = explain_preference_change({}, {}, adjustments)
        combined = " ".join(result)
        assert "nightlife" in combined

    def test_minor_adjustments_fallback(self):
        old = {"interests": ["history"]}
        new = {"interests": ["history"]}  # same
        result = explain_preference_change(old, new)
        combined = " ".join(result)
        assert "Minor" in combined


# ── Test: explain_profile ──────────────────────────────────────────────────


class TestExplainProfile:

    def test_none_profile(self):
        result = explain_profile(None)
        assert any("default" in r.lower() for r in result)

    def test_includes_style_and_pace(self):
        profile = _make_profile()
        result = explain_profile(profile)
        combined = " ".join(result)
        assert "cultural" in combined
        assert "moderate" in combined

    def test_includes_budget(self):
        profile = _make_profile(budget_level="luxury")
        result = explain_profile(profile)
        combined = " ".join(result)
        assert "Luxury" in combined


# ── Test: format_full_explanation ──────────────────────────────────────────


class TestFormatFullExplanation:

    def test_returns_all_sections(self):
        result = format_full_explanation(
            itinerary=_make_itinerary(),
            validation=_make_validation(),
            profile=_make_profile(),
        )
        assert "title" in result
        assert "profile" in result
        assert "verdict" in result
        assert "metrics" in result
        assert "stop_details" in result

    def test_title_contains_destination(self):
        result = format_full_explanation(itinerary=_make_itinerary())
        assert "Cairo" in result["title"]

    def test_stop_details_capped(self):
        result = format_full_explanation(itinerary=_make_itinerary())
        assert len(result["stop_details"]) > 0

    def test_no_itinerary(self):
        result = format_full_explanation()
        assert result["title"] == "Itinerary Summary"

    def test_includes_preference_changes(self):
        result = format_full_explanation(
            preference_changes={
                "old_prefs": {"budget_level": "budget"},
                "new_prefs": {"budget_level": "luxury"},
            },
        )
        assert "preference_changes" in result

    def test_agent_trace_included(self):
        result = format_full_explanation(
            agent_messages=["[Planner] Created 3 days", "[Validator] Passed"],
        )
        assert "agent_trace" in result
        assert len(result["agent_trace"]) == 2


# ── Test: quick_summary ────────────────────────────────────────────────────


class TestQuickSummary:

    def test_returns_string(self):
        result = quick_summary(
            itinerary=_make_itinerary(),
            validation=_make_validation(),
            metrics=_make_validation()["metrics"],
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_destination(self):
        result = quick_summary(itinerary=_make_itinerary())
        assert "Cairo" in result

    def test_includes_quality(self):
        result = quick_summary(
            itinerary=_make_itinerary(),
            metrics=_make_validation()["metrics"],
        )
        assert "good" in result.lower() or "75" in result or "quality" in result.lower()
