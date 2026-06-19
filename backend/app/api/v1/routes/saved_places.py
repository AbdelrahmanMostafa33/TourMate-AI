"""Saved Places routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.saved_place import SavedPlace
from app.schemas.saved_place import SavedPlaceCreate, SavedPlaceResponse

router = APIRouter()


@router.post("/", response_model=SavedPlaceResponse)
async def save_place(
    body: SavedPlaceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sp = SavedPlace(
        saved_place_id=str(uuid.uuid4()),
        user_id=current_user["uid"],
        place_id=body.place_id,
        note=body.note,
    )
    db.add(sp)
    await db.commit()
    await db.refresh(sp)
    return sp


@router.get("/", response_model=list[SavedPlaceResponse])
async def get_saved_places(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedPlace).where(SavedPlace.user_id == current_user["uid"])
    )
    return result.scalars().all()


@router.delete("/{saved_place_id}")
async def unsave_place(
    saved_place_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SavedPlace).where(
            SavedPlace.saved_place_id == saved_place_id,
            SavedPlace.user_id == current_user["uid"],
        )
    )
    sp = result.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Saved place not found")
    await db.delete(sp)
    await db.commit()
    return {"message": "Saved place removed"}
