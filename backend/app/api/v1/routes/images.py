"""Images routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.image import Image
from app.schemas.image import ImageResponse

router = APIRouter()


@router.get("/trip/{trip_id}", response_model=list[ImageResponse])
async def get_images_for_trip(
    trip_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Image).where(Image.trip_id == trip_id)
    )
    return result.scalars().all()


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Image).where(Image.image_id == image_id)
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    await db.delete(image)
    await db.commit()
    return {"message": "Image deleted"}
