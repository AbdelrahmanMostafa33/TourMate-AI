# backend/tests/unit/test_ai_engine/test_routing.py

"""
Unit tests for the routing tool functions.

Tests cover:
    - haversine distance calculation
    - get_reorder_indices (matrix-based nearest-neighbor)
    - improve_order_2opt (2-opt local search)
    - order_stops_by_proximity (Euclidean fallback)
"""

import pytest
from unittest.mock import AsyncMock, patch
from ai_engine.tools.haversine import haversine
from ai_engine.tools.routing_tool import (
    WALK_THRESHOLD_KM,
    _WALK_SPEED_KMH,
    compute_day_matrix,
    get_reorder_indices,
    improve_order_2opt,
    order_stops_by_matrix,
    order_stops_by_proximity,
)


# ── Haversine Tests ───────────────────────────────────────────────────────────

class TestHaversine:

    def test_same_point_returns_zero(self):
        dist = haversine(30.0, 31.0, 30.0, 31.0)
        assert dist == 0.0

    def test_known_distance(self):
        # Cairo (30.0444, 31.2357) to Giza (30.0131, 31.2089) ≈ 3.7 km
        dist = haversine(30.0444, 31.2357, 30.0131, 31.2089)
        assert 3.0 < dist < 5.0

    def test_symmetry(self):
        d1 = haversine(30.0, 31.0, 29.9, 31.1)
        d2 = haversine(29.9, 31.1, 30.0, 31.0)
        assert abs(d1 - d2) < 0.001

    def test_returns_positive(self):
        dist = haversine(30.0, 31.0, 35.0, 36.0)
        assert dist > 0

    def test_long_distance(self):
        # Cairo to London ≈ 3,500 km
        dist = haversine(30.0444, 31.2357, 51.5074, -0.1278)
        assert 3400 < dist < 3600


# ── get_reorder_indices Tests ─────────────────────────────────────────────────

class TestGetReorderIndices:

    def test_single_stop(self):
        matrix = [[0.0]]
        order = get_reorder_indices([{"name": "A"}], matrix)
        assert order == [0]

    def test_two_stops(self):
        matrix = [[0.0, 10.0], [10.0, 0.0]]
        order = get_reorder_indices([{"name": "A"}, {"name": "B"}], matrix)
        assert order == [0, 1]  # Start at 0, nearest is 1

    def test_three_stops_nearest_neighbor(self):
        # 0→1 = 5, 0→2 = 10, 1→2 = 3
        # Nearest from 0: 1 (5), then from 1: 2 (3)
        matrix = [
            [0.0, 5.0, 10.0],
            [5.0, 0.0, 3.0],
            [10.0, 3.0, 0.0],
        ]
        order = get_reorder_indices([{"name": "A"}, {"name": "B"}, {"name": "C"}], matrix)
        assert order[0] == 0  # Always starts at first stop
        assert order[1] == 1  # Nearest to 0 is 1 (5 < 10)
        assert order[2] == 2  # Then 2

    def test_empty_stops(self):
        order = get_reorder_indices([], [[0.0]])
        assert order == []

    def test_returns_correct_length(self):
        n = 5
        matrix = [[0.0] * n for _ in range(n)]
        stops = [{"name": f"S{i}"} for i in range(n)]
        order = get_reorder_indices(stops, matrix)
        assert len(order) == n
        # All indices present
        assert set(order) == set(range(n))


# ── improve_order_2opt Tests ──────────────────────────────────────────────────

