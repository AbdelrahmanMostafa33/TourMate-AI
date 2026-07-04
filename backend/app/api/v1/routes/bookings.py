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

import uuid
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.booking import Booking, Payment
from app.models.enums import (
    TripStatus,
    BookingType,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from app.models.trip import Trip
from app.schemas.booking import (
    BookingCreate, BookingResponse,
    PaymentCreate, ConfirmAfterPaymentRequest,
    CombinedBookInitiateRequest,
    CombinedBookInitiateResponse,
    CombinedBookConfirmRequest,
)
from app.schemas.flight import FlightBookConfirmRequest
from app.services.booking_service import BookingService
from app.services.flight_service import FlightService
from app.services.amadeus_client import amadeus_client

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

@router.post("/", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
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
    if trip and trip.status in (TripStatus.awaiting_booking, TripStatus.booking_pending, TripStatus.payment_failed):
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


# ═══════════════════════════════════════════════════════════════════════════════
# POST /combined/initiate — Single Stripe charge for flight + hotel
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/combined/initiate", response_model=CombinedBookInitiateResponse)
async def combined_initiate_booking(
    data:         CombinedBookInitiateRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Initiate a single Stripe PaymentIntent for flight-only, hotel-only, or both.

    Branches based on what data is provided:
    - ``raw_offer`` present → price flight via Amadeus
    - ``hotel_place_id`` present → create pending hotel booking + Payment record
    - Both present → combine into one PI
    """
    has_flight = data.raw_offer is not None
    has_hotel  = data.hotel_place_id is not None

    logger.info(
        "[BookingsRoute] POST /bookings/combined/initiate — trip=%s, "
        "flight=%s, hotel=%s",
        data.trip_id, has_flight, has_hotel,
    )

    flight_amount = 0.0
    flight_offer = None
    airline_name = None
    flight_number = None
    origin = None
    destination = None
    departure_at = None
    arrival_at = None
    cabin_class = None
    base_currency = "USD"  # fallback if neither flight nor hotel provides it

    # ── 1. Price flight via Amadeus (if raw_offer provided) ────────────────
    if has_flight:
        try:
            priced_offer = amadeus_client.price_flight(data.raw_offer)

            if "flightOffers" in priced_offer:
                flight_offer = priced_offer["flightOffers"][0]
            else:
                flight_offer = priced_offer

            flight_amount = float(flight_offer["price"]["total"])
            base_currency = flight_offer["price"]["currency"]
            segment = flight_offer["itineraries"][0]["segments"][0]
            last_segment = flight_offer["itineraries"][0]["segments"][-1]
            origin = segment["departure"]["iataCode"]
            destination = last_segment["arrival"]["iataCode"]
            departure_at = datetime.fromisoformat(
                segment["departure"]["at"].replace("Z", "+00:00")
            )
            arrival_at = datetime.fromisoformat(
                last_segment["arrival"]["at"].replace("Z", "+00:00")
            )
            airline_code = flight_offer["validatingAirlineCodes"][0]
            flight_number = f"{segment['carrierCode']}{segment['number']}"
            cabin_class = (
                flight_offer["travelerPricings"][0]
                ["fareDetailsBySegment"][0]["cabin"]
            )

            try:
                r = amadeus_client._client.reference_data.airlines.get(
                    airlineCodes=airline_code
                )
                airline_name = r.data[0]["businessName"]
            except Exception:
                airline_name = airline_code
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("[BookingsRoute] Flight pricing failed: %s", exc)
            raise HTTPException(
                status_code=400,
                detail=f"Could not price the selected flight: {exc}",
            )

    # ── 2. Create pending hotel booking (if hotel_place_id provided) ───────
    hotel_booking_id = None
    hotel_amount = 0.0
    hotel_currency = data.hotel_currency or base_currency

    if has_hotel:
        svc = BookingService(db)
        hotel_booking = await svc.create_booking(
            trip_id=data.trip_id,
            user_id=current_user["uid"],
            data=BookingCreate(
                place_id=data.hotel_place_id,
                booking_type=BookingType.hotel,
                total_cost=data.hotel_total_cost,
                currency=hotel_currency,
                start_datetime=data.hotel_start_datetime,
                end_datetime=data.hotel_end_datetime,
            ),
        )
        hotel_booking_id = hotel_booking.booking_id
        hotel_amount = data.hotel_total_cost or 0.0
        base_currency = hotel_currency

    # ── 3. Create Stripe PaymentIntent for the combined total ──────────────
    combined_amount = flight_amount + hotel_amount
    combined_currency = base_currency.lower()

    import stripe
    from app.core.config import settings
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = "2026-06-24.dahlia"

    metadata: dict[str, str] = {
        "trip_id": data.trip_id,
        "mode": "combined",
    }
    if hotel_booking_id:
        metadata["hotel_booking_id"] = hotel_booking_id
    if flight_number:
        metadata["flight_number"] = flight_number
    if origin and destination:
        metadata["origin"] = origin
        metadata["destination"] = destination

    intent = stripe.PaymentIntent.create(
        amount=int(round(combined_amount * 100)),
        currency=combined_currency,
        automatic_payment_methods={"enabled": True},
        metadata=metadata,
    )

    # ── 4. Create pending Payment record for the hotel booking (if any) ────
    if has_hotel:
        payment_id = str(uuid.uuid4())
        payment = Payment(
            payment_id=payment_id,
            booking_id=hotel_booking_id,
            amount=hotel_amount,
            currency=combined_currency.upper(),
            payment_method=PaymentMethod.credit_card,
            provider=PaymentProvider.stripe,
            stripe_payment_intent_id=intent["id"],
            transaction_reference=intent["id"],
            status=PaymentStatus.pending,
            raw_response={
                "combined": True,
                "flight_amount": flight_amount,
                "stripe_payment_intent_id": intent["id"],
                "initiated": True,
            },
        )
        db.add(payment)
        hotel_booking = await db.get(Booking, hotel_booking_id)
        if hotel_booking:
            hotel_booking.payment = payment

    await db.commit()

    logger.info(
        "[BookingsRoute] Combined initiate: flight=%.2f + hotel=%.2f = %.2f %s "
        "(PI=%s)",
        flight_amount, hotel_amount, combined_amount,
        combined_currency.upper(), intent["id"],
    )

    return CombinedBookInitiateResponse(
        client_secret=intent["client_secret"],
        payment_intent_id=intent["id"],
        combined_amount=combined_amount,
        currency=combined_currency.upper(),
        flight_airline_name=airline_name,
        flight_number=flight_number,
        flight_origin_iata=origin,
        flight_destination_iata=destination,
        flight_departure_at=departure_at,
        flight_arrival_at=arrival_at,
        flight_cabin_class=cabin_class,
        flight_amount=flight_amount if has_flight else None,
        hotel_booking_id=hotel_booking_id,
        hotel_amount=hotel_amount if has_hotel else None,
        priced_offer=flight_offer,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /combined/confirm — Finalize both flight + hotel after Stripe success
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/combined/confirm")
async def combined_confirm_booking(
    data:         CombinedBookConfirmRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Confirm after Stripe success — supports flight-only, hotel-only, or both.

    1. Verifies the Stripe PaymentIntent status is ``succeeded``
    2. If ``priced_offer`` provided → books flight via Amadeus
    3. If ``hotel_booking_id`` provided → confirms hotel booking

    If flight fails after payment received, returns 402 with refund message.
    If hotel fails after flight succeeds, returns 402 with refund message.
    """
    has_flight = data.priced_offer is not None
    has_hotel  = data.hotel_booking_id is not None

    logger.info(
        "[BookingsRoute] POST /bookings/combined/confirm — trip=%s, "
        "flight=%s, hotel=%s, PI=%s",
        data.trip_id, has_flight, has_hotel, data.payment_intent_id,
    )

    # ── 1. Verify Stripe PaymentIntent ─────────────────────────────────────
    import stripe
    from app.core.config import settings
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = "2026-06-24.dahlia"

    try:
        intent = stripe.PaymentIntent.retrieve(data.payment_intent_id)
        pi_status = intent.status
    except Exception as exc:
        err_str = str(exc)
        if "No such PaymentIntent" in err_str:
            raise HTTPException(
                status_code=400,
                detail=f"PaymentIntent '{data.payment_intent_id}' not found in Stripe. "
                       "It may have been created in a different environment.",
            )
        logger.error("[BookingsRoute] Stripe verify failed for PI %s: %s",
                     data.payment_intent_id, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Stripe verification failed: {exc}",
        )

    if pi_status != "succeeded":
        raise HTTPException(status_code=400, detail="Payment not completed")

    flight_booking_id = None
    hotel_booking_id = None

    # ── 2. Book flight via Amadeus (if priced_offer provided) ────────────────
    if has_flight:
        flight_svc = FlightService(db)
        flight_confirm_data = FlightBookConfirmRequest(
            payment_intent_id=data.payment_intent_id,
            priced_offer=data.priced_offer,
            trip_id=data.trip_id,
            traveler_first_name=data.traveler_first_name or "",
            traveler_last_name=data.traveler_last_name or "",
            traveler_date_of_birth=data.traveler_date_of_birth or date(1990, 1, 1),
            traveler_gender=data.traveler_gender or "MALE",
            traveler_email=data.traveler_email or "traveler@example.com",
            traveler_phone=data.traveler_phone or "+201000000000",
        )

        try:
            flight_booking = await flight_svc.confirm_flight_booking(
                current_user["uid"], flight_confirm_data,
            )
            flight_booking_id = flight_booking.booking_id
        except ValueError as exc:
            if str(exc) == "PAYMENT_RECEIVED_BOOKING_FAILED":
                detail: dict[str, object] = {
                    "message": "Payment received but flight booking failed.",
                    "refund_status": "simulated_refund",
                    "note": "Flight refund will be processed.",
                }
                if data.hotel_booking_id:
                    detail["hotel_booking_id"] = data.hotel_booking_id
                raise HTTPException(status_code=402, detail=detail)
            raise HTTPException(status_code=400, detail=str(exc))

    # ── 3. Confirm hotel booking (if hotel_booking_id provided) ──────────────
    if has_hotel:
        hotel_svc = BookingService(db)
        try:
            await hotel_svc.confirm_payment_and_booking(
                booking_id=data.hotel_booking_id,
                stripe_payment_intent_id=data.payment_intent_id,
            )
            hotel_booking_id = data.hotel_booking_id
        except ValueError as exc:
            detail: dict[str, object] = {
                "message": "Payment received but hotel confirmation failed.",
                "refund_status": "simulated_refund",
                "note": "Hotel refund will be processed.",
            }
            if flight_booking_id:
                detail["flight_booking_id"] = flight_booking_id
            if data.hotel_booking_id:
                detail["hotel_booking_id"] = data.hotel_booking_id
            raise HTTPException(status_code=402, detail=detail)

    # ── 4. Update trip status ──────────────────────────────────────────────
    trip_result = await db.execute(
        select(Trip).where(Trip.trip_id == data.trip_id)
    )
    trip = trip_result.scalar_one_or_none()
    if trip and trip.status in (TripStatus.awaiting_booking, TripStatus.booking_pending):
        trip.status = TripStatus.booking_confirmed

    await db.commit()

    logger.info(
        "[BookingsRoute] Combined booking confirmed: flight=%s, hotel=%s",
        flight_booking_id, hotel_booking_id,
    )

    return {
        "success": True,
        "flight_booking_id": flight_booking_id,
        "hotel_booking_id": hotel_booking_id,
        "status": "confirmed",
    }


