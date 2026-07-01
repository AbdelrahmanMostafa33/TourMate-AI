"""
Booking routes — Hybrid booking system.

Provides a full CRUD + lifecycle API for the Booking → Payment → Receipt
pipeline.  Booking confirmations are simulated (no real hotel/restaurant API),
while payments are processed through Stripe sandbox (test mode) with a
simulated fallback.

Endpoints:
  - ``POST   /``                          — Create a booking
  - ``GET    /{booking_id}``              — Get booking details
  - ``GET    /trip/{trip_id}``            — List bookings for a trip
  - ``PATCH  /{booking_id}/status``       — Update booking status
  - ``POST   /{booking_id}/pay``          — Process payment (Stripe sandbox)
  - ``POST   /{booking_id}/cancel``       — Cancel a booking
  - ``POST   /{booking_id}/complete``     — Mark booking as completed
  - ``POST   /trip/{trip_id}/package``    — Book all stops in the trip
  - ``POST   /trip/{trip_id}/pay-all``    — Pay all pending bookings in a trip
  - ``POST   /trip/{trip_id}/initiate-pay-all`` — Initiate async payment for all pending bookings
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
from app.models.enums import BookingStatus, TripStatus
from app.models.trip import Trip
from app.schemas.booking import (
    BookingCreate, BookingResponse, BookingStatusUpdate,
    PaymentCreate, TripPackageBookingResponse,
    BulkPaymentRequest, TripPackagePaymentResponse,
    HotelBookRequest, ConfirmAfterPaymentRequest,
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
# GET /{booking_id}
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id:   str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Get full details for a single booking, including payment + receipt."""
    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")
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
    status_enum = None
    if status:
        try:
            status_enum = BookingStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in BookingStatus]}",
            )

    svc = BookingService(db)
    bookings = await svc.list_trip_bookings(trip_id, status=status_enum)
    bookings = [b for b in bookings if b.user_id == current_user["uid"]]
    return bookings


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /{booking_id}/status
# ═══════════════════════════════════════════════════════════════════════════════

