"""Saved Places routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.saved_place import SavedPlace
from app.models.place import Place
from app.schemas.saved_place import SavedPlaceCreate, SavedPlaceResponse

from app.repositories.place_repo import PlaceRepository

router = APIRouter()


@router.post("/", response_model=SavedPlaceResponse, status_code=status.HTTP_201_CREATED)
async def save_place(
    body: SavedPlaceCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate save
    existing = await db.execute(
        select(SavedPlace).where(
            SavedPlace.user_id == current_user["uid"],
            SavedPlace.place_id == body.place_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Place already saved")

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


@router.get("/")
async def get_saved_places(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return saved places with full place data embedded."""
    result = await db.execute(
        select(SavedPlace)
        .options(
            selectinload(SavedPlace.place).selectinload(Place.attraction_details),
            selectinload(SavedPlace.place).selectinload(Place.restaurant_details),
            selectinload(SavedPlace.place).selectinload(Place.hotel_details),
        )
        .where(SavedPlace.user_id == current_user["uid"])
        .order_by(SavedPlace.saved_at.desc())
    )
    saved = result.scalars().all()
    repo = PlaceRepository(db)
    items = []
    for sp in saved:
        place_dict = repo._place_to_dict(sp.place)
        items.append({
            "saved_place_id": sp.saved_place_id,
            "place_id": sp.place_id,
            "saved_at": sp.saved_at.isoformat() if sp.saved_at else None,
            "place": place_dict,
        })
    return items


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



