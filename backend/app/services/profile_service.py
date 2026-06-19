from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.profile import BehavioralProfile
from app.schemas.profile import QuizSubmitRequest


async def save_quiz(user_id: str, data: QuizSubmitRequest, db: AsyncSession) -> BehavioralProfile:
    """
    Save quiz responses and create/update a BehavioralProfile.

    Note: cold_start.generate_persona was removed as part of the Phase 6
    migration to per-trip profiles. Persona generation now happens in the
    conversation agent from chat context rather than from quiz data.
    """

    result = await db.execute(
        select(BehavioralProfile).where(BehavioralProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = BehavioralProfile(user_id=user_id)
        db.add(profile)

    profile.pace_style = data.pace_style.value
    profile.spending_style = data.spending_style.value
    profile.experience_lean = data.experience_lean.value
    profile.day_rhythm = data.day_rhythm.value
    profile.attraction_preference = data.attraction_preference.value
    profile.social_style = data.social_style.value
    profile.interests = data.interests
    profile.dining_preferences = data.dining_preferences
    profile.accommodation_preferences = data.accommodation_preferences
    profile.custom_interests = data.custom_interests
    profile.quiz_completed = True
    profile.completed_at = datetime.utcnow()

    await db.commit()
    await db.refresh(profile)
    return profile


async def save_default_persona(user_id: str, db: AsyncSession) -> BehavioralProfile:

    result = await db.execute(
        select(BehavioralProfile).where(BehavioralProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = BehavioralProfile(user_id=user_id)
        db.add(profile)

    profile.persona_title = "The Open Explorer"
    profile.persona_summary = (
        "You're a free spirit who enjoys discovering new places "
        "without a fixed plan. Every trip is a new adventure!"
    )
    profile.interests = []
    profile.dining_preferences = []
    profile.accommodation_preferences = []
    profile.custom_interests = []
    profile.quiz_completed = False

    await db.commit()
    await db.refresh(profile)
    return profile