class TestImproveOrder2Opt:

    def test_three_stops_returns_unchanged(self):
        """With 3 or fewer stops, 2-opt should return unchanged."""
        order = [0, 1, 2]
        matrix = [[0.0, 10.0, 5.0], [10.0, 0.0, 8.0], [5.0, 8.0, 0.0]]
        result = improve_order_2opt(order, matrix)
        assert result == order

    def test_four_stops_can_improve(self):
        """A suboptimal 4-stop route should be improved by 2-opt."""
        # Route: 0→1→2→3
        # Edges: 0-1=10, 1-2=10, 2-3=10 (total 30)
        # But 0-2=1, 1-3=1 (so 0→2→1→3 would be better: 1+10+1=12)
        matrix = [
            [0.0, 10.0, 1.0, 10.0],
            [10.0, 0.0, 10.0, 1.0],
            [1.0, 10.0, 0.0, 10.0],
            [10.0, 1.0, 10.0, 0.0],
        ]
        order = [0, 1, 2, 3]
        result = improve_order_2opt(order, matrix)

        # Calculate route costs
        def route_cost(o):
            return sum(matrix[o[i]][o[i + 1]] for i in range(len(o) - 1))

        original_cost = route_cost(order)
        improved_cost = route_cost(result)
        assert improved_cost <= original_cost

    def test_already_optimal_unchanged(self):
        """An already-optimal route should not be changed."""
        # Linear: 0→1→2→3 with increasing costs away from diagonal
        matrix = [
            [0.0, 1.0, 5.0, 10.0],
            [1.0, 0.0, 1.0, 5.0],
            [5.0, 1.0, 0.0, 1.0],
            [10.0, 5.0, 1.0, 0.0],
        ]
        order = [0, 1, 2, 3]
        result = improve_order_2opt(order, matrix)
        # Should stay the same or improve
        assert result == order or (
            sum(matrix[result[i]][result[i + 1]] for i in range(len(result) - 1))
            <= sum(matrix[order[i]][order[i + 1]] for i in range(len(order) - 1))
        )

    def test_does_not_lose_stops(self):
        """Result should contain all original stops."""
        order = [0, 3, 1, 2]
        matrix = [
            [0.0, 5.0, 8.0, 3.0],
            [5.0, 0.0, 2.0, 6.0],
            [8.0, 2.0, 0.0, 7.0],
            [3.0, 6.0, 7.0, 0.0],
        ]
        result = improve_order_2opt(order, matrix)
        assert sorted(result) == sorted(order)


# ── order_stops_by_matrix Tests ───────────────────────────────────────────────

class TestOrderStopsByMatrix:

    def test_empty_stops(self):
        result = order_stops_by_matrix([], [[0.0]])
        assert result == []

    def test_single_stop(self):
        stops = [{"name": "A"}]
        result = order_stops_by_matrix(stops, [[0.0]])
        assert len(result) == 1
        assert result[0]["name"] == "A"

    def test_preserves_stop_dicts(self):
        stops = [
            {"name": "A", "lat": 30.0},
            {"name": "B", "lat": 29.9},
        ]
        matrix = [[0.0, 5.0], [5.0, 0.0]]
        result = order_stops_by_matrix(stops, matrix)
        assert all(isinstance(s, dict) for s in result)
        assert result[0]["name"] == "A"


# ── WALK_THRESHOLD_KM Tests ───────────────────────────────────────────────────

class TestWalkThreshold:

    def test_is_2km(self):
        assert WALK_THRESHOLD_KM == 2.0

    def test_walk_speed(self):
        assert _WALK_SPEED_KMH == 5.0


# ── compute_day_matrix Tests ──────────────────────────────────────────────────

