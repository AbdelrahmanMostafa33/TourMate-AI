from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.profile import UserProfile
from app.schemas.profile import QuizSubmitRequest
from ai.profiling.cold_start import generate_persona


async def save_quiz(user_id: str, data: QuizSubmitRequest, db: AsyncSession) -> UserProfile:

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    profile.age = data.age
    profile.sex = data.sex
    profile.travel_companion = data.travel_companion
    profile.location = data.location
    profile.adventure_relaxing = data.adventure_relaxing
    profile.nature_culture = data.nature_culture
    profile.popular_local = data.popular_local
    profile.budget_level = data.budget_level
    profile.early_night = data.early_night
    profile.independent_social = data.independent_social
    profile.accommodation_styles = data.accommodation_styles
    profile.dining_preferences = data.dining_preferences
    profile.interests = data.interests
    profile.traveler_types = data.traveler_types
    profile.quiz_completed = True


    persona = generate_persona(data.model_dump())
    profile.persona_name = persona["persona_name"]
    profile.persona_bio = persona["persona_bio"]
    profile.suggested_questions = persona["suggested_questions"]

    await db.commit()
    await db.refresh(profile)
    return profile


async def save_default_persona(user_id: str, db: AsyncSession) -> UserProfile:

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    profile.persona_name = "The Open Explorer"
    profile.persona_bio = (
        "You're a free spirit who enjoys discovering new places "
        "without a fixed plan. Every trip is a new adventure!"
    )
    profile.suggested_questions = [
        "What's a good place to visit this weekend?",
        "Surprise me with a travel idea!",
        "What are the most popular destinations right now?"
    ]
    profile.quiz_completed = False

    profile.accommodation_styles = []
    profile.dining_preferences = []
    profile.interests = []
    profile.traveler_types = []

    profile.adventure_relaxing = 50
    profile.nature_culture = 50
    profile.popular_local = 50
    profile.budget_level = 50
    profile.early_night = 50
    profile.independent_social = 50

    await db.commit()
    await db.refresh(profile)
    return profile