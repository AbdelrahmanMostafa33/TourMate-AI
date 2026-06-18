from app.models.profile import BehavioralProfile
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
        persona_title=profile.persona_title or "",
        persona_summary=profile.persona_summary or "",
        interests=profile.interests or [],
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
        persona_title=profile.persona_title or "",
        persona_summary=profile.persona_summary or "",
        interests=profile.interests or [],
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
        persona_title=profile.persona_title or "",
        persona_summary=profile.persona_summary or "",
        interests=profile.interests or [],
        quiz_completed=True,
    )


@router.get("/profile", response_model=PersonaResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user_id = current_user["uid"]

    result = await db.execute(
        select(BehavioralProfile).where(BehavioralProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return PersonaResponse(
        persona_title=profile.persona_title or "The Open Explorer",
        persona_summary=profile.persona_summary or "",
        interests=profile.interests or [],
        quiz_completed=bool(profile.persona_title),
    )


@router.patch("/profile/interests")
async def update_interests(
    body: dict,
    db: AsyncSession = Depends(get_db)
):
    user_id = body.get("user_id")
    new_interests = body.get("interests")
    new_persona_title = body.get("persona_title")
    new_persona_summary = body.get("persona_summary")

    result = await db.execute(
        select(BehavioralProfile).where(BehavioralProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.interests = new_interests

    if new_persona_title:
        profile.persona_title = new_persona_title
    if new_persona_summary:
        profile.persona_summary = new_persona_summary

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
        select(BehavioralProfile).where(BehavioralProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    return FullProfileResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        home_city=user.home_city,
        registration_date=user.registration_date,
        quiz_completed=profile.quiz_completed if profile else False,
        persona_title=profile.persona_title if profile else None,
        persona_summary=profile.persona_summary if profile else None,
        pace_style=profile.pace_style if profile else None,
        spending_style=profile.spending_style if profile else None,
        experience_lean=profile.experience_lean if profile else None,
        day_rhythm=profile.day_rhythm if profile else None,
        attraction_preference=profile.attraction_preference if profile else None,
        social_style=profile.social_style if profile else None,
        interests=profile.interests if profile else None,
        dining_preferences=profile.dining_preferences if profile else None,
        accommodation_preferences=profile.accommodation_preferences if profile else None,
        custom_interests=profile.custom_interests if profile else None,
        completed_at=profile.completed_at if profile else None,
        updated_at=profile.updated_at if profile else None,
    )