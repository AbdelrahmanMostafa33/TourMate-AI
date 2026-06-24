"""Unit tests for pool_manager service."""

import pytest

from ai_engine.services.pool_manager import (
    compute_pool_metadata,
    extract_used_place_ids,
    get_fresh_pool,
    merge_pool_enrichment,
    needs_database_query,
)


SAMPLE_ITINERARY = {
    "days": [
        {
            "day_number": 1,
            "stops": [
                {"id": "p1", "name": "Museum A"},
                {"id": "p2", "name": "Park B"},
            ],
        }
    ],
    "accommodation_suggestions": [{"id": "h1", "name": "Hotel X"}],
}


SAMPLE_POOL = [
    {"id": "p1", "category": "attraction", "sub_category": "museums"},
    {"id": "p2", "category": "attraction", "sub_category": "parks"},
    {"id": "p3", "category": "attraction", "sub_category": "museums"},
    {"id": "p4", "category": "restaurant"},
    {"id": "h1", "category": "hotel"},
    {"id": "h2", "category": "hotel"},
]


class TestExtractUsedPlaceIds:
    def test_collects_stops_and_hotels(self):
        used = extract_used_place_ids(SAMPLE_ITINERARY)
        assert used == {"p1", "p2", "h1"}


class TestGetFreshPool:
    def test_excludes_used_places(self):
        used = extract_used_place_ids(SAMPLE_ITINERARY)
        fresh = get_fresh_pool(SAMPLE_POOL, used)
        fresh_ids = {p["id"] for p in fresh}
        assert fresh_ids == {"p3", "p4", "h2"}


class TestComputePoolMetadata:
    def test_metadata_counts(self):
        meta = compute_pool_metadata(SAMPLE_POOL, SAMPLE_POOL[:4], SAMPLE_ITINERARY)
        assert meta["filtered_count"] == len(SAMPLE_POOL)
        assert meta["used_count"] == 3
        assert meta["remaining_unused"] == 3
        assert 0.0 <= meta["coverage_score"] <= 1.0


class TestNeedsDatabaseQuery:
    def test_sufficient_pool_for_reorder(self):
        need_db, reason = needs_database_query(
            "move the museum to day 2",
            SAMPLE_POOL,
            SAMPLE_POOL[:4],
            SAMPLE_ITINERARY,
            {"edit_type": "REORDER"},
        )
        assert need_db is False
        assert reason == "pool_sufficient"

    def test_missing_category_triggers_db(self):
        need_db, reason = needs_database_query(
            "add nightlife activities",
            SAMPLE_POOL,
            SAMPLE_POOL[:4],
            SAMPLE_ITINERARY,
            {"edit_type": "ADD_PLACE", "target_category": "nightlife"},
        )
        assert need_db is True
        assert reason == "missing_category"

    def test_regenerate_requested(self):
        need_db, reason = needs_database_query(
            "remove all museums and make it adventure",
            SAMPLE_POOL,
            SAMPLE_POOL[:4],
            SAMPLE_ITINERARY,
            {"edit_type": "REGENERATE"},
        )
        assert need_db is True
        assert reason == "regenerate_requested"


class TestMergePoolEnrichment:
    def test_no_duplicates(self):
        existing = [{"id": "a1"}, {"id": "a2"}]
        new = [{"id": "a2"}, {"id": "a3"}]
        merged = merge_pool_enrichment(existing, new)
        assert len(merged) == 3
        assert {p["id"] for p in merged} == {"a1", "a2", "a3"}
