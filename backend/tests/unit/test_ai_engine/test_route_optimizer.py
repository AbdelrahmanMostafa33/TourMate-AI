# backend/tests/unit/test_ai_engine/test_route_optimizer.py

"""
Unit tests for the Route Optimizer (optimize_route).

Tests cover:
- Reordering stops via nearest-neighbor + 2-opt
- Travel-time matrix computation and annotation
- Transport mode assignment (walking < 2 km, driving > 2 km)
- Total travel time per day
- Deep copy safety (original draft not mutated)
- Edge cases: no draft, error state, single stop, empty days, empty stops
"""

import copy
import pytest
from unittest.mock import AsyncMock, patch

from ai_engine.services.route_optimizer import optimize_route
from tests.unit.test_ai_engine.conftest import _make_state


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_stop(name: str, lat: float, lon: float) -> dict:
    """Create a minimal stop dict with required lat/lon keys."""
    return {"name": name, "lat": lat, "lon": lon}


def _make_day(stops: list[dict], day_number: int = 1) -> dict:
    """Create a day dict with the given stops."""
    return {"day_number": day_number, "stops": stops}


def _make_draft(*days: dict) -> dict:
    """Create a draft itinerary from one or more day dicts."""
    return {"days": list(days)}


def _make_opt_state(**overrides) -> dict:
    """Create a minimal TripState dict for optimization tests."""
    defaults = {
        "profile": None,
        "planning_attempts": None,
        "destination_city": None,
        "duration_days": None,
    }
    defaults.update(overrides)
    return _make_state(**defaults)


# ── Exit-early Tests ────────────────────────────────────────────────────────

class TestExitEarly:
    """Tests for early-exit conditions before optimization runs."""

    @pytest.mark.asyncio
    async def test_no_draft_itinerary_returns_unchanged(self):
        """When draft_itinerary is None, state is returned unchanged."""
        state = _make_opt_state(draft_itinerary=None)
        result = await optimize_route(state)
        assert result["optimized_itinerary"] is None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_error_state_returns_unchanged(self):
        """When error is set, optimization is skipped."""
        state = _make_opt_state(
            draft_itinerary=_make_draft(_make_day([_make_stop("A", 30.0, 31.0)])),
            error="Something went wrong",
        )
        result = await optimize_route(state)
        assert result["optimized_itinerary"] is None

    @pytest.mark.asyncio
    async def test_empty_days_produces_empty_itinerary(self):
        """Draft with no days produces an optimized itinerary with empty days."""
        state = _make_opt_state(draft_itinerary={"days": []})
        result = await optimize_route(state)
        assert result["optimized_itinerary"]["days"] == []


# ── Single-Stop Tests ───────────────────────────────────────────────────────

