"""Images routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.image import ImageResponse
from app.services.image_service import ImageService

router = APIRouter()


@router.get("/trip/{trip_id}", response_model=list[ImageResponse])
async def get_images_for_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all images for a trip, each with extracted features eagerly loaded."""
    svc = ImageService(db)
    return await svc.get_images_for_trip(trip_id)


@router.get("/{image_id}", response_model=ImageResponse)
async def get_image_with_features(
    image_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a single image with its extracted features eagerly loaded."""
    svc = ImageService(db)
    image = await svc.get_image_with_features(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = ImageService(db)
    deleted = await svc.delete_image(image_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Image not found")
    await db.commit()
    return {"message": "Image deleted"}
