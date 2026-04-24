from app.models.profile import UserProfile
from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.profile import QuizSubmitRequest,FullProfileResponse,PersonaResponse
from app.services.profile_service import save_quiz, save_default_persona
from app.models.user import User
router = APIRouter()


@router.post("/quiz", response_model=PersonaResponse)
def submit_quiz(
    body: QuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["uid"]
    profile = save_quiz(user_id, body, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=profile.quiz_completed,
    )


@router.post("/quiz/skip", response_model=PersonaResponse)
def skip_quiz(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["uid"]
    profile = save_default_persona(user_id, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=profile.quiz_completed,
)
    
@router.post("/quiz/test", response_model=PersonaResponse)
def test_submit_quiz(
    body: QuizSubmitRequest,
    db: Session = Depends(get_db)
):
    fake_user_id = "newuser123"
    profile = save_quiz(fake_user_id, body, db)

    return PersonaResponse(
        persona_name=profile.persona_name,
        persona_bio=profile.persona_bio,
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=profile.quiz_completed,
    )    
    
@router.get("/profile", response_model=PersonaResponse)
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["uid"]
    
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return PersonaResponse(
        persona_name=profile.persona_name or "The Open Explorer",
        persona_bio=profile.persona_bio or "",
        interests=profile.interests or [],
        suggested_questions=profile.suggested_questions or [],
        quiz_completed=profile.quiz_completed or False,
    )   
    
@router.patch("/profile/interests")
def update_interests(
    body: dict,
    db: Session = Depends(get_db)
):
    user_id = body.get("user_id")
    new_interests = body.get("interests")
    new_persona_name = body.get("persona_name")  
    new_persona_bio = body.get("persona_bio")   
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile.interests = new_interests
    
    if new_persona_name:
        profile.persona_name = new_persona_name
    if new_persona_bio:
        profile.persona_bio = new_persona_bio

    db.commit()
    return {"message": "Profile updated successfully"}

@router.get("/profile/full", response_model=FullProfileResponse)
def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user["uid"]

    # Get User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get Profile (might not exist if user hasn't taken or skipped quiz)
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == user_id
    ).first()

    # ── Build response ──
    return FullProfileResponse(
        # User info (always available)
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,

        # Quiz status
        quiz_completed=profile.quiz_completed if profile else False,

        # Persona (only if profile exists)
        persona_name=profile.persona_name if profile else None,
        persona_bio=profile.persona_bio if profile else None,
        suggested_questions=profile.suggested_questions if profile else None,

        # Basic info
        age=profile.age if profile else None,
        sex=profile.sex if profile else None,
        travel_companion=profile.travel_companion if profile else None,
        location=profile.location if profile else None,

        # Sliders
        adventure_relaxing=profile.adventure_relaxing if profile else None,
        nature_culture=profile.nature_culture if profile else None,
        popular_local=profile.popular_local if profile else None,
        budget_level=profile.budget_level if profile else None,
        early_night=profile.early_night if profile else None,
        independent_social=profile.independent_social if profile else None,

        # Multi-select
        accommodation_styles=profile.accommodation_styles if profile else None,
        dining_preferences=profile.dining_preferences if profile else None,
        interests=profile.interests if profile else None,
        traveler_types=profile.traveler_types if profile else None,
    )