@router.patch("/{booking_id}/status", response_model=BookingResponse)
async def update_booking_status(
    booking_id:   str,
    body:         BookingStatusUpdate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Manually update the status of a booking."""
    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.status = body.status
    booking.raw_response = {
        **(booking.raw_response or {}),
        f"status_changed_to_{body.status.value}_at": None,
    }
    await db.commit()
    booking = await _load_booking(db, booking_id)
    return booking


# ═══════════════════════════════════════════════════════════════════════════════
# POST /{booking_id}/pay
# ═══════════════════════════════════════════════════════════════════════════════

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

    Unlike ``POST /{booking_id}/pay``, this endpoint does NOT confirm the
    payment or booking synchronously.  This is the correct endpoint for the
    async Stripe Payment Sheet flow.

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
# POST /{booking_id}/pay
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{booking_id}/pay")
async def pay_booking(
    booking_id:   str,
    data:         PaymentCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Process payment for a booking (Stripe sandbox with simulation fallback).

    Trip status transitions:
      booking_pending → payment_processing → booking_confirmed  (all paid)
      booking_pending → payment_processing → booking_pending    (more unpaid)
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
        trip.updated_at = None  # trigger onupdate
        await db.commit()  # persist so Flutter/Stripe sees the processing state

    # ── Process payment ─────────────────────────────────────────────────────
    try:
        result = await svc.process_payment(booking_id, data)
    except ValueError as exc:
        # Revert to payment_failed so the user can retry
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.payment_failed
            await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    await svc.confirm_booking(booking_id)

    # ── After payment: check if all bookings are now paid ────────────────────
    if trip and trip.status == TripStatus.payment_processing:
        remaining_pending = await svc.list_trip_bookings(
            booking.trip_id, status=BookingStatus.pending
        )
        if not remaining_pending:
            trip.status = TripStatus.booking_confirmed
            logger.info(
                "[BookingsRoute] All bookings paid for trip %s → booking_confirmed",
                booking.trip_id,
            )
        else:
            trip.status = TripStatus.booking_pending
            logger.info(
                "[BookingsRoute] Booking %s paid, %d still pending for trip %s",
                booking_id, len(remaining_pending), booking.trip_id,
            )

    await db.commit()

    payment = result["payment"]
    receipt = result["receipt"]

    # Extract client_secret for Stripe Payment Sheet async flow
    client_secret = (payment.raw_response or {}).get("client_secret")

    return {
        "success":                    True,
        "payment_id":                 payment.payment_id,
        "stripe_payment_intent_id":   result["stripe_payment_intent_id"],
        "client_secret":              client_secret,
        "amount":                     payment.amount,
        "currency":                   payment.currency,
        "receipt_number":             receipt.receipt_number,
        "receipt_id":                 receipt.receipt_id,
        "total_charged":              receipt.total,
        "simulated":                  payment.raw_response.get("simulated", False),
        "message":                    result["message"],
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
# POST /{booking_id}/complete
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/{booking_id}/complete", response_model=BookingResponse)
async def complete_booking(
    booking_id:   str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Mark a confirmed booking as completed (post-visit)."""
    svc = BookingService(db)

    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        await svc.complete_booking(booking_id)
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


# ═══════════════════════════════════════════════════════════════════════════════
# POST /hotel-book — Single hotel booking (create + pay + confirm)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/hotel-book", response_model=BookingResponse)
async def book_hotel(
    data:         HotelBookRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Create, pay, and confirm a single hotel booking in one call.

    Used by the Pay Now flow when a user has selected a specific hotel.
    Creates a pending booking, processes payment (sandbox), and confirms it.
    Unlike ``book_trip_package``, this only books ONE hotel — not all stops.
    """
    logger.info(
        "[BookingsRoute] /hotel-book called - trip_id=%s, place_id=%s, cost=%.2f %s, user=%s",
        data.trip_id, data.place_id, data.total_cost, data.currency or "USD", current_user.get("uid", "unknown")
    )
    svc = BookingService(db)

    # ── 1. Create booking ─────────────────────────────────────────────
    booking_create = BookingCreate(
        trip_id=data.trip_id,
        place_id=data.place_id,
        booking_type=BookingType.hotel,
        total_cost=data.total_cost,
        currency=data.currency or "USD",
        start_datetime=data.start_datetime,
        end_datetime=data.end_datetime,
    )
    booking = await svc.create_booking(
        trip_id=data.trip_id,
        user_id=current_user["uid"],
        data=booking_create,
    )

    # ── 2. Process payment ────────────────────────────────────────────
    payment_data = PaymentCreate(
        amount=data.total_cost,
        currency=data.currency or "USD",
        payment_method=PaymentMethod.credit_card,
    )
    await svc.process_payment(booking.booking_id, payment_data)

    # ── 3. Confirm booking ────────────────────────────────────────────
    await svc.confirm_booking(booking.booking_id)

    await db.commit()

    booking = await _load_booking(db, booking.booking_id)
    logger.info(
        "[BookingsRoute] Single hotel booked: %s for trip %s (cost=%.2f %s)",
        booking.booking_id, data.trip_id, data.total_cost, data.currency or "USD",
    )
    return booking


# ═══════════════════════════════════════════════════════════════════════════════
# POST /trip/{trip_id}/package
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/trip/{trip_id}/package", response_model=TripPackageBookingResponse)
async def book_trip_package(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Book every stop in the trip's itinerary as a package."""
    svc = BookingService(db)

    try:
        result = await svc.book_trip_package(
            trip_id=trip_id,
            user_id=current_user["uid"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # ── Update trip status to booking_pending ────────────────────────────────
    trip_result = await db.execute(
        select(Trip).where(Trip.trip_id == trip_id)
    )
    trip = trip_result.scalar_one_or_none()
    if trip and trip.status == TripStatus.awaiting_booking:
        trip.status = TripStatus.booking_pending
        trip.updated_at = None  # trigger onupdate

    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /trip/{trip_id}/initiate-pay-all
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/trip/{trip_id}/initiate-pay-all")
async def initiate_trip_package_payment(
    trip_id:      str,
    data:         BulkPaymentRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Initiate async Stripe Payment Sheet payments for all pending bookings.

    Creates a Stripe PaymentIntent in ``requires_payment_method`` status for
    each pending booking and returns ``client_secret`` values so the Flutter
    client can open the Stripe Payment Sheet for each one.

    Unlike ``POST /trip/{trip_id}/pay-all``, this endpoint does NOT confirm
    any payment or booking synchronously — the Stripe webhook handlers
    (``payment_intent.succeeded``) will do that.

    The trip status transitions to ``payment_processing`` while initiations
    are in progress.  It stays in ``payment_processing`` after completion
    because the async Payment Sheet flow hasn't finished yet.

    Accepts a shared body (``payment_method``, optional ``currency``) that is
    applied to each pending booking.  The per-booking ``amount`` is taken from
    each booking's ``total_cost``.

    - Pending bookings have payments initiated.
    - Non-pending bookings are silently skipped with a reason.
    - If initiation fails for an individual booking, processing continues.
    """
    svc = BookingService(db)

    # ── Enter payment_processing ───────────────────────────────────────────
    trip_result = await db.execute(
        select(Trip).where(Trip.trip_id == trip_id)
    )
    trip = trip_result.scalar_one_or_none()
    if trip and trip.status == TripStatus.booking_pending:
        trip.status = TripStatus.payment_processing
        trip.updated_at = None
        await db.commit()

    try:
        result = await svc.initiate_trip_package(
            trip_id=trip_id,
            user_id=current_user["uid"],
            data=data,
        )
    except ValueError as exc:
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.booking_pending
            await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /trip/{trip_id}/pay-all
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/trip/{trip_id}/pay-all", response_model=TripPackagePaymentResponse)
async def pay_trip_package(
    trip_id:      str,
    data:         BulkPaymentRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Pay for all pending bookings in a trip at once.

    Accepts a shared body (``payment_method``, optional ``currency``) that is
    applied to each pending booking.  The per-booking ``amount`` is taken from
    each booking's ``total_cost``.

    - Pending bookings are paid and confirmed.
    - Non-pending bookings (confirmed, cancelled, completed) are silently
      skipped with a reason in the response.
    - If a payment fails for an individual booking, processing continues with
      the next one.
    """
    svc = BookingService(db)

    # ── Enter payment_processing before processing payments ───────────────────
    trip_result = await db.execute(
        select(Trip).where(Trip.trip_id == trip_id)
    )
    trip = trip_result.scalar_one_or_none()
    if trip and trip.status == TripStatus.booking_pending:
        trip.status = TripStatus.payment_processing
        trip.updated_at = None  # trigger onupdate
        await db.commit()  # persist so Flutter/Stripe sees the processing state

    try:
        result = await svc.pay_trip_package(
            trip_id=trip_id,
            user_id=current_user["uid"],
            data=data,
        )
    except ValueError as exc:
        # Revert to booking_pending so the user can retry
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.booking_pending
            await db.commit()
        raise HTTPException(status_code=400, detail=str(exc))

    # ── Update trip status based on payment results ───────────────────────────
    if result.get("paid_count", 0) > 0:
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.booking_confirmed
            trip.updated_at = None  # trigger onupdate
            logger.info(
                "[BookingsRoute] Bulk pay for trip %s → booking_confirmed (%d paid)",
                trip_id, result["paid_count"],
            )
    else:
        # Nothing was paid (all skipped) — revert from payment_processing
        if trip and trip.status == TripStatus.payment_processing:
            trip.status = TripStatus.booking_pending
            trip.updated_at = None
            logger.info(
                "[BookingsRoute] Bulk pay for trip %s — no bookings paid, reverted to booking_pending",
                trip_id,
            )

    await db.commit()
    return result