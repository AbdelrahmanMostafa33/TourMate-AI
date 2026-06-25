"""
Script to:
1. Delete the problematic trip (4ff516ec-caa6-4a6f-b75c-ea228085fa30)
2. Verify that remaining trips' profiles can be loaded without the 'balanced' error

Run: python verify_fix.py
"""

import os
import sys
import asyncio

# Load .env
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

# ── DB Setup ────────────────────────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def main():
    print("=" * 60)
    print("TRIP PROFILE FIX VERIFICATION")
    print("=" * 60)

    async with async_session() as db:
        # ── 1. Check trip_profiles for any remaining 'balanced' pace values ──────
        result = await db.execute(
            text("SELECT trip_id, pace FROM trip_profiles WHERE pace = 'balanced'")
        )
        balanced_rows = result.fetchall()
        if balanced_rows:
            print(f"\n[FAIL] Found {len(balanced_rows)} rows with pace='balanced':")
            for row in balanced_rows:
                print(f"   Trip {row[0]}: pace={row[1]}")
        else:
            print("\n[OK] No rows with pace='balanced' remain - migration worked!")

        # ── 2. Try to load all trip profiles (simulates what the API does) ───────
        from app.models.profile import TripProfile

        result = await db.execute(select(TripProfile))
        profiles = result.scalars().all()
        print(f"\n📊 Total trip profiles in DB: {len(profiles)}")

        failed = 0
        for p in profiles:
            try:
                # Access pace to trigger the enum conversion (this is what crashes)
                _ = p.trip_id
                _ = p.pace
                _ = p.budget_level
                _ = p.travel_style
            except Exception as e:
                print(f"❌ Profile {p.profile_id}: {e}")
                failed += 1

        if failed == 0:
            print("[OK] All profiles load successfully - no LookupError!")
        else:
            print(f"\n[FAIL] {failed} profiles still fail to load!")

        # ── 3. Check which trips from the logs still have profiles ──────────────
        problematic_trip = "4ff516ec-caa6-4a6f-b75c-ea228085fa30"
        working_trip = "94799b34-92d6-411c-a1da-6f64671d9681"

        for tid in [problematic_trip, working_trip, "2cc92d87-d0f7-4dc6-8d31-c6c021e92fda"]:
            result = await db.execute(
                select(TripProfile).where(TripProfile.trip_id == tid)
            )
            profile = result.scalar_one_or_none()
            if profile:
                try:
                    _ = profile.pace
                    print(f"[OK] Trip {tid[:8]}... profile loads OK (pace={profile.pace})")
                except Exception as e:
                    print(f"[FAIL] Trip {tid[:8]}... profile FAILS: {e}")
            else:
                print(f"[INFO] Trip {tid[:8]}... has no profile")

    # ── 4. Delete the problematic trip ─────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("DELETING PROBLEMATIC TRIP")
    print(f"{'=' * 60}")

    # Import models for cascade awareness
    from app.models.trip import Trip
    from app.models.chat import Conversation, Message
    from app.models.itinerary import Itinerary, Day, ItineraryStop
    from app.models.profile import TripProfile
    from app.models.booking import Booking
    from app.models.feedback import Feedback

    async with async_session() as db:
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.conversation),
                selectinload(Trip.trip_profiles),
            )
            .where(Trip.trip_id == problematic_trip)
        )
        trip = result.scalar_one_or_none()

        if not trip:
            print(f"[INFO] Trip {problematic_trip[:8]}... already deleted or doesn't exist")
        else:
            print(f"[DELETE] Deleting trip: {trip.trip_name or 'Unnamed'} -> {trip.destination}")

            # Delete conversation first (cascades to messages)
            if trip.conversation:
                await db.delete(trip.conversation)

            # DB-level CASCADE will handle itineraries, days, stops, trip_profiles, etc.
            await db.delete(trip)
            await db.commit()
            print(f"[OK] Trip {problematic_trip[:8]}... deleted successfully!")

    # ── 5. Verify the remaining working trip still loads fine ──────────────────
    print(f"\n{'=' * 60}")
    print("VERIFYING REMAINING TRIPS")
    print(f"{'=' * 60}")

    async with async_session() as db:
        result = await db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops)
            )
            .order_by(Trip.created_at.desc())
        )
        trips = result.scalars().all()

        print(f"\nRemaining trips after deletion: {len(trips)}")
        for t in trips:
            print(f"   - {t.trip_id[:8]}... -> {t.destination} ({t.status})")

    await engine.dispose()
    print("\n[OK] Verification complete!")


if __name__ == "__main__":
    asyncio.run(main())
