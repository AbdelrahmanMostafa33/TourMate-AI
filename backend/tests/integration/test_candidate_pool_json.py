"""
Integration tests for candidate_pool_json on Itinerary.

Verifies that the JSON column correctly persists and round-trips through
the SQLAlchemy ORM for various pool shapes used by the AI engine.
"""

import pytest
from datetime import date

from copy import deepcopy

from app.models.trip import Trip
from app.models.user import User
from app.models.itinerary import Itinerary
from app.services.itinerary_service import ItineraryService


# ── Shared pool data ────────────────────────────────────────────────────────

SAMPLE_POOL = {
    "filtered_places": [
        {
            "id": "place_001",
            "name": "Egyptian Museum",
            "category": "attractions",
            "lat": 30.0478,
            "lon": 31.2336,
            "rating": 4.7,
            "popularity_score": 90,
            "interest_tags": ["history", "art", "museum"],
        },
        {
            "id": "hotel_001",
            "name": "Marriott Mena House",
            "category": "hotel",
            "lat": 29.9758,
            "lon": 31.1334,
            "rating": 4.6,
            "popularity_score": 80,
        },
    ],
    "candidate_places": [
        {
            "id": "rest_001",
            "name": "Abu Shukri",
            "category": "restaurant",
            "lat": 30.0464,
            "lon": 31.2325,
            "rating": 4.5,
            "popularity_score": 75,
            "cuisine_type": "local cuisine",
        },
    ],
    "pool_metadata": {
        "total_places": 3,
        "unused_places": 3,
        "category_coverage": {
            "attractions": 1,
            "hotel": 1,
            "restaurant": 1,
        },
    },
    "itinerary": {
        "days": [
            {
                "day_number": 1,
                "stops": [{"id": "place_001", "name": "Egyptian Museum"}],
            }
        ],
    },
}


