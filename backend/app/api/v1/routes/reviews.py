"""Reviews routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewResponse

router = APIRouter()


@router.post("/", response_model=ReviewResponse)
async def create_review(
    body: ReviewCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    review = Review(
        review_id=str(uuid.uuid4()),
        user_id=current_user["uid"],
        place_id=body.place_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


@router.get("/place/{place_id}", response_model=list[ReviewResponse])
async def get_reviews_for_place(place_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review).where(Review.place_id == place_id).order_by(Review.review_date.desc())
    )
    return result.scalars().all()


@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(Review.review_id == review_id, Review.user_id == current_user["uid"])
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await db.delete(review)
    await db.commit()
    return {"message": "Review deleted"}
