# backend/tests/unit/test_ai_engine/test_itinerary_validator.py

"""
Unit tests for the Itinerary Validator.

Tests cover:
    - run_programmatic_checks(): deterministic feasibility checks
      (lives in ai_engine.evaluation.feasibility_checker)
    - validate_itinerary(): full validator with mocked LLM
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from ai_engine.evaluation.feasibility_checker import (
    run_programmatic_checks,
    MAX_DAILY_TRAVEL_MINUTES,
    MAX_DAILY_STOPS,
    MIN_DAILY_STOPS,
    MAX_CONSECUTIVE_CATEGORY,
    MAX_DISTANCE_BETWEEN_STOPS_KM,
)
from ai_engine.services.itinerary_validator import validate_itinerary
from tests.unit.test_ai_engine.conftest import _make_state


def _make_validator_state(**overrides) -> dict:
    """State with optimized_itinerary defaulting to a valid itinerary."""
    defaults = {
        "profile": None,
        "optimized_itinerary": _make_itinerary(),
    }
    defaults.update(overrides)
    return _make_state(**defaults)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_stop(**overrides) -> dict:
    """Create a minimal stop dict."""
    base = {
        "name": "Test Stop",
        "category": "attractions",
        "lat": 30.0444,
        "lon": 31.2357,
        "time_of_day": "morning",
    }
    base.update(overrides)
    return base


def _make_day(day_number: int, stops: list, total_travel_time_minutes: int = 60) -> dict:
    """Create a day dict with stops."""
    return {
        "day_number": day_number,
        "stops": stops,
        "total_travel_time_minutes": total_travel_time_minutes,
    }


def _make_itinerary(**overrides) -> dict:
    """Create a valid itinerary dict."""
    base = {
        "status": "generated",
        "days": [
            _make_day(1, [
                _make_stop(name="Museum", category="attractions", lat=30.05, lon=31.24),
                _make_stop(name="Restaurant", category="restaurant", lat=30.04, lon=31.23),
                _make_stop(name="Park", category="attractions", lat=30.03, lon=31.22),
            ], total_travel_time_minutes=60),
            _make_day(2, [
                _make_stop(name="Castle", category="attractions", lat=30.02, lon=31.21),
                _make_stop(name="Cafe", category="restaurant", lat=30.01, lon=31.20),
            ], total_travel_time_minutes=45),
        ],
        "accommodation_suggestions": [
            {"name": "Grand Hotel", "category": "hotel"},
        ],
    }
    base.update(overrides)
    return base


# ── run_programmatic_checks Tests ──────────────────────────────────────────

class TestRunProgrammaticChecks:

    def test_valid_itinerary_passes(self):
        """A well-formed itinerary should produce no issues."""
        itinerary = _make_itinerary()
        issues = run_programmatic_checks(itinerary)
        # Day 2 has 2 stops, MIN_DAILY_STOPS=3, so expect a warning
        assert len(issues) == 1
        assert "Day 2: only 2 stop(s)" in issues[0]

    def test_too_few_days(self):
        """Itinerary with 0 days should flag."""
        itinerary = _make_itinerary(days=[])
        issues = run_programmatic_checks(itinerary)
        assert any("at least" in i for i in issues)

    def test_too_many_stops_per_day(self):
        """Day with more than MAX_DAILY_STOPS should flag."""
        stops = [_make_stop(name=f"Stop {i}") for i in range(MAX_DAILY_STOPS + 2)]
        itinerary = _make_itinerary(days=[_make_day(1, stops)])
        issues = run_programmatic_checks(itinerary)
        assert any("exceeds max" in i for i in issues)

    def test_too_few_stops_per_day(self):
        """Day with fewer than MIN_DAILY_STOPS should flag."""
        itinerary = _make_itinerary(days=[_make_day(1, [_make_stop()])])
        issues = run_programmatic_checks(itinerary)
        assert any("add more activities" in i for i in issues)

    def test_consecutive_same_category(self):
        """3 consecutive same-category stops should flag."""
        stops = [
            _make_stop(name="Museum 1", category="attractions"),
            _make_stop(name="Museum 2", category="attractions"),
            _make_stop(name="Museum 3", category="attractions"),
        ]
        itinerary = _make_itinerary(days=[_make_day(1, stops)])
        issues = run_programmatic_checks(itinerary)
        assert any("consecutive" in i for i in issues)

    def test_two_consecutive_same_category_ok(self):
        """2 consecutive same-category stops should NOT flag."""
        stops = [
            _make_stop(name="Museum 1", category="attractions"),
            _make_stop(name="Museum 2", category="attractions"),
            _make_stop(name="Restaurant", category="restaurant"),
        ]
        itinerary = _make_itinerary(days=[_make_day(1, stops)])
        issues = run_programmatic_checks(itinerary)
        # Should not have consecutive issue (but might have other issues)
        consecutive_issues = [i for i in issues if "consecutive" in i]
        assert consecutive_issues == []

    def test_consecutive_hotels_not_flagged(self):
        """Consecutive hotels should not trigger the consecutive category check."""
        stops = [
            _make_stop(name="Hotel 1", category="hotel"),
            _make_stop(name="Hotel 2", category="hotel"),
        ]
        itinerary = _make_itinerary(days=[_make_day(1, stops)])
        issues = run_programmatic_checks(itinerary)
        consecutive_issues = [i for i in issues if "consecutive" in i]
        assert consecutive_issues == []

    def test_excessive_travel_time(self):
        """Day with too much travel time should flag."""
        itinerary = _make_itinerary(
            days=[_make_day(1, [_make_stop(), _make_stop()], total_travel_time_minutes=MAX_DAILY_TRAVEL_MINUTES + 30)]
        )
        issues = run_programmatic_checks(itinerary)
        assert any("travel time" in i for i in issues)

    def test_normal_travel_time_ok(self):
        """Day with reasonable travel time should pass."""
        itinerary = _make_itinerary(
            days=[_make_day(1, [_make_stop(), _make_stop()], total_travel_time_minutes=60)]
        )
        issues = run_programmatic_checks(itinerary)
        travel_issues = [i for i in issues if "travel time" in i]
        assert travel_issues == []

    def test_consecutive_stops_too_far_apart(self):
        """Two consecutive stops >40km apart should flag."""
        stop_near = _make_stop(name="Near", lat=30.0, lon=31.0)
        stop_far = _make_stop(name="Far", lat=31.0, lon=32.0)  # ~150km away
        itinerary = _make_itinerary(
            days=[_make_day(1, [stop_near, stop_far])]
        )
        issues = run_programmatic_checks(itinerary)
        assert any("too far" in i for i in issues)

    def test_consecutive_stops_close_ok(self):
        """Two consecutive stops within 40km should pass."""
        stop1 = _make_stop(name="A", lat=30.04, lon=31.23)
        stop2 = _make_stop(name="B", lat=30.05, lon=31.24)
        itinerary = _make_itinerary(
            days=[_make_day(1, [stop1, stop2])]
        )
        issues = run_programmatic_checks(itinerary)
        far_issues = [i for i in issues if "too far" in i]
        assert far_issues == []

    def test_no_accommodation_suggestions(self):
        """Missing accommodation suggestions should flag."""
        itinerary = _make_itinerary(accommodation_suggestions=[])
        issues = run_programmatic_checks(itinerary)
        assert any("accommodation" in i.lower() for i in issues)

    def test_too_many_hotel_suggestions(self):
        """More than 5 hotel suggestions should flag."""
        hotels = [{"name": f"Hotel {i}"} for i in range(6)]
        itinerary = _make_itinerary(accommodation_suggestions=hotels)
        issues = run_programmatic_checks(itinerary)
        assert any("hotel suggestions is too many" in i for i in issues)

    def test_five_hotel_suggestions_ok(self):
        """Exactly 5 hotel suggestions should pass."""
        hotels = [{"name": f"Hotel {i}"} for i in range(5)]
        itinerary = _make_itinerary(accommodation_suggestions=hotels)
        issues = run_programmatic_checks(itinerary)
        hotel_issues = [i for i in issues if "hotel suggestions" in i]
        assert hotel_issues == []

    def test_missing_lat_lon_stops_no_crash(self):
        """Stops without lat/lon should not crash the distance check."""
        stops = [
            {"name": "A", "category": "attractions"},
            {"name": "B", "category": "restaurant"},
        ]
        itinerary = _make_itinerary(days=[_make_day(1, stops)])
        # Should not raise
        issues = run_programmatic_checks(itinerary)
        assert isinstance(issues, list)


# ── validate_itinerary Tests (with mocked LLM) ─────────────────────────────

class TestRunValidation:

    @pytest.mark.asyncio
    async def test_no_itinerary_sets_invalid(self):
        """No optimized itinerary → invalid with error message."""
        state = _make_state(optimized_itinerary=None, profile=None)
        result = await validate_itinerary(state)

        assert result["is_valid"] is False
        assert "No itinerary" in result["validation"]["issues"][0]

    @pytest.mark.asyncio
    async def test_error_state_sets_invalid(self):
        """If state has an error → invalid immediately."""
        state = _make_state(error="Something went wrong", optimized_itinerary=_make_itinerary(), profile=None)
        result = await validate_itinerary(state)

        assert result["is_valid"] is False

    @pytest.mark.asyncio
    async def test_critical_programmatic_issues_skip_llm(self):
        """Too many stops (critical) → skip LLM, fail fast."""
        too_many_stops = [_make_stop(name=f"S{i}") for i in range(MAX_DAILY_STOPS + 3)]
        itinerary = _make_itinerary(
            days=[_make_day(1, too_many_stops)],
            accommodation_suggestions=[],
        )
        state = _make_state(optimized_itinerary=itinerary)

        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback") as mock_fn:
            result = await validate_itinerary(state)

        assert result["is_valid"] is False
        assert result["validation"]["score"] == 30
        # LLM should NOT have been called
        mock_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_critical_distance_issue_skip_llm(self):
        """Stops too far apart (critical) → skip LLM."""
        stop_near = _make_stop(name="Near", lat=30.0, lon=31.0)
        stop_far = _make_stop(name="Far", lat=31.0, lon=32.0)
        itinerary = _make_itinerary(
            days=[_make_day(1, [stop_near, stop_far])],
            accommodation_suggestions=[],
        )
        state = _make_state(optimized_itinerary=itinerary)

        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback") as mock_fn:
            result = await validate_itinerary(state)

        assert result["is_valid"] is False
        mock_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_itinerary_calls_llm(self):
        """Valid itinerary → LLM quality check is called."""
        llm_response = {
            "is_valid": True,
            "score": 90,
            "issues": [],
            "suggestions": ["Consider adding a local food tour"],
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(llm_response)

        state = _make_validator_state()
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", return_value=mock_response) as mock_fn:
            result = await validate_itinerary(state)

        mock_fn.assert_called_once()
        # Programmatic issue (1 issue) reduces score by 5: 90 - 5 = 85
        assert result["validation"]["score"] == 85
        assert result["is_valid"] is True
        # Quantitative metrics should be attached
        assert "metrics" in result["validation"]
        metrics = result["validation"]["metrics"]
        assert set(metrics.keys()) == {
            "category_diversity", "interest_alignment",
            "pacing", "geographic_coverage", "overall",
            "travel_style_alignment", "pace_alignment",
        }
        for v in metrics.values():
            assert 0.0 <= v <= 1.0

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_programmatic(self):
        """LLM exception → fallback to programmatic result."""
        state = _make_validator_state()
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", side_effect=Exception("API timeout")):
            result = await validate_itinerary(state)

        assert "LLM validation failed" in str(result["validation"]["issues"])

    @pytest.mark.asyncio
    async def test_llm_invalid_json_falls_back(self):
        """LLM returns invalid JSON → graceful fallback."""
        mock_response = MagicMock()
        mock_response.content = "not json"

        state = _make_validator_state()
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", return_value=mock_response):
            result = await validate_itinerary(state)

        # Should still have a validation result
        assert result["validation"] is not None

    @pytest.mark.asyncio
    async def test_non_critical_issues_still_calls_llm(self):
        """Non-critical issues (e.g., too few stops) → LLM still runs."""
        itinerary = _make_itinerary(
            days=[_make_day(1, [_make_stop()])],  # only 1 stop (non-critical)
        )
        llm_response = {
            "is_valid": True,
            "score": 70,
            "issues": ["Pacing could be improved"],
            "suggestions": [],
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(llm_response)

        state = _make_state(optimized_itinerary=itinerary)
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", return_value=mock_response) as mock_fn:
            result = await validate_itinerary(state)

        mock_fn.assert_called_once()
        # Score should be reduced due to programmatic issue
        assert result["validation"]["score"] <= 70

    @pytest.mark.asyncio
    async def test_programmatic_issues_lower_llm_score(self):
        """Programmatic issues should reduce the LLM-assigned score."""
        itinerary = _make_itinerary(
            days=[_make_day(1, [_make_stop()])],  # 1 stop = non-critical issue
            accommodation_suggestions=[],  # missing hotels = non-critical
        )
        llm_response = {
            "is_valid": True,
            "score": 85,
            "issues": [],
            "suggestions": [],
        }
        mock_response = MagicMock()
        mock_response.content = json.dumps(llm_response)

        state = _make_state(optimized_itinerary=itinerary)
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", return_value=mock_response):
            result = await validate_itinerary(state)

        # 2 programmatic issues × 5 points = 10 points reduction
        assert result["validation"]["score"] == 75

    @pytest.mark.asyncio
    async def test_user_message_included_in_prompt(self):
        """User's original message should be in the LLM prompt."""
        llm_response = {"is_valid": True, "score": 90, "issues": [], "suggestions": []}
        mock_response = MagicMock()
        mock_response.content = json.dumps(llm_response)

        state = _make_validator_state(user_message="I want a romantic Paris trip")
        with patch("ai_engine.services.itinerary_validator.invoke_with_fallback", return_value=mock_response) as mock_fn:
            await validate_itinerary(state)

        call_args = mock_fn.call_args
        messages = call_args[0][1]
        human_msg = messages[1].content
        assert "romantic Paris trip" in human_msg