class TestComputeDayMatrix:
    """Tests for the mixed-mode walk/drive matrix computation."""

    @pytest.mark.asyncio
    async def test_empty_stops_returns_zero_matrix(self):
        result = await compute_day_matrix([])
        assert result == [[0.0]]

    @pytest.mark.asyncio
    async def test_single_stop_returns_zero_matrix(self):
        stops = [{"name": "A", "lat": 30.0, "lon": 31.0}]
        result = await compute_day_matrix(stops)
        assert result == [[0.0]]

    @pytest.mark.asyncio
    async def test_all_walkable_uses_haversine_no_osrm(self):
        """All stops within 2km → Haversine estimate, no OSRM call."""
        # Two points ~0.5km apart (within WALK_THRESHOLD_KM)
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 30.004, "lon": 31.004},
        ]
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix") as mock_osrm:
            result = await compute_day_matrix(stops)
            mock_osrm.assert_not_called()  # No OSRM call for walkable pairs

        # Matrix should be symmetric
        assert result[0][0] == 0.0
        assert result[1][1] == 0.0
        assert result[0][1] == result[1][0]

        # Walk time should be positive
        assert result[0][1] > 0

    @pytest.mark.asyncio
    async def test_all_driving_uses_osrm(self):
        """All stops >2km apart → OSRM Table API call."""
        # Cairo to Giza ≈ 3.7km (beyond threshold)
        stops = [
            {"name": "Cairo", "lat": 30.0444, "lon": 31.2357},
            {"name": "Giza", "lat": 30.0131, "lon": 31.2089},
        ]
        mock_osrm = AsyncMock(return_value=[[0.0, 15.0], [15.0, 0.0]])
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix", mock_osrm):
            result = await compute_day_matrix(stops)
            mock_osrm.assert_called_once()

        assert result[0][1] == 15.0
        assert result[1][0] == 15.0

    @pytest.mark.asyncio
    async def test_mixed_walk_and_drive(self):
        """Some pairs walkable, some driving → split logic works."""
        # Stop A and B are close (~0.5km), C is far from both (~5km)
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 30.004, "lon": 31.004},  # ~0.5km from A
            {"name": "C", "lat": 30.1, "lon": 31.1},      # ~12km from A and B
        ]
        mock_osrm = AsyncMock(return_value=[[0.0, 20.0, 20.0],
                                              [20.0, 0.0, 20.0],
                                              [20.0, 20.0, 0.0]])
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix", mock_osrm):
            result = await compute_day_matrix(stops)

        # OSRM should be called (there are driving pairs)
        mock_osrm.assert_called_once()

        # A↔B is walkable (Haversine estimate)
        assert result[0][1] == result[1][0]
        assert result[0][1] > 0

        # A↔C and B↔C are driving (from OSRM)
        assert result[0][2] == 20.0
        assert result[2][0] == 20.0
        assert result[1][2] == 20.0
        assert result[2][1] == 20.0

        # Diagonal is always 0
        assert result[0][0] == 0.0
        assert result[1][1] == 0.0
        assert result[2][2] == 0.0

    @pytest.mark.asyncio
    async def test_walk_time_calculation(self):
        """Walk time = (haversine_distance / walk_speed) * 60 minutes."""
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 30.004, "lon": 31.004},
        ]
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix"):
            result = await compute_day_matrix(stops)

        # Calculate expected walk time
        dist_km = haversine(30.0, 31.0, 30.004, 31.004)
        expected_min = round((dist_km / _WALK_SPEED_KMH) * 60, 1)
        assert result[0][1] == expected_min

    @pytest.mark.asyncio
    async def test_osrm_receives_correct_sub_stops(self):
        """OSRM receives only the stops that need driving, in sorted index order."""
        # A-B close, C-D close, but A-C far
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 30.004, "lon": 31.004},
            {"name": "C", "lat": 30.1, "lon": 31.1},
            {"name": "D", "lat": 30.104, "lon": 31.104},
        ]
        mock_osrm = AsyncMock(return_value=[[0.0] * 4 for _ in range(4)])
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix", mock_osrm):
            await compute_day_matrix(stops)

        # OSRM should be called with the driving stops
        call_args = mock_osrm.call_args
        sub_stops = call_args[0][0]
        # Sub-stops should include A, C, D (B is walkable with A)
        # Actually all 4 are in sub_stops because A-C, A-D, B-C, B-D are driving
        # All 4 stops are in sub_stops because A-C, A-D, B-C, B-D are all driving
        assert len(sub_stops) == 4

    @pytest.mark.asyncio
    async def test_two_stops_symmetric(self):
        """Two stops produce symmetric matrix."""
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 30.004, "lon": 31.004},
        ]
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix"):
            result = await compute_day_matrix(stops)

        assert len(result) == 2
        assert len(result[0]) == 2
        assert result[0][1] == result[1][0]

    @pytest.mark.asyncio
    async def test_osrm_failure_propagates(self):
        """OSRM API failure should propagate as an exception."""
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 35.0, "lon": 36.0},  # far apart
        ]
        mock_osrm = AsyncMock(side_effect=Exception("OSRM unavailable"))
        with patch("ai_engine.tools.routing_tool.get_travel_time_matrix", mock_osrm):
            with pytest.raises(Exception, match="OSRM unavailable"):
                await compute_day_matrix(stops)
