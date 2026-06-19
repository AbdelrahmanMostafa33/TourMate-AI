from app.models.profile import TripProfile
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.profile import TripProfileCreate, TripProfileResponse, UserProfileResponse

router = APIRouter()


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    trip_id: str = None,
):
    """Get user profile, optionally with a trip profile."""
    user_id = current_user["uid"]

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    trip_profile = None
    if trip_id:
        tp_result = await db.execute(
            select(TripProfile).where(TripProfile.trip_id == trip_id)
        )
        trip_profile = tp_result.scalar_one_or_none()

    return UserProfileResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        home_city=user.home_city,
        registration_date=user.registration_date,
        traveler_persona=user.traveler_persona,
        trip_profile=trip_profile,
    )


@router.get("/profile/full", response_model=UserProfileResponse)
async def get_full_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full user profile."""
    user_id = current_user["uid"]

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserProfileResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        home_city=user.home_city,
        registration_date=user.registration_date,
        traveler_persona=user.traveler_persona,
    )