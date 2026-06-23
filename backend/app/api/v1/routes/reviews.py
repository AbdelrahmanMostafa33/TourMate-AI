"""Reviews routes – place reviews with CRUD + likes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════════
# POST /reviews/  –  Create a review for a place
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=ReviewResponse)
async def create_review(
    body: ReviewCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ── Check: one review per user per place ────────────────────────────
    existing = await db.execute(
        select(Review).where(
            Review.user_id == current_user["uid"],
            Review.place_id == body.place_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You have already reviewed this place. Use PUT to update.",
        )

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


# ═════════════════════════════════════════════════════════════════════════════
# GET /reviews/my-reviews  –  Get all reviews by the current user
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/my-reviews", response_model=list[ReviewResponse])
async def get_my_reviews(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review)
        .where(Review.user_id == current_user["uid"])
        .order_by(Review.review_date.desc())
    )
    return result.scalars().all()


# ═════════════════════════════════════════════════════════════════════════════
# GET /reviews/place/{place_id}  –  Get all reviews for a place + summary
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/place/{place_id}")
async def get_reviews_for_place(
    place_id: str,
    db: AsyncSession = Depends(get_db),
):
    # ── Fetch reviews with user data ───────────────────────────────────
    # Eager-load the user relationship so we can access full_name without
    # a separate query per review.
    result = await db.execute(
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.place_id == place_id)
        .order_by(Review.review_date.desc())
    )
    reviews = result.scalars().unique().all()

    # ── Compute average rating ─────────────────────────────────────────
    avg_result = await db.execute(
        select(func.avg(Review.rating), func.count(Review.review_id))
        .where(Review.place_id == place_id)
    )
    avg_rating, total_count = avg_result.one()

    return {
        "place_id":       place_id,
        "total_reviews":  total_count,
        "average_rating": round(float(avg_rating), 2) if avg_rating else None,
        "reviews": [
            {
                "review_id":   r.review_id,
                "user_id":     r.user_id,
                "place_id":    r.place_id,
                "rating":      r.rating,
                "comment":     r.comment,
                "review_date": r.review_date,
                "likes_count": r.likes_count,
                "user_name":   r.user.full_name if r.user else None,
            }
            for r in reviews
        ],
    }


# ═════════════════════════════════════════════════════════════════════════════
# GET /reviews/{review_id}  –  Get a single review
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(Review.review_id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


# ═════════════════════════════════════════════════════════════════════════════
# PUT /reviews/{review_id}  –  Update own review
# ═════════════════════════════════════════════════════════════════════════════

@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    body: ReviewUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.review_id == review_id,
            Review.user_id == current_user["uid"],
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if body.rating is not None:
        review.rating = body.rating
    if body.comment is not None:
        review.comment = body.comment

    await db.commit()
    await db.refresh(review)
    return review


# ═════════════════════════════════════════════════════════════════════════════
# POST /reviews/{review_id}/like  –  Like a review (increment likes_count)
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/{review_id}/like", response_model=ReviewResponse)
async def like_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(Review.review_id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    review.likes_count = (review.likes_count or 0) + 1
    await db.commit()
    await db.refresh(review)
    return review


# ═════════════════════════════════════════════════════════════════════════════
# DELETE /reviews/{review_id}  –  Delete own review
# ═════════════════════════════════════════════════════════════════════════════

@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Review).where(
            Review.review_id == review_id,
            Review.user_id == current_user["uid"],
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await db.delete(review)
    await db.commit()
    return {"message": "Review deleted"}
