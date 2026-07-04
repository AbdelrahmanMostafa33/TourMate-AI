from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func as sqlfunc
from datetime import timedelta
import logging
import uuid


logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.trip import Trip
from app.models.booking import Booking
from app.models.enums import BookingStatus, BookingType, TripStatus
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.chat import Conversation, Message
from app.models.profile import TripProfile
from app.schemas.trip import TripCreate, TripResponse, TripSummary, TripStatusUpdate
from app.schemas.profile import TripProfileCreate, TripProfileResponse
from app.services.profile_service import get_trip_profile, upsert_trip_profile
from app.services.booking_service import BookingService
from app.services.flight_service import FlightService

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

@router.post("/", status_code=status.HTTP_201_CREATED)
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

    # Count pending bookings for this trip
    pending_count = await db.scalar(
        select(sqlfunc.count(Booking.booking_id))
        .where(
            Booking.trip_id == trip_id,
            Booking.status == BookingStatus.pending,
        )
    )
    response = TripResponse.model_validate(trip).model_dump()
    response["pending_bookings_count"] = pending_count or 0
    return response


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

# ═════════════════════════════════════════════════════════════════════════════
# POST /trips/{trip_id}/cancel
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/{trip_id}/cancel")
async def cancel_trip(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Cancel an entire trip — cancels all bookings, refunds all payments, and marks trip as cancelled.

    Cancels both hotel and flight bookings for the trip, refunds any linked
    payments (marks them as refunded), and transitions the trip status to
    ``cancelled``.

    Returns:
        - success: bool
        - trip_id: str
        - status: "cancelled"
        - cancelled_bookings: list of booking IDs
        - refunded_payments: list of payment IDs

    Raises:
        404: Trip not found or doesn't belong to user
        400: Trip is already cancelled
    """
    # 1. Load trip and verify ownership
    result = await db.execute(
        select(Trip).where(
            Trip.trip_id == trip_id,
            Trip.user_id == current_user["uid"],
        )
    )
    trip = result.scalar_one_or_none()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.status == TripStatus.cancelled:
        raise HTTPException(status_code=400, detail="Trip is already cancelled")

    # 2. Load all bookings for this trip with payments eager-loaded
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.payment))
        .where(Booking.trip_id == trip_id)
    )
    bookings = list(result.scalars().all())

    cancelled_booking_ids: list[str] = []
    refunded_payment_ids: list[str] = []

    # 3. Cancel each booking and refund payments
    booking_svc = BookingService(db)
    flight_svc = FlightService(db)

    for booking in bookings:
        try:
            if booking.booking_type == BookingType.flight:
                await flight_svc.cancel_flight_booking(booking.booking_id, current_user["uid"])
            else:
                await booking_svc.cancel_booking(booking.booking_id)

            cancelled_booking_ids.append(booking.booking_id)

            if booking.payment:
                refunded_payment_ids.append(booking.payment.payment_id)
        except ValueError as exc:
            # Skip already-cancelled bookings, raise on unexpected errors
            if "already cancelled" not in str(exc):
                raise HTTPException(status_code=400, detail=f"Failed to cancel booking {booking.booking_id}: {exc}")
            # Already cancelled — still consider it done
            cancelled_booking_ids.append(booking.booking_id)

    # 4. Update trip status
    trip.status = TripStatus.cancelled

    await db.commit()

    logger.info(
        "[TripsRoute] Cancelled trip %s — %d booking(s) cancelled, %d payment(s) refunded",
        trip_id, len(cancelled_booking_ids), len(refunded_payment_ids),
    )

    return {
        "success": True,
        "trip_id": trip_id,
        "status": TripStatus.cancelled.value,
        "cancelled_bookings": cancelled_booking_ids,
        "refunded_payments": refunded_payment_ids,
    }


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