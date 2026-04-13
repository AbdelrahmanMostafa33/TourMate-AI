from http.client import HTTPException
from app.models.profile import UserProfile
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.profile import PersonaResponse, QuizSubmitRequest
from app.services.profile_service import save_quiz, save_default_persona

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
    