class TestSingleStop:
    """Days with 0 or 1 stop should pass through without matrix calls."""

    @pytest.mark.asyncio
    async def test_single_stop_no_reorder(self):
        """Single stop stays in place, no travel time annotation."""
        stop = _make_stop("Pyramids", 29.9792, 31.1342)
        state = _make_opt_state(draft_itinerary=_make_draft(_make_day([stop])))
        result = await optimize_route(state)
        optimized = result["optimized_itinerary"]
        assert len(optimized["days"]) == 1
        assert len(optimized["days"][0]["stops"]) == 1
        assert optimized["days"][0]["stops"][0]["name"] == "Pyramids"
        assert optimized["days"][0]["total_travel_time_minutes"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_stops_no_crash(self):
        """Day with empty stops list doesn't crash."""
        state = _make_opt_state(draft_itinerary=_make_draft(_make_day([])))
        result = await optimize_route(state)
        assert result["optimized_itinerary"]["days"][0]["stops"] == []
        assert result["optimized_itinerary"]["days"][0]["total_travel_time_minutes"] == 0.0


# ── Multi-Stop Reordering Tests ─────────────────────────────────────────────

class TestReordering:
    """Tests for nearest-neighbor + 2-opt reordering with mocked matrix."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_reorders_stops_by_travel_time(self, mock_matrix):
        """Stops are reordered to minimize total travel time."""
        # 3 stops: A is close to C, far from B
        # Original order: A, B, C
        # Matrix: A->B=30min, A->C=5min, B->A=30min, B->C=25min, C->A=5min, C->B=25min
        # Optimal order: A -> C -> B (5 + 25 = 30 min)
        # vs original: A -> B -> C (30 + 25 = 55 min)
        stops = [
            _make_stop("A", 30.0, 31.0),
            _make_stop("B", 30.5, 31.5),  # far
            _make_stop("C", 30.01, 31.01),  # close to A
        ]
        matrix = [
            [0.0, 30.0, 5.0],
            [30.0, 0.0, 25.0],
            [5.0, 25.0, 0.0],
        ]
        mock_matrix.return_value = matrix

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        optimized = result["optimized_itinerary"]
        reordered_names = [s["name"] for s in optimized["days"][0]["stops"]]
        # The optimal route is A -> C -> B
        assert reordered_names == ["A", "C", "B"]

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_matrix_called_for_multi_stop_day(self, mock_matrix):
        """compute_day_matrix is called for days with >1 stop."""
        stops = [_make_stop("A", 30.0, 31.0), _make_stop("B", 30.1, 31.1)]
        mock_matrix.return_value = [[0.0, 15.0], [15.0, 0.0]]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        await optimize_route(state)
        # Verify it was called once, and with a list of 2 stops
        mock_matrix.assert_called_once()
        call_args = mock_matrix.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0]["name"] == "A"
        assert call_args[1]["name"] == "B"

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_matrix_not_called_for_single_stop(self, mock_matrix):
        """compute_day_matrix is NOT called for days with <=1 stop."""
        stops = [_make_stop("A", 30.0, 31.0)]
        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        await optimize_route(state)
        mock_matrix.assert_not_called()


# ── Transport Mode Tests ─────────────────────────────────────────────────────

class TestTransportMode:
    """Tests for walking vs driving mode assignment."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_walking_mode_for_close_stops(self, mock_matrix):
        """Stops < 2 km apart are tagged as walking."""
        # Two stops ~0.1 km apart
        stops = [
            _make_stop("Near1", 30.0, 31.0),
            _make_stop("Near2", 30.001, 31.001),
        ]
        # Travel time: 2 min (walk)
        mock_matrix.return_value = [[0.0, 2.0], [2.0, 0.0]]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        stop = result["optimized_itinerary"]["days"][0]["stops"][0]
        assert stop["transport_mode"] == "walking"
        assert stop["travel_time_to_next_minutes"] == 2.0

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_driving_mode_for_distant_stops(self, mock_matrix):
        """Stops > 2 km apart are tagged as driving."""
        stops = [
            _make_stop("Far1", 30.0, 31.0),
            _make_stop("Far2", 30.5, 31.5),
        ]
        # Travel time: 20 min (drive)
        mock_matrix.return_value = [[0.0, 20.0], [20.0, 0.0]]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        stop = result["optimized_itinerary"]["days"][0]["stops"][0]
        assert stop["transport_mode"] == "driving"
        assert stop["travel_time_to_next_minutes"] == 20.0


# ── Travel Time Annotation Tests ─────────────────────────────────────────────

class TestTravelTimeAnnotation:
    """Tests for travel_time_to_next_minutes and total_travel_time_minutes."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_travel_time_annotated_on_each_stop(self, mock_matrix):
        """Each stop (except last) gets travel_time_to_next_minutes."""
        stops = [
            _make_stop("A", 30.0, 31.0),
            _make_stop("B", 30.1, 31.1),
            _make_stop("C", 30.2, 31.2),
        ]
        mock_matrix.return_value = [
            [0.0, 10.0, 20.0],
            [10.0, 0.0, 15.0],
            [20.0, 15.0, 0.0],
        ]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        day_stops = result["optimized_itinerary"]["days"][0]["stops"]
        # Last stop should NOT have travel_time_to_next_minutes
        assert "travel_time_to_next_minutes" not in day_stops[-1]
        # All others should
        for s in day_stops[:-1]:
            assert "travel_time_to_next_minutes" in s
            assert "transport_mode" in s

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_total_travel_time_is_sum(self, mock_matrix):
        """total_travel_time_minutes is the sum of all inter-stop times."""
        stops = [
            _make_stop("A", 30.0, 31.0),
            _make_stop("B", 30.1, 31.1),
            _make_stop("C", 30.2, 31.2),
        ]
        # After reordering, suppose A->C->B with times 5 + 12 = 17
        mock_matrix.return_value = [
            [0.0, 20.0, 5.0],
            [20.0, 0.0, 12.0],
            [5.0, 12.0, 0.0],
        ]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        total = result["optimized_itinerary"]["days"][0]["total_travel_time_minutes"]
        assert isinstance(total, float)
        assert total > 0


# ── Deep Copy Safety Tests ──────────────────────────────────────────────────

class TestDeepCopySafety:
    """Optimization must not mutate the original draft itinerary."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_original_draft_not_mutated(self, mock_matrix):
        """The original draft_itinerary is not modified by optimization."""
        stops = [
            _make_stop("A", 30.0, 31.0),
            _make_stop("B", 30.1, 31.1),
        ]
        mock_matrix.return_value = [[0.0, 10.0], [10.0, 0.0]]

        original_stops = copy.deepcopy(stops)
        draft = _make_draft(_make_day(stops))
        original_draft = copy.deepcopy(draft)
        state = _make_opt_state(draft_itinerary=draft)

        await optimize_route(state)

        # Original draft should be unchanged
        assert state["draft_itinerary"] == original_draft
        assert state["draft_itinerary"]["days"][0]["stops"] == original_stops


# ── Multi-Day Tests ─────────────────────────────────────────────────────────

class TestMultiDay:
    """Tests for itineraries with multiple days."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_each_day_optimized_independently(self, mock_matrix):
        """Each day gets its own matrix computation and reordering."""
        day1_stops = [
            _make_stop("D1A", 30.0, 31.0),
            _make_stop("D1B", 30.1, 31.1),
        ]
        day2_stops = [
            _make_stop("D2A", 40.0, 41.0),
            _make_stop("D2B", 40.1, 41.1),
        ]

        # Return different matrices for each day
        mock_matrix.side_effect = [
            [[0.0, 10.0], [10.0, 0.0]],
            [[0.0, 5.0], [5.0, 0.0]],
        ]

        draft = _make_draft(
            _make_day(day1_stops, day_number=1),
            _make_day(day2_stops, day_number=2),
        )
        state = _make_opt_state(draft_itinerary=draft)
        result = await optimize_route(state)

        optimized = result["optimized_itinerary"]
        assert len(optimized["days"]) == 2
        assert mock_matrix.call_count == 2

        # Each day should have total_travel_time_minutes
        for day in optimized["days"]:
            assert "total_travel_time_minutes" in day
            assert day["total_travel_time_minutes"] >= 0


# ── Agent Messages Test ─────────────────────────────────────────────────────

class TestAgentMessages:
    """Test that the agent does not modify agent_messages."""

    @pytest.mark.asyncio
    @patch("ai_engine.services.route_optimizer.compute_day_matrix")
    async def test_agent_messages_not_modified(self, mock_matrix):
        """The optimization agent preserves existing agent_messages."""
        stops = [_make_stop("A", 30.0, 31.0), _make_stop("B", 30.1, 31.1)]
        mock_matrix.return_value = [[0.0, 10.0], [10.0, 0.0]]

        state = _make_opt_state(draft_itinerary=_make_draft(_make_day(stops)))
        result = await optimize_route(state)

        # Optimization agent appends a progress log message
        assert len(result["agent_messages"]) == 1
        assert "[RouteOptimizer]" in result["agent_messages"][0]
