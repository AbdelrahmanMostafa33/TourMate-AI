"""Recommendations routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.recommendation import Recommendation
from app.schemas.recommendation import RecommendationResponse

router = APIRouter()


@router.get("/trip/{trip_id}", response_model=list[RecommendationResponse])
async def get_recommendations_for_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Recommendation).where(Recommendation.trip_id == trip_id)
    )
    return result.scalars().all()


@router.patch("/{recommendation_id}/accept", response_model=RecommendationResponse)
async def accept_recommendation(
    recommendation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.enums import RecommendationStatus
    result = await db.execute(
        select(Recommendation).where(Recommendation.recommendation_id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.status = RecommendationStatus.accepted
    await db.commit()
    await db.refresh(rec)
    return rec


@router.patch("/{recommendation_id}/reject", response_model=RecommendationResponse)
async def reject_recommendation(
    recommendation_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.enums import RecommendationStatus
    result = await db.execute(
        select(Recommendation).where(Recommendation.recommendation_id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.status = RecommendationStatus.rejected
    await db.commit()
    await db.refresh(rec)
    return rec