class TestCandidatePoolJsonRoundTrip:
    """candidate_pool_json column persists and round-trips through the ORM."""

    @pytest.fixture(autouse=True)
    async def _seed_user_and_trip(self, db_session):
        """Create the minimum parent records required for an Itinerary."""
        user = User(
            user_id="pool_test_user",
            email="pool@test.com",
            full_name="Pool Tester",
        )
        db_session.add(user)

        trip = Trip(
            trip_id="pool_test_trip",
            user_id="pool_test_user",
            destination="Cairo",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 4),
        )
        db_session.add(trip)
        await db_session.commit()

    # ── Basic round-trip ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_full_pool_round_trip(self, db_session):
        """Writing a complete pool dict and reading it back should be lossless."""
        itinerary = Itinerary(
            itinerary_id="itin_pool_001",
            trip_id="pool_test_trip",
            candidate_pool_json=SAMPLE_POOL,
        )
        db_session.add(itinerary)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "itin_pool_001")

        assert loaded is not None
        assert loaded.candidate_pool_json == SAMPLE_POOL
        assert loaded.candidate_pool_json["filtered_places"][0]["name"] == "Egyptian Museum"
        assert len(loaded.candidate_pool_json["candidate_places"]) == 1

    # ── Null value ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_null_pool_by_default(self, db_session):
        """Itinerary without a pool should have candidate_pool_json == None."""
        itinerary = Itinerary(
            itinerary_id="itin_pool_002",
            trip_id="pool_test_trip",
        )
        db_session.add(itinerary)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "itin_pool_002")
        assert loaded.candidate_pool_json is None

    # ── Empty dict ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_dict_pool(self, db_session):
        """An empty dict should persist and read back unchanged."""
        itinerary = Itinerary(
            itinerary_id="itin_pool_003",
            trip_id="pool_test_trip",
            candidate_pool_json={},
        )
        db_session.add(itinerary)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "itin_pool_003")
        assert loaded.candidate_pool_json == {}

    # ── Empty lists ──────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_lists_pool(self, db_session):
        """Pool with empty filtered/candidate lists should round-trip."""
        pool = {"filtered_places": [], "candidate_places": [], "pool_metadata": None}
        itinerary = Itinerary(
            itinerary_id="itin_pool_004",
            trip_id="pool_test_trip",
            candidate_pool_json=pool,
        )
        db_session.add(itinerary)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "itin_pool_004")
        assert loaded.candidate_pool_json["filtered_places"] == []
        assert loaded.candidate_pool_json["candidate_places"] == []

    # ── Update in-place ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_update_pool_in_place(self, db_session):
        """Modifying the pool dict and committing should persist changes."""
        pool_input = deepcopy(SAMPLE_POOL)
        itinerary = Itinerary(
            itinerary_id="itin_pool_005",
            trip_id="pool_test_trip",
            candidate_pool_json=pool_input,
        )
        db_session.add(itinerary)
        await db_session.commit()

        # Modify the pool
        loaded = await db_session.get(Itinerary, "itin_pool_005")
        pool = loaded.candidate_pool_json
        pool["filtered_places"].append({
            "id": "place_002",
            "name": "Khan El Khalili",
            "category": "attractions",
        })
        pool["pool_metadata"]["total_places"] = 4
        await db_session.commit()

        # Re-read from a fresh session-like perspective
        refreshed = await db_session.get(Itinerary, "itin_pool_005")
        assert len(refreshed.candidate_pool_json["filtered_places"]) == 3
        assert refreshed.candidate_pool_json["filtered_places"][2]["name"] == "Khan El Khalili"
        assert refreshed.candidate_pool_json["pool_metadata"]["total_places"] == 4

    # ── Replace entire pool ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_replace_pool_entirely(self, db_session):
        """Replacing candidate_pool_json entirely should persist the new value."""
        itinerary = Itinerary(
            itinerary_id="itin_pool_006",
            trip_id="pool_test_trip",
            candidate_pool_json=SAMPLE_POOL,
        )
        db_session.add(itinerary)
        await db_session.commit()

        new_pool = {"filtered_places": [{"id": "new_place"}], "candidate_places": []}
        loaded = await db_session.get(Itinerary, "itin_pool_006")
        loaded.candidate_pool_json = new_pool
        await db_session.commit()

        refreshed = await db_session.get(Itinerary, "itin_pool_006")
        assert refreshed.candidate_pool_json == new_pool
        assert refreshed.candidate_pool_json["filtered_places"][0]["id"] == "new_place"

    # ── Deeply nested structure ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_deeply_nested_pool_structure(self, db_session):
        """Deeply nested dicts/lists should survive the round-trip."""
        deep_pool = {
            "filtered_places": [
                {
                    "id": "place_999",
                    "nested": {
                        "level2": {
                            "level3": ["a", "b", {"key": "value"}],
                        }
                    },
                }
            ],
            "candidate_places": [],
            "itinerary": {
                "days": [
                    {
                        "day_number": 1,
                        "stops": [
                            {
                                "id": "s1",
                                "tags": ["tag1", "tag2"],
                                "meta": {"score": 0.95, "flag": True, "nil": None},
                            }
                        ],
                    }
                ]
            },
        }
        itinerary = Itinerary(
            itinerary_id="itin_pool_007",
            trip_id="pool_test_trip",
            candidate_pool_json=deep_pool,
        )
        db_session.add(itinerary)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "itin_pool_007")
        assert loaded.candidate_pool_json == deep_pool
        assert loaded.candidate_pool_json["itinerary"]["days"][0]["stops"][0]["meta"]["flag"] is True
        assert loaded.candidate_pool_json["itinerary"]["days"][0]["stops"][0]["meta"]["nil"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Service-layer tests — ItineraryService.save / get_candidate_pool
# ═════════════════════════════════════════════════════════════════════════════


class TestCandidatePoolServiceLayer:
    """Exercise ItineraryService.save_candidate_pool & get_candidate_pool_by_trip_id."""

    @pytest.fixture(autouse=True)
    async def _seed_and_service(self, db_session):
        """Create parent records and wire up the service."""
        user = User(user_id="svc_user", email="svc@test.com")
        db_session.add(user)

        trip = Trip(
            trip_id="svc_trip",
            user_id="svc_user",
            destination="Cairo",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 4),
        )
        db_session.add(trip)
        await db_session.commit()

        self.svc = ItineraryService(db_session)

    # ── save_candidate_pool ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_save_pool_persists_to_itinerary(self, db_session):
        """save_candidate_pool should write the pool to the itinerary's JSON column."""
        itinerary = Itinerary(itinerary_id="svc_itin_001", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        pool_state = {
            "filtered_places": [{"id": "p1", "name": "Pyramids"}],
            "candidate_places": [{"id": "h1", "name": "Hotel"}],
            "pool_metadata": {"total": 2},
        }
        await self.svc.save_candidate_pool("svc_itin_001", pool_state)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "svc_itin_001")
        assert loaded.candidate_pool_json == pool_state
        assert loaded.candidate_pool_json["filtered_places"][0]["name"] == "Pyramids"

    @pytest.mark.asyncio
    async def test_save_pool_empty_dict_is_noop(self, db_session):
        """save_candidate_pool with empty dict is a no-op (falsy guard)."""
        itinerary = Itinerary(itinerary_id="svc_itin_002", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        await self.svc.save_candidate_pool("svc_itin_002", {})
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "svc_itin_002")
        assert loaded.candidate_pool_json is None

    @pytest.mark.asyncio
    async def test_save_pool_none_ignored(self, db_session):
        """save_candidate_pool with None should be a no-op."""
        itinerary = Itinerary(itinerary_id="svc_itin_003", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        await self.svc.save_candidate_pool("svc_itin_003", None)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "svc_itin_003")
        assert loaded.candidate_pool_json is None

    @pytest.mark.asyncio
    async def test_save_pool_missing_itinerary_ignored(self, db_session):
        """save_candidate_pool for a non-existent itinerary should be a no-op."""
        await self.svc.save_candidate_pool("nonexistent_itin", SAMPLE_POOL)
        await db_session.commit()  # should not raise

    @pytest.mark.asyncio
    async def test_save_pool_overwrites_previous(self, db_session):
        """Calling save_candidate_pool twice should replace the first pool."""
        itinerary = Itinerary(itinerary_id="svc_itin_004", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        first_pool = {"filtered_places": [{"id": "old"}]}
        second_pool = {"filtered_places": [{"id": "new"}]}

        await self.svc.save_candidate_pool("svc_itin_004", first_pool)
        await db_session.commit()

        await self.svc.save_candidate_pool("svc_itin_004", second_pool)
        await db_session.commit()

        loaded = await db_session.get(Itinerary, "svc_itin_004")
        assert loaded.candidate_pool_json == second_pool

    # ── get_candidate_pool_by_trip_id ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_pool_returns_saved_data(self, db_session):
        """get_candidate_pool_by_trip_id should return the saved pool."""
        pool = deepcopy(SAMPLE_POOL)
        itinerary = Itinerary(itinerary_id="svc_itin_010", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        await self.svc.save_candidate_pool("svc_itin_010", pool)
        await db_session.commit()

        result = await self.svc.get_candidate_pool_by_trip_id("svc_trip")
        assert result == pool
        assert result["pool_metadata"]["total_places"] == 3

    @pytest.mark.asyncio
    async def test_get_pool_no_itinerary_returns_none(self, db_session):
        """get_candidate_pool_by_trip_id returns None when trip has no itinerary."""
        result = await self.svc.get_candidate_pool_by_trip_id("empty_trip")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pool_itinerary_without_pool_returns_none(self, db_session):
        """get_candidate_pool_by_trip_id returns None when pool column is NULL."""
        itinerary = Itinerary(itinerary_id="svc_itin_011", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        result = await self.svc.get_candidate_pool_by_trip_id("svc_trip")
        assert result is None

    @pytest.mark.asyncio
    async def test_full_save_get_cycle(self, db_session):
        """Complete cycle: create itinerary → save pool → retrieve pool."""
        itinerary = Itinerary(itinerary_id="svc_itin_020", trip_id="svc_trip")
        db_session.add(itinerary)
        await db_session.commit()

        pool = {
            "filtered_places": [
                {"id": "p1", "name": "Pyramids", "category": "attractions"},
                {"id": "p2", "name": "Museum", "category": "attractions"},
            ],
            "candidate_places": [
                {"id": "h1", "name": "Marriott", "category": "hotel"},
            ],
            "pool_metadata": {
                "total_places": 3,
                "category_coverage": {"attractions": 2, "hotel": 1},
            },
        }

        await self.svc.save_candidate_pool("svc_itin_020", pool)
        await db_session.commit()

        loaded = await self.svc.get_candidate_pool_by_trip_id("svc_trip")

        assert loaded is not None
        assert len(loaded["filtered_places"]) == 2
        assert len(loaded["candidate_places"]) == 1
        assert loaded["pool_metadata"]["total_places"] == 3
        assert loaded["filtered_places"][0]["id"] == "p1"
        assert loaded["candidate_places"][0]["name"] == "Marriott"
