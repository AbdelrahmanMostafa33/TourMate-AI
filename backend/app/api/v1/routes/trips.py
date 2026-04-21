from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import timedelta
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip, TripDay, TripActivity
from app.models.chat import Conversation, Message, MessageRole
from app.schemas.trip import TripCreate, TripResponse, TripSummary, TripStatusUpdate

router = APIRouter()


# ─── Helper ──────────────────────────────────────────────────────────────────

def build_auto_message(data: TripCreate, delta: int) -> str:
    msg = (
        f"Plan my trip to {data.destination_city}, {data.destination_country} "
        f"for {delta} days"
    )
    if data.start_date and data.end_date:
        msg += f" from {data.start_date} to {data.end_date}"
    if data.traveler_count and data.traveler_count > 1:
        msg += f", for {data.traveler_count} travelers"
    if data.budget_total:
        msg += f", with a total budget of ${data.budget_total}"
    if data.preferences:
        msg += f", my preferences are: {data.preferences}"
    return msg


# ═════════════════════════════════════════════════════════════════════════════
# POST /trips/
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/")
async def create_trip(
    data:         TripCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    user_id = current_user["uid"]

    # ── حساب المدة ───────────────────────────────────────────────────────
    if data.start_date and data.end_date:
        delta = (data.end_date - data.start_date).days + 1
    else:
        delta = 1

    # ── إنشاء Trip ───────────────────────────────────────────────────────
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

    # ── إنشاء الأيام ────────────────────────────────────────────────────
    if data.start_date:
        for i in range(delta):
            db.add(TripDay(
                trip_id    = trip.trip_id,
                day_number = i + 1,
                date       = data.start_date + timedelta(days=i),
            ))
    else:
        for i in range(delta):
            db.add(TripDay(
                trip_id    = trip.trip_id,
                day_number = i + 1,
            ))

    # ── إنشاء Conversation ───────────────────────────────────────────────
    conversation = Conversation(
        conversation_id = str(uuid.uuid4()),
        trip_id         = trip.trip_id,
        user_id         = user_id,
    )
    db.add(conversation)
    await db.flush()

    # ── بناء auto_message وحفظها كأول رسالة ──────────────────────────────
    auto_message = build_auto_message(data, delta)

    first_msg = Message(
        message_id      = str(uuid.uuid4()),
        conversation_id = conversation.conversation_id,
        role            = MessageRole.user,
        content         = auto_message,
    )
    db.add(first_msg)

    await db.commit()

    # ── جيب الـ Trip كامل ────────────────────────────────────────────────
    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.days)
            .selectinload(TripDay.activities)
        )
        .where(Trip.trip_id == trip.trip_id)
    )
    trip_obj = result.scalar_one()

    response = TripResponse.model_validate(trip_obj).model_dump()
    response["auto_message"]    = auto_message
    response["conversation_id"] = conversation.conversation_id

    return response


# ═════════════════════════════════════════════════════════════════════════════
# GET /trips/
# ═════════════════════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════════════════════
# GET /trips/{trip_id}
# ═════════════════════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════════════════════
# GET /trips/{trip_id}/itinerary
# ═════════════════════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════════════════════
# PATCH /trips/{trip_id}/status
# ═════════════════════════════════════════════════════════════════════════════

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