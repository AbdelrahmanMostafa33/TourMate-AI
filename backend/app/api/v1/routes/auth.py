from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import RegisterRequest, UserResponse
import uuid

router = APIRouter()

@router.post("/register", response_model=UserResponse)
def register(
    body: RegisterRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    firebase_uid = current_user["uid"]
    email = current_user.get("email")

    existing = db.query(User).filter(User.user_id == firebase_uid).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        user_id=firebase_uid,
        email=email,
        full_name=body.full_name,
        phone=body.phone,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user