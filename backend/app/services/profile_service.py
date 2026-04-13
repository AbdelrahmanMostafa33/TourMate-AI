from sqlalchemy.orm import Session
from app.models.profile import UserProfile
from app.schemas.profile import QuizSubmitRequest


def save_quiz(user_id: str, data: QuizSubmitRequest, db: Session) -> UserProfile:

    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

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

    # TODO: AI 
    profile.persona_name = "Explorer"
    profile.persona_bio = "AI persona coming soon"
    profile.suggested_questions = []

    db.commit()
    db.refresh(profile)
    return profile


def save_default_persona(user_id: str, db: Session) -> UserProfile:

    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

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

    db.commit()
    db.refresh(profile)
    return profile