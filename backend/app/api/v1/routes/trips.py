from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func as sqlfunc
from datetime import timedelta
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.enums import TripStatus
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation, Message
from app.models.profile import TripProfile
from app.schemas.trip import TripCreate, TripResponse, TripSummary, TripStatusUpdate
from app.schemas.profile import TripProfileCreate, TripProfileResponse
from app.services.profile_service import get_trip_profile, upsert_trip_profile

router = APIRouter()


# ─── Helper ──────────────────────────────────────────────────────────────────

def build_auto_message(data: TripCreate, delta: int) -> str:
    msg = (
        f"Plan my trip to {data.destination} "
        f"for {delta} days"
    )
    if data.start_date and data.end_date:
        msg += f" from {data.start_date} to {data.end_date}"
    if data.number_of_travelers and data.number_of_travelers > 1:
        msg += f", for {data.number_of_travelers} travelers"
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
        trip_id              = str(uuid.uuid4()),
        user_id              = user_id,
        trip_name            = data.trip_name,
        destination          = data.destination,
        start_date           = data.start_date,
        end_date             = data.end_date,
        number_of_travelers  = data.number_of_travelers,
    )
    db.add(trip)
    await db.flush()

    # ── إنشاء Itinerary ──────────────────────────────────────────────────
    itinerary = Itinerary(
        itinerary_id = str(uuid.uuid4()),
        trip_id      = trip.trip_id,
    )
    db.add(itinerary)
    await db.flush()

    # ── إنشاء الأيام ────────────────────────────────────────────────────
    if data.start_date:
        for i in range(delta):
            db.add(Day(
                itinerary_id = itinerary.itinerary_id,
                day_number   = i + 1,
                date         = data.start_date + timedelta(days=i),
            ))
    else:
        for i in range(delta):
            db.add(Day(
                itinerary_id = itinerary.itinerary_id,
                day_number   = i + 1,
            ))

    # ── إنشاء Conversation ───────────────────────────────────────────────
    conversation = Conversation(
        conversation_id = str(uuid.uuid4()),
        user_id         = user_id,
    )
    db.add(conversation)
    await db.flush()

    # ── بناء auto_message وحفظها كأول رسالة ──────────────────────────────
    auto_message = build_auto_message(data, delta)

    first_msg = Message(
        message_id      = str(uuid.uuid4()),
        conversation_id = conversation.conversation_id,
        sender          = "user",
        content         = auto_message,
    )
    db.add(first_msg)

    await db.commit()

    # ── جيب الـ Trip كامل ────────────────────────────────────────────────
    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops)
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
        .options(
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
        )
        .where(Trip.user_id == current_user["uid"])
        .order_by(Trip.created_at.desc())
    )
    trips = result.scalars().all()

    # Compute duration from itinerary days for each trip
    summaries = []
    for t in trips:
        day_count = 0
        for itin in t.itineraries:
            day_count += len(itin.days)
        summaries.append(TripSummary(
            trip_id=t.trip_id,
            trip_name=t.trip_name,
            destination=t.destination,
            start_date=t.start_date,
            end_date=t.end_date,
            number_of_travelers=t.number_of_travelers,
            status=t.status,
            duration=day_count if day_count > 0 else None,
        ))

    return summaries


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
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops)
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
# DELETE /trips/{trip_id}
# ═════════════════════════════════════════════════════════════════════════════

@router.delete("/{trip_id}")
async def delete_trip(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Delete a trip and cascade to all related data.

    Deletes:
      - The trip's conversation and all its messages
      - The trip's AI-generated profile
      - All itineraries, days, and stops
      - Any images, bookings, and feedbacks
    """
    result = await db.execute(
        select(Trip)
        .options(
            selectinload(Trip.conversation),
            selectinload(Trip.trip_profiles),
        )
        .where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # ── 1. Delete the conversation and its messages ───────────────────────
    conversation = trip.conversation
    if conversation:
        # Null the FK so the trip row doesn't block conversation deletion
        trip.conversation_id = None
        trip.conversation = None
        await db.flush()
        await db.delete(conversation)  # cascades to messages via FK ondelete=CASCADE

    # ── 2. Delete the trip — DB-level ON DELETE CASCADE handles           ──
    #    itineraries → days → stops, trip_profiles, images, bookings, etc.
    await db.delete(trip)
    await db.commit()
    return {"message": "Trip deleted successfully"}


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
            selectinload(Trip.itineraries)
            .selectinload(Itinerary.days)
            .selectinload(Day.stops)
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

    # Set approved_at when trip is approved (status → active) via DB now()
    if body.status == TripStatus.active and trip.approved_at is None:
        trip.approved_at = sqlfunc.now()

    # Touch TripProfile.updated_at when trip is approved via DB now()
    if body.status == TripStatus.active:
        profile_result = await db.execute(
            select(TripProfile).where(TripProfile.trip_id == trip_id)
        )
        for prof in profile_result.scalars().all():
            prof.updated_at = sqlfunc.now()

    await db.commit()
    return {"trip_id": trip_id, "status": trip.status, "approved_at": trip.approved_at}


# ═════════════════════════════════════════════════════════════════════════════
# GET /trips/{trip_id}/profile
# ═════════════════════════════════════════════════════════════════════════════

@router.get("/{trip_id}/profile", response_model=TripProfileResponse)
async def get_trip_profile_endpoint(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Get the AI-generated trip profile for a specific trip.

    Returns 404 if no profile exists — the mobile client handles
    this gracefully and shows an empty state instead of crashing.
    """
    result = await db.execute(
        select(Trip).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    profile = await get_trip_profile(trip_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Trip profile not found")

    return profile


# ═════════════════════════════════════════════════════════════════════════════
# PUT /trips/{trip_id}/profile
# ═════════════════════════════════════════════════════════════════════════════

@router.put("/{trip_id}/profile", response_model=TripProfileResponse)
async def upsert_trip_profile_endpoint(
    trip_id:      str,
    data:         TripProfileCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Create or update the trip profile (called by AI engine or user)."""
    result = await db.execute(
        select(Trip).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    profile = await upsert_trip_profile(trip_id, data, db)
    return profile