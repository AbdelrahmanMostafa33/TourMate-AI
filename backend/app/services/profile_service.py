# app/services/profile_service.py

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


logger = logging.getLogger(__name__)

from app.models.profile import TripProfile
from app.models.user import User
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


async def update_traveler_persona(
    user_id: str,
    trip_id: str,
    db: AsyncSession,
) -> str | None:
    """
    Update the user's ``traveler_persona`` by blending their existing persona
    with the just-approved trip's ``TripProfile`` via an LLM call.

    This is called **after** an itinerary is approved.  It:
    1. Loads the user's current ``traveler_persona`` (may be None).
    2. Loads the trip's ``TripProfile``.
    3. If no TripProfile exists → skips (nothing new to learn).
    4. Calls ``persona_updater.update_persona()`` to produce an evolved persona.
    5. Persists the result back to ``users.traveler_persona``.

    Args:
        user_id: Firebase UID of the user.
        trip_id: ID of the trip that was just approved.
        db:      Active database session.

    Returns:
        The updated persona text, or ``None`` if no update was performed.
    """
    # 1. Load user
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(
            "[ProfileService] update_traveler_persona: user %s not found", user_id,
        )
        return None

    # 2. Load trip profile
    profile_result = await db.execute(
        select(TripProfile).where(TripProfile.trip_id == trip_id)
    )
    trip_profile = profile_result.scalar_one_or_none()
    if not trip_profile:
        logger.info(
            "[ProfileService] update_traveler_persona: no TripProfile for trip %s — skipping",
            trip_id,
        )
        return None

    # 3. Convert ORM to plain dict (avoid circular import: ai_engine → app)
    profile_data = {
        "budget_level": trip_profile.budget_level,
        "travel_style": trip_profile.travel_style,
        "pace": trip_profile.pace,
        "interests": trip_profile.interests or [],
        "food_preferences": trip_profile.food_preferences or [],
        "accommodation_preferences": trip_profile.accommodation_preferences or [],
    }

    # 4. Merge new trip profile data into preference confidence counts
    from ai_engine.profiling.preference_tracker import PreferenceTracker
    tracker = PreferenceTracker()
    merged_counts = tracker.merge(
        old_counts=user.preference_counts,
        profile_data=profile_data,
    )

    # 5. Call LLM to blend old persona + new trip profile + counts
    from ai_engine.profiling.persona_updater import update_persona as _llm_update_persona

    updated = await _llm_update_persona(
        old_persona=user.traveler_persona,
        trip_profile_data=profile_data,
        preference_counts=merged_counts,
    )

    if updated is None:
        logger.info(
            "[ProfileService] update_traveler_persona: LLM returned None — keeping old persona for user %s",
            user_id,
        )
        return None

    if updated == user.traveler_persona:
        # LLM returned the same text — no change needed
        # Still save the updated counts (they reflect new evidence)
        user.preference_counts = merged_counts
        await db.commit()
        await db.refresh(user)
        logger.info(
            "[ProfileService] update_traveler_persona: persona unchanged, but counts updated for user %s",
            user_id,
        )
        return updated

    # 6. Persist updated persona AND preference counts
    user.traveler_persona = updated
    user.preference_counts = merged_counts
    await db.commit()
    await db.refresh(user)

    logger.info(
        "[ProfileService] Traveler persona updated for user %s "
        "(based on trip %s)",
        user_id, trip_id,
    )
    return updated



