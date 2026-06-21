from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import RegisterRequest, UserResponse
import uuid

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(
    body:         RegisterRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    firebase_uid = current_user["uid"]
    email        = current_user.get("email")

    result = await db.execute(
        select(User).where(User.user_id == firebase_uid)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        user_id      = firebase_uid,
        email        = email,
        full_name    = body.full_name,
        phone_number = body.phone_number,
        home_city = body.home_city,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login")
async def login(
    user: dict         = Depends(get_current_user),
    db:   AsyncSession = Depends(get_db),
):
    firebase_uid = user["uid"]
    email        = user.get("email")

    result = await db.execute(
        select(User).where(User.user_id == firebase_uid)
    )
    db_user = result.scalar_one_or_none()

    if not db_user:
        db_user = User(
            user_id = firebase_uid,
            email   = email,
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

    return db_user


"""------------ Test Only ------------"""

@router.post("/test-register")
async def test_register(
    body: RegisterRequest,
    db:   AsyncSession = Depends(get_db),
):
    new_user = User(
        user_id      = str(uuid.uuid4()),
        full_name    = body.full_name,
        phone_number = body.phone_number,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user