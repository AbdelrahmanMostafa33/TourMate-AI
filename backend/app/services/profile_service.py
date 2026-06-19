import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.profile import TripProfile
from app.schemas.profile import TripProfileCreate


async def create_trip_profile(trip_id: str, data: TripProfileCreate, db: AsyncSession) -> TripProfile:
    """Create a new trip profile for a given trip."""
    profile = TripProfile(
        profile_id=str(uuid.uuid4()),
        trip_id=trip_id,
        budget_level=data.budget_level.value if data.budget_level else None,
        travel_style=data.travel_style.value if data.travel_style else None,
        pace=data.pace.value if data.pace else None,
        interests=data.interests,
        food_preferences=data.food_preferences,
        accommodation_preferences=data.accommodation_preferences,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_trip_profile(trip_id: str, db: AsyncSession) -> TripProfile | None:
    """Get the trip profile for a given trip."""
    result = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    return result.scalar_one_or_none()


async def update_trip_profile(trip_id: str, data: TripProfileCreate, db: AsyncSession) -> TripProfile:
    """Update an existing trip profile, or create one if it doesn't exist."""
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

    if data.budget_level is not None:
        profile.budget_level = data.budget_level.value
    if data.travel_style is not None:
        profile.travel_style = data.travel_style.value
    if data.pace is not None:
        profile.pace = data.pace.value
    if data.interests:
        profile.interests = data.interests
    if data.food_preferences:
        profile.food_preferences = data.food_preferences
    if data.accommodation_preferences:
        profile.accommodation_preferences = data.accommodation_preferences

    await db.commit()
    await db.refresh(profile)
    return profile


async def upsert_trip_profile_scores(
    trip_id: str,
    scores: dict,
    db: AsyncSession,
) -> TripProfile:
    """
    Upsert AI-generated scoring fields on a trip profile.
    Called by the AI pipeline after preference extraction.
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

    score_fields = [
        "luxury_score", "culture_score", "adventure_score",
        "shopping_score", "family_score", "confidence",
    ]
    for field in score_fields:
        if field in scores and scores[field] is not None:
            setattr(profile, field, scores[field])

    profile.generated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(profile)
    return profile