# tests/integration/test_trip_name_place_id_tripprofile.py

"""
Integration test: verify that trip_name, place_id, and TripProfile
are correctly persisted when create_trip_from_ai_result() is called.

Fixes validated:
1. trip_name is set on Trip (not null)
2. place_id is populated on ItineraryStop records (not null)
3. TripProfile is created with non-null preference fields

Uses a fresh in-memory SQLite async database for each test.
"""

import pytest
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.trip import Trip
from app.models.itinerary import Itinerary, Day
from app.models.profile import TripProfile
from app.models.enums import BudgetLevel, TravelStyle, TripPace
from app.services.chat_service import ChatService


# ═════════════════════════════════════════════════════════════════════════════
# Sample AI Result WITH all data needed: trip_name, id fields, profile
# ═════════════════════════════════════════════════════════════════════════════

SAMPLE_AI_RESULT_WITH_ALL = {
    "itinerary": {
        # ── trip_name at the top level ───────────────────────────────
        "trip_name": "Summer Cairo Adventure",
        "destination": "Cairo",
        "destination_country": "Egypt",
        "start_date": "2026-07-01",
        "end_date": "2026-07-04",
        "duration_days": 4,
        "number_of_travelers": 2,
        "budget": 1500,
        # ── Accommodation WITH id field ──────────────────────────────
        "accommodation_suggestions": [
            {
                "id": "hotel_001",  # <-- This should become place_id
                "name": "Marriott Mena House",
                "rating": 4.6,
                "lat": 29.9758,
                "lon": 31.1334,
                "address": "Pyramids Area, Giza",
                "why_recommended": "Luxury hotel with pyramid views",
                "accommodation_type": "luxury",
            },
        ],
        "days": [
            {
                "day_number": 1,
                "theme": "Pyramids & Ancient History",
                "stops": [
                    {
                        # ── stop WITH id field ───────────────────────
                        "id": "place_003",  # <-- This should become place_id
                        "name": "Pyramids of Giza",
                        "category": "attractions",
                        "sub_category": "historic",
                        "lat": 29.9792,
                        "lon": 31.1342,
                        "rating": 4.8,
                        "address": "Giza, Egypt",
                        "description": "The last remaining Wonder of the Ancient World",
                        "why_recommended": "Must-see ancient wonder",
                        "estimated_duration_minutes": 180,
                        "suggested_time_of_day": "morning",
                        "estimated_cost": 20.0,
                    },
                    {
                        # ── stop WITHOUT id field ───────────────────
                        # This tests that place_id can be null gracefully
                        "name": "Great Sphinx",
                        "category": "attractions",
                        "sub_category": "historic",
                        "lat": 29.9753,
                        "lon": 31.1376,
                        "rating": 4.7,
                        "why_recommended": "Iconic monument",
                        "estimated_duration_minutes": 60,
                        "suggested_time_of_day": "morning",
                        "estimated_cost": 10.0,
                    },
                ],
            },
        ],
    },
    # ── Profile data (built from conversation slots) ────────────────────
    "profile": {
        "profile_id": None,
        "trip_id": None,  # Will be assigned by create_trip_from_ai_result
        "budget_level": "moderate",
        "travel_style": "cultural",
        "pace": "moderate",
        "interests": ["history", "art", "food"],
        "food_preferences": ["local cuisine", "street food"],
        "accommodation_preferences": ["boutique hotel"],
        "generated_at": None,
        "updated_at": None,
    },
}


# Sample AI result WITHOUT trip_name → should fallback to "Trip to {destination}"
SAMPLE_AI_RESULT_NO_TRIP_NAME = {
    "itinerary": {
        "destination": "Alexandria",
        "destination_country": "Egypt",
        "start_date": "2026-08-01",
        "end_date": "2026-08-03",
        "duration_days": 3,
        "number_of_travelers": 1,
        "days": [],
    },
    "profile": {
        "budget_level": "luxury",
        "travel_style": "relaxation",
        "pace": "relaxed",
        "interests": ["beach", "history"],
        "food_preferences": ["seafood"],
        "accommodation_preferences": ["resort"],
    },
}


# ═════════════════════════════════════════════════════════════════════════════
# Test 1: trip_name is saved correctly
# ═════════════════════════════════════════════════════════════════════════════


