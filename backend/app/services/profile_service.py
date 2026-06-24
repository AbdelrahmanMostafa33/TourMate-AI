# app/services/profile_service.py

import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.profile import TripProfile
from app.schemas.profile import TripProfileCreate


async def get_trip_profile(trip_id: str, db: AsyncSession) -> TripProfile | None:
    """
    Fetch the AI-generated trip profile for a given trip.
    Returns None if no profile exists yet.
    """
    result = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    return result.scalar_one_or_none()


async def upsert_trip_profile(
    trip_id: str,
    data: TripProfileCreate,
    db: AsyncSession,
) -> TripProfile:
    """
    Create or update a TripProfile for a given trip.
    - If a profile already exists for this trip, update its fields.
    - Otherwise, create a new one.
    """
    result = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = TripProfile(
            profile_id=str(uuid.uuid4()),
            trip_id=trip_id,
        )
        db.add(profile)

    # ── Update fields from request data ──────────────────────────────
    if data.budget_level is not None:
        profile.budget_level = data.budget_level
    if data.travel_style is not None:
        profile.travel_style = data.travel_style
    if data.pace is not None:
        profile.pace = data.pace
    if data.interests:
        profile.interests = data.interests
    if data.food_preferences:
        profile.food_preferences = data.food_preferences
    if data.accommodation_preferences:
        profile.accommodation_preferences = data.accommodation_preferences

    await db.commit()
    await db.refresh(profile)
    return profile
