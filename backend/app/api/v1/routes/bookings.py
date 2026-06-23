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
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.enums import BookingStatus
from app.schemas.booking import (
    BookingCreate, BookingResponse, BookingStatusUpdate,
    PaymentCreate, TripPackageBookingResponse,
)
from app.services.booking_service import BookingService

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# POST /
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/", response_model=BookingResponse)
async def create_booking(
    data:         BookingCreate,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Create a simulated booking for the given trip.

    The booking starts in **pending** status.  Use ``/{booking_id}/pay`` to
    process payment (Stripe sandbox) which will auto-confirm the booking.
    """
    svc = BookingService(db)
    booking = await svc.create_booking(
        trip_id=data.trip_id,
        user_id=current_user["uid"],
        data=data,
    )
    await db.commit()
    await db.refresh(booking)
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
    svc = BookingService(db)
    booking = await svc.get_booking(booking_id)
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

    # Security: only return bookings that belong to the current user
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
    """Manually update the status of a booking.

    Use this as a low-level override.  Prefer the dedicated endpoints
    ``/cancel`` and ``/complete`` for standard lifecycle transitions.
    """
    svc = BookingService(db)
    booking = await svc.get_booking(booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking.status = body.status
    booking.raw_response = {
        **(booking.raw_response or {}),
        f"status_changed_to_{body.status.value}_at": None,  # will be set by DB onupdate
    }
    await db.commit()
    await db.refresh(booking)
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
    """Process payment for a booking (Stripe sandbox with simulation fallback).

    Uses Stripe test mode if ``STRIPE_SECRET_KEY`` is configured, otherwise
    falls back to a fully simulated payment.  On success, creates a
    ``Payment`` and ``Receipt`` record and transitions the booking to
    **confirmed**.

    Request body example (sandbox mode — test token is automatic)::

        {
          "amount": 150.00,
          "currency": "USD",
          "payment_method": "credit_card"
        }

    Returns payment details including ``stripe_payment_intent_id`` and the
    generated ``receipt_number``.
    """
    svc = BookingService(db)

    # Security: verify ownership first
    booking = await svc.get_booking(booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        result = await svc.process_payment(booking_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Auto-confirm booking after successful payment
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

    # Security: verify ownership first
    booking = await svc.get_booking(booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        booking = await svc.cancel_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    await db.refresh(booking)
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

    # Security: verify ownership first
    booking = await svc.get_booking(booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Booking not found")

    try:
        booking = await svc.complete_booking(booking_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    await db.refresh(booking)
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
    """Book every stop in the trip's itinerary as a package.

    Creates individual ``Booking`` records (status = pending) for each stop
    in the latest itinerary version.  Stops are mapped to booking types:

    - hotels → ``hotel``
    - restaurants → ``restaurant``
    - attractions / activities → ``activity``

    All bookings are created in ``pending`` status.  Use the individual
    ``/{booking_id}/pay`` endpoint to pay for each, or use ``/pay-all``
    for a single bulk payment.

    Returns a summary with total cost, booking count, and the list of
    created bookings with their confirmation numbers.
    """
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