class TestTripName:
    """Verify trip_name is set correctly."""

    @pytest.mark.asyncio
    async def test_trip_name_from_ai_data(self, db_session):
        """trip_name from AI itinerary data is saved on Trip."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tn_001",
            ai_result=SAMPLE_AI_RESULT_WITH_ALL,
        )
        await db_session.commit()

        # Reload trip
        trip = await db_session.get(Trip, result["trip_id"])
        assert trip is not None
        assert trip.trip_name == "Summer Cairo Adventure", (
            f"Expected 'Summer Cairo Adventure', got '{trip.trip_name}'"
        )

    @pytest.mark.asyncio
    async def test_trip_name_fallback_to_destination(self, db_session):
        """When no trip_name in AI data → falls back to 'Trip to {destination}'."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tn_002",
            ai_result=SAMPLE_AI_RESULT_NO_TRIP_NAME,
        )
        await db_session.commit()

        trip = await db_session.get(Trip, result["trip_id"])
        assert trip is not None
        assert trip.trip_name == "Trip to Alexandria, Egypt", (
            f"Expected 'Trip to Alexandria, Egypt', got '{trip.trip_name}'"
        )

    @pytest.mark.asyncio
    async def test_trip_name_without_profile(self, db_session):
        """trip_name still works even without profile data."""
        ai_result = {
            "itinerary": {
                "destination": "Luxor",
                "destination_country": "Egypt",
                "start_date": "2026-09-01",
                "end_date": "2026-09-05",
                "duration_days": 5,
                "number_of_travelers": 2,
            },
            # No profile key
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tn_003",
            ai_result=ai_result,
        )
        await db_session.commit()

        trip = await db_session.get(Trip, result["trip_id"])
        assert trip is not None
        assert trip.trip_name == "Trip to Luxor, Egypt", (
            f"Expected 'Trip to Luxor, Egypt', got '{trip.trip_name}'"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Test 2: place_id is saved correctly on ItineraryStop
# ═════════════════════════════════════════════════════════════════════════════


class TestPlaceId:
    """Verify place_id is populated from stop data."""

    @pytest.mark.asyncio
    async def test_place_id_from_stop_id(self, db_session):
        """Stops with 'id' field → place_id is saved."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_pi_001",
            ai_result=SAMPLE_AI_RESULT_WITH_ALL,
        )
        await db_session.commit()

        # Reload with stops
        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded is not None

        # Day 1 has 2 activity stops
        day1 = loaded.days[0]
        stops = sorted(day1.stops, key=lambda s: s.order_in_day)

        # Stop 1: "Pyramids of Giza" has id="place_003" → place_id="place_003"
        s0 = stops[0]
        assert s0.place_snapshot["name"] == "Pyramids of Giza"
        assert s0.place_id == "place_003", (
            f"Expected place_id='place_003', got '{s0.place_id}'"
        )

        # Stop 2: "Great Sphinx" has no id → place_id=None
        s1 = stops[1]
        assert s1.place_snapshot["name"] == "Great Sphinx"
        assert s1.place_id is None, (
            f"Expected place_id=None for stop without id, got '{s1.place_id}'"
        )

        # Hotel accommodation (appended to last day): has id="hotel_001" → place_id="hotel_001"
        # Day 1 is the last (and only) day, so hotel is appended here
        day1_stops = sorted(day1.stops, key=lambda s: s.order_in_day)
        hotel_stop = day1_stops[-1]  # Last stop is the hotel
        assert hotel_stop.place_snapshot["name"] == "Marriott Mena House"
        assert hotel_stop.place_id == "hotel_001", (
            f"Expected place_id='hotel_001', got '{hotel_stop.place_id}'"
        )

    @pytest.mark.asyncio
    async def test_place_id_null_when_no_id_field(self, db_session):
        """Stops without 'id' field → place_id is null (not a crash)."""
        ai_result = {
            "itinerary": {
                "destination": "Aswan",
                "days": [
                    {
                        "day_number": 1,
                        "stops": [
                            {
                                "name": "Temple of Philae",
                                "category": "attractions",
                                "lat": 24.0256,
                                "lon": 32.8842,
                                # No "id" field
                            },
                        ],
                    },
                ],
            },
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_pi_002",
            ai_result=ai_result,
        )
        await db_session.commit()

        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        assert loaded is not None

        stop = loaded.days[0].stops[0]
        assert stop.place_id is None, (
            f"Expected place_id=None for stop without id, got '{stop.place_id}'"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Test 3: TripProfile is created with non-null fields
# ═════════════════════════════════════════════════════════════════════════════


class TestTripProfileCreation:
    """Verify TripProfile is created with correct data."""

    @pytest.mark.asyncio
    async def test_trip_profile_created_with_all_fields(self, db_session):
        """TripProfile is created with all preference fields populated."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tp_001",
            ai_result=SAMPLE_AI_RESULT_WITH_ALL,
        )
        await db_session.commit()

        # Reload TripProfile by trip_id
        query = select(TripProfile).where(
            TripProfile.trip_id == result["trip_id"]
        )
        profile = (await db_session.execute(query)).scalars().first()

        assert profile is not None, "TripProfile should be created"

        # ── Verify enum fields ────────────────────────────────────────
        assert profile.budget_level == BudgetLevel.MODERATE, (
            f"Expected MODERATE, got {profile.budget_level}"
        )
        assert profile.travel_style == TravelStyle.CULTURAL, (
            f"Expected CULTURAL, got {profile.travel_style}"
        )
        assert profile.pace == TripPace.MODERATE, (
            f"Expected BALANCED, got {profile.pace}"
        )

        # ── Verify list fields ────────────────────────────────────────
        assert profile.interests == ["history", "art", "food"], (
            f"Expected interests list, got {profile.interests}"
        )
        assert profile.food_preferences == ["local cuisine", "street food"], (
            f"Expected food_preferences list, got {profile.food_preferences}"
        )
        assert profile.accommodation_preferences == ["boutique hotel"], (
            f"Expected accommodation_preferences list, got {profile.accommodation_preferences}"
        )

        # ── Verify timestamps are set ─────────────────────────────────
        assert profile.generated_at is not None
        assert profile.updated_at is not None

        # ── Verify FK linkage ─────────────────────────────────────────
        assert profile.trip_id == result["trip_id"]

    @pytest.mark.asyncio
    async def test_trip_profile_created_with_different_enums(self, db_session):
        """Different enum values (luxury, relaxation, relaxed) map correctly."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tp_002",
            ai_result=SAMPLE_AI_RESULT_NO_TRIP_NAME,
        )
        await db_session.commit()

        query = select(TripProfile).where(
            TripProfile.trip_id == result["trip_id"]
        )
        profile = (await db_session.execute(query)).scalars().first()

        assert profile is not None
        assert profile.budget_level == BudgetLevel.LUXURY
        assert profile.travel_style == TravelStyle.RELAXATION
        assert profile.pace == TripPace.RELAXED
        assert profile.interests == ["beach", "history"]
        assert profile.food_preferences == ["seafood"]
        assert profile.accommodation_preferences == ["resort"]

    @pytest.mark.asyncio
    async def test_no_trip_profile_when_no_profile_data(self, db_session):
        """No profile data in ai_result → no TripProfile created (no crash)."""
        ai_result = {
            "itinerary": {
                "destination": "Sharm El Sheikh",
                "duration_days": 3,
                "days": [],
            },
            # No 'profile' key
        }
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_tp_003",
            ai_result=ai_result,
        )
        await db_session.commit()

        query = select(TripProfile).where(
            TripProfile.trip_id == result["trip_id"]
        )
        profile = (await db_session.execute(query)).scalars().first()

        assert profile is None, (
            "TripProfile should NOT be created when no profile data provided"
        )


# ═════════════════════════════════════════════════════════════════════════════
# Test 4: Combined — Full flow verification
# ═════════════════════════════════════════════════════════════════════════════


class TestFullFlowVerification:
    """Comprehensive test: all three fixes working together."""

    @pytest.mark.asyncio
    async def test_trip_place_id_and_profile_all_present(self, db_session):
        """Trip, ItineraryStop, and TripProfile all have correct data."""
        svc = ChatService(db_session)
        result = await svc.create_trip_from_ai_result(
            user_id="user_full_001",
            ai_result=SAMPLE_AI_RESULT_WITH_ALL,
        )
        await db_session.commit()

        trip_id = result["trip_id"]

        # ── 1. Verify Trip ─────────────────────────────────────────────
        trip = await db_session.get(Trip, trip_id)
        assert trip is not None
        assert trip.trip_name == "Summer Cairo Adventure"
        assert trip.destination == "Cairo, Egypt"
        assert trip.user_id == "user_full_001"

        # ── 2. Verify ItineraryStop has place_id ───────────────────────
        itinerary_id = result["itinerary"].itinerary_id
        query = (
            select(Itinerary)
            .options(selectinload(Itinerary.days).selectinload(Day.stops))
            .where(Itinerary.itinerary_id == itinerary_id)
        )
        loaded = (await db_session.execute(query)).scalars().first()
        day1 = loaded.days[0]
        stops = sorted(day1.stops, key=lambda s: s.order_in_day)

        # First stop has place_id
        assert stops[0].place_id == "place_003"
        # Hotel accommodation has place_id
        hotel_stop = stops[-1]
        assert hotel_stop.place_id == "hotel_001"

        # ── 3. Verify TripProfile ──────────────────────────────────────
        pq = select(TripProfile).where(TripProfile.trip_id == trip_id)
        profile = (await db_session.execute(pq)).scalars().first()
        assert profile is not None
        assert profile.trip_id == trip_id
        assert profile.budget_level == BudgetLevel.MODERATE
        assert profile.travel_style == TravelStyle.CULTURAL
        assert profile.pace == TripPace.MODERATE
        assert "history" in profile.interests
