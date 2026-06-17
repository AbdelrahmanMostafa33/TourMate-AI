from app.models.profile import TravelerProfile
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.profile import QuizSubmitRequest, FullProfileResponse, PersonaResponse
from app.services.profile_service import save_quiz, save_default_persona

router = APIRouter()


@router.post("/quiz", response_model=PersonaResponse)
async def submit_quiz(
    body: QuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["uid"]
    profile = await save_quiz(user_id, body, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=True,
    )


@router.post("/quiz/skip", response_model=PersonaResponse)
async def skip_quiz(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["uid"]
    profile = await save_default_persona(user_id, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=False,
    )


@router.post("/quiz/test", response_model=PersonaResponse)
async def test_submit_quiz(
    body: QuizSubmitRequest,
    db: AsyncSession = Depends(get_db)
):
    fake_user_id = "newuser123"
    profile = await save_quiz(fake_user_id, body, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=True,
    )


@router.get("/profile", response_model=PersonaResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["uid"]

    result = await db.execute(
        select(TravelerProfile).where(TravelerProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return PersonaResponse(
        persona_name=profile.persona_name or "The Open Explorer",
        persona_bio=profile.persona_bio or "",
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=bool(profile.persona_name),
    )


@router.patch("/profile/interests")
async def update_interests(
    body: dict,
    db: AsyncSession = Depends(get_db)
):
    user_id = body.get("user_id")
    new_interests = body.get("interests")
    new_persona_name = body.get("persona_name")
    new_persona_bio = body.get("persona_bio")

    result = await db.execute(
        select(TravelerProfile).where(TravelerProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.interests = new_interests

    if new_persona_name:
        profile.persona_name = new_persona_name
    if new_persona_bio:
        profile.persona_bio = new_persona_bio

    await db.commit()
    return {"message": "Profile updated successfully"}


@router.get("/profile/full", response_model=FullProfileResponse)
async def get_full_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["uid"]

    # Get User
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get Profile
    result = await db.execute(
        select(TravelerProfile).where(TravelerProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    return FullProfileResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        home_city=user.home_city,
        registration_date=user.registration_date,
        quiz_completed=bool(profile.persona_name) if profile else False,
        persona_name=profile.persona_name if profile else None,
        persona_bio=profile.persona_bio if profile else None,
        suggested_questions=profile.suggested_questions if profile else None,
        age=profile.age if profile else None,
        sex=profile.sex if profile else None,
        travel_companion=profile.travel_companion if profile else None,
        location=profile.location if profile else None,
        adventure_relaxing=profile.adventure_relaxing if profile else None,
        nature_culture=profile.nature_culture if profile else None,
        popular_local=profile.popular_local if profile else None,
        budget_level=profile.budget_level if profile else None,
        early_night=profile.early_night if profile else None,
        independent_social=profile.independent_social if profile else None,
        accommodation_styles=profile.accommodation_styles if profile else None,
        dining_preferences=profile.dining_preferences if profile else None,
        interests=profile.interests if profile else None,
        traveler_types=profile.traveler_types if profile else None,
    )