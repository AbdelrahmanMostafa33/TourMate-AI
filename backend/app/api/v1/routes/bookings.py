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
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.booking import Booking, Payment
from app.models.enums import BookingStatus
from app.schemas.booking import (
    BookingCreate, BookingResponse, BookingStatusUpdate,
    PaymentCreate, TripPackageBookingResponse,
    BulkPaymentRequest, TripPackagePaymentResponse,
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

@router.post("/{booking_id}/pay")
async def pay_booking(
    booking_id:   str,
    data:         PaymentCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Process payment for a booking (Stripe sandbox with simulation fallback)."""
    svc = BookingService(db)

    booking = await _load_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        result = await svc.process_payment(booking_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await svc.confirm_booking(booking_id)
    await db.commit()

    payment = result["payment"]
    receipt = result["receipt"]

    return {
        "success":                    True,
        "payment_id":                 payment.payment_id,
        "stripe_payment_intent_id":   result["stripe_payment_intent_id"],
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

    try:
        result = await svc.pay_trip_package(
            trip_id=trip_id,
            user_id=current_user["uid"],
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    return result