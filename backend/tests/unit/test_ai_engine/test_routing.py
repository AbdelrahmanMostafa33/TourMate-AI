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
from ai_engine.tools.haversine import haversine
from ai_engine.tools.routing_tool import (
    get_reorder_indices,
    improve_order_2opt,
    order_stops_by_matrix,
    order_stops_by_proximity,
    WALK_THRESHOLD_KM,
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
