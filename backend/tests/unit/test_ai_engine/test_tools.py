# backend/tests/unit/test_ai_engine/test_tools.py

import pytest
from ai_engine.tools.places_tool import get_places_for_city
from ai_engine.tools.routing_tool import get_travel_time_minutes, order_stops_by_proximity


# ── places_tool tests ─────────────────────────────────────────────────────────

class TestGetPlacesForCity:

    def test_known_city_returns_places(self):
        places = get_places_for_city("Cairo")
        assert isinstance(places, list)
        assert len(places) > 0

    def test_city_lookup_is_case_insensitive(self):
        lower = get_places_for_city("cairo")
        upper = get_places_for_city("CAIRO")
        assert lower == upper

    def test_each_place_has_required_keys(self):
        places = get_places_for_city("Cairo")
        for place in places:
            assert "name" in place
            assert "category" in place
            assert "lat" in place
            assert "lon" in place
            assert isinstance(place["lat"], float)
            assert isinstance(place["lon"], float)

    def test_no_interests_returns_all_places(self):
        all_places = get_places_for_city("Cairo", interests=None)
        assert len(all_places) > 0

    def test_matching_interest_filters_results(self):
        places = get_places_for_city("Cairo", interests=["museum"])
        assert all(
            "museum" in p["category"] or "museum" in p["name"].lower()
            for p in places
        )

    def test_non_matching_interest_falls_back_to_all(self):
        # Interest that matches nothing → should fall back to full list, not empty
        places = get_places_for_city("Cairo", interests=["scuba diving"])
        assert len(places) > 0

    def test_unknown_city_returns_default_places(self):
        places = get_places_for_city("Atlantis")
        assert isinstance(places, list)
        assert len(places) > 0

    def test_none_city_returns_default_places(self):
        places = get_places_for_city(None)
        assert isinstance(places, list)
        assert len(places) > 0


# ── routing_tool tests ────────────────────────────────────────────────────────

class TestGetTravelTime:

    def test_returns_float(self):
        origin = {"lat": 30.0478, "lon": 31.2336}
        dest   = {"lat": 29.9792, "lon": 31.1342}
        result = get_travel_time_minutes(origin, dest)
        assert isinstance(result, float)

    def test_returns_positive_value(self):
        origin = {"lat": 30.0478, "lon": 31.2336}
        dest   = {"lat": 29.9792, "lon": 31.1342}
        assert get_travel_time_minutes(origin, dest) > 0

    def test_same_point_returns_value(self):
        point = {"lat": 30.0478, "lon": 31.2336}
        # Sprint 3 mock always returns 20.0 — just assert it doesn't crash
        result = get_travel_time_minutes(point, point)
        assert isinstance(result, float)


class TestOrderStopsByProximity:

    def test_returns_list(self):
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 29.9, "lon": 31.1},
        ]
        result = order_stops_by_proximity(stops)
        assert isinstance(result, list)

    def test_returns_same_length(self):
        stops = [
            {"name": "A", "lat": 30.0, "lon": 31.0},
            {"name": "B", "lat": 29.9, "lon": 31.1},
            {"name": "C", "lat": 30.1, "lon": 31.2},
        ]
        result = order_stops_by_proximity(stops)
        assert len(result) == len(stops)

    def test_empty_list_returns_empty(self):
        assert order_stops_by_proximity([]) == []

    def test_single_stop_returns_single(self):
        stops = [{"name": "A", "lat": 30.0, "lon": 31.0}]
        result = order_stops_by_proximity(stops)
        assert len(result) == 1