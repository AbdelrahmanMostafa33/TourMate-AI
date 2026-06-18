from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.profile import BehavioralProfile
from app.schemas.profile import QuizSubmitRequest
from ai_engine.profiling.cold_start import generate_persona


async def save_quiz(user_id: str, data: QuizSubmitRequest, db: AsyncSession) -> BehavioralProfile:

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

    # Map new enum fields to the old slider-based format that generate_persona expects
    style_map = {"ADVENTUROUS": 80, "RELAXING": 20}
    spending_map = {"LUXURIOUS": 80, "BUDGET_CONSCIOUS": 20}
    nature_map = {"NATURE_OUTDOORS": 20, "CULTURE": 80}

    legacy_quiz_data = {
        "adventure_relaxing": style_map.get(data.pace_style.value, 50),
        "nature_culture": nature_map.get(data.experience_lean.value, 50),
        "budget_level": spending_map.get(data.spending_style.value, 50),
        "interests": data.interests,
        "dining_preferences": data.dining_preferences,
        "traveler_types": data.accommodation_preferences,
        "travel_companion": "solo" if data.social_style.value == "INDEPENDENT" else "group",
    }
    persona = generate_persona(legacy_quiz_data)
    profile.persona_title = persona.get("persona_name", "")
    profile.persona_summary = persona.get("persona_bio", "")
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