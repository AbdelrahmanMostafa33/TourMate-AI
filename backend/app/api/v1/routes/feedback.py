"""Feedback routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackResponse

router = APIRouter()


@router.post("/", response_model=FeedbackResponse)
async def create_feedback(
    body: FeedbackCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback = Feedback(
        feedback_id=str(uuid.uuid4()),
        user_id=current_user["uid"],
        trip_id=body.trip_id,
        feedback_type=body.feedback_type,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.get("/", response_model=list[FeedbackResponse])
async def get_my_feedback(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback)
        .where(Feedback.user_id == current_user["uid"])
        .order_by(Feedback.submitted_at.desc())
    )
    return result.scalars().all()


@router.get("/trip/{trip_id}", response_model=list[FeedbackResponse])
async def get_feedback_for_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback)
        .where(
            Feedback.trip_id == trip_id,
            Feedback.user_id == current_user["uid"],
        )
        .order_by(Feedback.submitted_at.desc())
    )
    return result.scalars().all()


@router.put("/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: str,
    body: FeedbackUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback).where(
            Feedback.feedback_id == feedback_id,
            Feedback.user_id == current_user["uid"],
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    if body.feedback_type is not None:
        feedback.feedback_type = body.feedback_type
    if body.rating is not None:
        feedback.rating = body.rating
    if body.comment is not None:
        feedback.comment = body.comment

    await db.commit()
    await db.refresh(feedback)
    return feedback


@router.delete("/{feedback_id}")
async def delete_feedback(
    feedback_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback).where(
            Feedback.feedback_id == feedback_id,
            Feedback.user_id == current_user["uid"],
        )
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")
    await db.delete(feedback)
    await db.commit()
    return {"message": "Feedback deleted"}
