"""
Booking routes — Hybrid booking system.

Provides a focused API for the Booking → Payment → Receipt pipeline.
Booking confirmations are simulated (no real hotel/restaurant API),
while payments are processed through Stripe sandbox (test mode) with a
simulated fallback.

Endpoints:
  - ``POST   /``                          — Create a booking
  - ``GET    /trip/{trip_id}``            — List bookings for a trip
  - ``POST   /{booking_id}/cancel``       — Cancel a booking
  - ``POST   /{booking_id}/initiate-payment``   — Initiate Stripe Payment Sheet
  - ``POST   /{booking_id}/confirm-after-payment``  — Confirm after Payment Sheet success
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.booking import Booking, Payment
from app.models.enums import TripStatus
from app.models.trip import Trip
from app.schemas.booking import (
    BookingCreate, BookingResponse,
    PaymentCreate, ConfirmAfterPaymentRequest,
)
from app.services.booking_service import BookingService

router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────────────

async def _load_booking(db: AsyncSession, booking_id: str) -> Booking | None:
    """Load a booking with payment + receipt eagerly to avoid lazy-load errors."""
    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.payment).selectinload(Payment.receipt),
        )
        .where(Booking.booking_id == booking_id)
    )
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=BookingResponse)
async def create_booking(
    data:         BookingCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Create a simulated booking for the given trip."""
    logger.info(
        "[BookingsRoute] POST /bookings/ called - trip_id=%s, place_id=%s, type=%s, cost=%.2f %s, user=%s",
        data.trip_id, data.place_id, data.booking_type.value if data.booking_type else "unknown",
        data.total_cost or 0, data.currency or "USD", current_user.get("uid", "unknown")
    )
    svc = BookingService(db)
    booking = await svc.create_booking(
        trip_id=data.trip_id,
        user_id=current_user["uid"],
        data=data,
    )
    await db.commit()
    booking = await _load_booking(db, booking.booking_id)
    return booking


# ═══════════════════════════════════════════════════════════════════════════════
# GET /trip/{trip_id}
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/trip/{trip_id}", response_model=list[BookingResponse])
async def list_trip_bookings(
    trip_id:      str,
    status:       str | None = None,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """List all bookings for a trip, optionally filtered by status."""
    svc = BookingService(db)
    bookings = await svc.list_trip_bookings(trip_id, status=status)
    bookings = [b for b in bookings if b.user_id == current_user["uid"]]
    return bookings


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{booking_id}/initiate-payment
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{booking_id}/initiate-payment")
async def initiate_booking_payment(
    booking_id:   str,
    data:         PaymentCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Initiate an async Stripe Payment Sheet payment for a booking.

    Creates a PaymentIntent in ``requires_payment_method`` status and returns
    the ``client_secret`` so the Flutter client can open the Stripe Payment
    Sheet for card entry.  The booking is NOT confirmed here — the Stripe
    webhook handler (``payment_intent.succeeded``) will do that.

    This endpoint does NOT confirm the payment or booking synchronously —
    the ``confirm-after-payment`` endpoint does that after the Stripe
    Payment Sheet is completed on the client.

    Returns:
        - client_secret: str (for Payment Sheet initialization)
        - stripe_payment_intent_id: str
        - payment_id: str
        - simulated: bool
        - message: str
    """
    svc = BookingService(db)

    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    # ── Update trip status: enter payment_processing ────────────────────────
    trip_result = await db.execute(
        select(Trip).where(Trip.trip_id == booking.trip_id)
    )
    trip = trip_result.scalar_one_or_none()
    if trip and trip.status in (TripStatus.booking_pending, TripStatus.payment_failed):
        trip.status = TripStatus.payment_processing
        trip.updated_at = None
        await db.commit()

    try:
        result = await svc.initiate_payment(booking_id, data)
    except ValueError as exc:
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.payment_failed
            await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()

    return {
        "success":                      True,
        "payment_id":                   result["payment_id"],
        "client_secret":                result["client_secret"],
        "stripe_payment_intent_id":     result["stripe_payment_intent_id"],
        "simulated":                    result["simulated"],
        "message":                      result["message"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{booking_id}/cancel
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id:   str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Cancel a booking and refund any linked payment."""
    svc = BookingService(db)

    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        await svc.cancel_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    booking = await _load_booking(db, booking_id)
    return booking


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{booking_id}/confirm-after-payment
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{booking_id}/confirm-after-payment")
async def confirm_booking_after_payment(
    booking_id:   str,
    data:         ConfirmAfterPaymentRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Confirm a booking after the client Payment Sheet succeeded.

    The Flutter app calls this after the Stripe Payment Sheet completes.
    The backend verifies the PaymentIntent status with Stripe's API directly
    (server-side verification — doesn't trust the client) and, if confirmed,
    marks the payment complete and confirms the booking immediately.

    This bypasses the need for a Stripe webhook in local development.
    The webhook handler does the same work — whichever arrives first wins
    (idempotent).

    Returns:
        - booking_id: str
        - payment_id: str
        - status: "confirmed" | "already_confirmed"
    """
    svc = BookingService(db)

    # Verify the booking belongs to the current user
    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        result = await svc.confirm_payment_and_booking(
            booking_id=booking_id,
            stripe_payment_intent_id=data.stripe_payment_intent_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    return result


