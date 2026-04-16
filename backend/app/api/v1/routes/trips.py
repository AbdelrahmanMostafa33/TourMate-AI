from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip, TripDay, TripActivity
from app.schemas.trip import TripCreate, TripResponse, TripSummary, TripStatusUpdate

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /trips/  ← إنشاء رحلة جديدة
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=TripResponse)
async def create_trip(
    data:         TripCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    user_id = current_user["uid"]                  # ← من الـ JWT مباشرةً
    delta   = (data.end_date - data.start_date).days + 1

    trip = Trip(
        trip_id             = str(uuid.uuid4()),
        user_id             = user_id,
        destination_city    = data.destination_city,
        destination_country = data.destination_country,
        start_date          = data.start_date,
        end_date            = data.end_date,
        duration_days       = delta,
        traveler_count      = data.traveler_count,
        budget_total        = data.budget_total,
        input_mode          = data.input_mode,
    )
    db.add(trip)
    await db.flush()

    # إنشاء TripDays تلقائياً
    for i in range(delta):
        db.add(TripDay(
            trip_id    = trip.trip_id,
            day_number = i + 1,
            date       = data.start_date + timedelta(days=i),
        ))

    await db.commit()

    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.days)
            .selectinload(TripDay.activities)
        )
        .where(Trip.trip_id == trip.trip_id)
    )
    return result.scalar_one()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /trips/  ← كل رحلات اليوزر (summary)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=list[TripSummary])
async def get_all_trips(
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trip)
        .where(Trip.user_id == current_user["uid"])
        .order_by(Trip.created_at.desc())
    )
    return result.scalars().all()

# ═══════════════════════════════════════════════════════════════════════════════
# GET /trips/{trip_id}  ← بيانات رحلة معينة (كاملة)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.days)
            .selectinload(TripDay.activities)
        )
        .where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


# ═══════════════════════════════════════════════════════════════════════════════
# GET /trips/{trip_id}/itinerary  ← للخريطة (Flutter بيناديه لما يستقبل itinerary_updated)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{trip_id}/itinerary", response_model=TripResponse)
async def get_itinerary(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.days)
            .selectinload(TripDay.activities)
        )
        .where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /trips/{trip_id}/status  ← تحديث status الرحلة
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{trip_id}/status")
async def update_trip_status(
    trip_id:      str,
    body:         TripStatusUpdate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trip).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    trip.status = body.status
    await db.commit()
    return {"trip_id": trip_id, "status": trip.status}
