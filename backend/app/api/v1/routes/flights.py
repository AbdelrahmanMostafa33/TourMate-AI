"""
Flight booking routes — Amadeus flight booking with Stripe payments.

All flight bookings reuse the existing ``Booking`` table with
``booking_type=flight`` and ``provider=amadeus`` — no new tables created.

Endpoints:
  - ``GET    /flights/cities?...``             — City/airport autocomplete (public)
  - ``POST   /flights/smart-search``           — Search by city name (public)
  - ``POST   /flights/search``                 — Search by IATA code (public, enhanced)
  - ``POST   /flights/book/initiate``          — Price raw offer + Stripe PaymentIntent (auth)
  - ``POST   /flights/book/confirm``           — Confirm after Stripe success (auth)
  - ``GET    /flights/trip/{trip_id}/context`` — Get trip context for pre-fill (auth)
  - ``GET    /flights/{booking_id}``           — Get flight booking details (auth)
  - ``GET    /flights/trip/{trip_id}``         — List flight bookings for a trip (auth)
  - ``POST   /flights/{booking_id}/cancel``    — Cancel a flight booking (auth)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.booking import Booking, Payment
from app.models.enums import BookingType
from app.schemas.flight import (
    FlightSearchRequest,
    FlightOfferItem,
    FlightBookingResponse,
    CitySearchResult,
    SmartFlightSearchRequest,
    SmartFlightSearchResponse,
    TripFlightContext,
    FlightBookInitiateRequest,
    FlightBookInitiateResponse,
    FlightBookConfirmRequest,
)
from app.services.flight_service import FlightService

router = APIRouter()


# ── flight routes ───────────────────────────────────────────────────────────

async def _load_flight_booking(
    db: AsyncSession, booking_id: str,
) -> Booking | None:
    """Load a flight booking with payment + receipt eagerly loaded."""
    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.payment).selectinload(Payment.receipt),
        )
        .where(
            Booking.booking_id == booking_id,
            Booking.booking_type == BookingType.flight,
        )
    )
    return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /flights/cities
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/flights/cities", response_model=list[CitySearchResult])
async def search_cities(
    q:   str  = Query(..., min_length=1, description="City or airport name to search for (e.g. 'Cairo', 'Lon')"),
    max: int = Query(10, alias="max", le=50, ge=1, description="Max results"),
    db:  AsyncSession = Depends(get_db),
):
    """Autocomplete cities and airports by keyword (no authentication required).

    Uses the Amadeus reference-data locations API.  Returns matching
    airports and cities with their IATA codes so frontends can build
    auto-complete dropdowns.

    Example:
        ``GET /api/v1/flights/cities?q=Cairo&max=5``
    """
    svc = FlightService(db)
    try:
        results = await svc.search_cities(query=q, max_results=max)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# POST /flights/smart-search
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/flights/smart-search", response_model=SmartFlightSearchResponse)
async def smart_search_flights(
    data: SmartFlightSearchRequest,
    db:   AsyncSession = Depends(get_db),
):
    """Resolve city names to IATA codes + search for flights (no auth required).

    Accepts city names (e.g. ``\"Cairo\"``, ``\"London\"``) instead of raw IATA
    codes.  The server resolves both cities to their airport IATA codes via
    the Amadeus locations API, then searches for flights.

    Returns the resolved city/airport info alongside the flight offers,
    so the frontend can display which airports were matched.
    """
    svc = FlightService(db)
    try:
        result = await svc.smart_search(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /flights/search  (enhanced — now auto-resolves city names)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/flights/search", response_model=list[FlightOfferItem])
async def search_flights(
    data: FlightSearchRequest,
    db:   AsyncSession = Depends(get_db),
):
    """Search for flight offers (no authentication required).

    ``origin`` and ``destination`` accept **either**:
    - A 3-letter IATA code (``\"CAI\"``)
    - A city name (``\"cairo\"``, ``\"london\"``) — the server will
      auto-resolve it to the best-matching IATA code.

    Returns a list of parsed flight offers with pricing and availability.
    """
    svc = FlightService(db)
    try:
        results = await svc.search_flights(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# POST /flights/book/initiate
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/flights/book/initiate", response_model=FlightBookInitiateResponse)
async def initiate_flight_booking(
    data:         FlightBookInitiateRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Initiate a flight booking — price the raw offer + create Stripe PaymentIntent.

    Accepts ``raw_offer`` directly from search results (no separate save-offer
    step needed).  Prices the flight via Amadeus, creates a Stripe
    PaymentIntent with ``automatic_payment_methods``, and returns the
    ``client_secret`` for the Payment Sheet plus the parsed ``priced_offer``
    (Flutter stores this and sends it back in the confirm step).

    Does NOT save anything to the database.
    """
    svc = FlightService(db)
    try:
        result = await svc.initiate_flight_booking(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# POST /flights/book/confirm
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/flights/book/confirm", response_model=FlightBookingResponse)
async def confirm_flight_booking(
    data:         FlightBookConfirmRequest,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Confirm a flight booking after Stripe payment succeeded.

    Verifies the Stripe PaymentIntent status is ``succeeded``, calls Amadeus
    to create the order, then creates Booking + Payment + Receipt records.
    Nothing is saved unless BOTH Stripe and Amadeus succeed.

    If Amadeus booking fails after payment is received, returns a 402 so the
    frontend can inform the user a refund will be processed.
    """
    svc = FlightService(db)
    try:
        booking = await svc.confirm_flight_booking(
            current_user["uid"], data,
        )
    except ValueError as exc:
        if str(exc) == "PAYMENT_RECEIVED_BOOKING_FAILED":
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Payment received but booking failed.",
                    "refund_status": "simulated_refund",
                    "note": "Refund will be processed within 3-5 days.",
                },
            )
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    booking = await _load_flight_booking(db, booking.booking_id)
    return FlightBookingResponse.from_booking(booking)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /flights/trip/{trip_id}/context
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/flights/trip/{trip_id}/context", response_model=TripFlightContext)
async def get_trip_flight_context(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Get pre-filled flight search suggestions from a trip (auth required).

    Reads the trip's destination, dates, and traveler count, then returns
    suggested search parameters.  The frontend can use this to auto-populate
    the flight search form instead of asking the user for every field.

    ``destination_iata`` is resolved automatically if possible.
    """
    svc = FlightService(db)
    try:
        context = await svc.get_trip_context(trip_id, current_user["uid"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return context



# ═══════════════════════════════════════════════════════════════════════════════
# GET /flights/{booking_id}
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/flights/{booking_id}", response_model=FlightBookingResponse)
async def get_flight_booking(
    booking_id:   str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Get full details for a single flight booking."""
    booking = await _load_flight_booking(db, booking_id)
    if not booking or booking.user_id != current_user["uid"]:
        raise HTTPException(status_code=404, detail="Flight booking not found")
    return FlightBookingResponse.from_booking(booking)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /flights/trip/{trip_id}
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/flights/trip/{trip_id}", response_model=list[FlightBookingResponse])
async def list_trip_flight_bookings(
    trip_id:      str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """List all flight bookings for a trip, ordered newest first."""
    svc = FlightService(db)
    bookings = await svc.list_trip_flight_bookings(trip_id)
    bookings = [b for b in bookings if b.user_id == current_user["uid"]]
    return [FlightBookingResponse.from_booking(b) for b in bookings]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /flights/{booking_id}/cancel
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/flights/{booking_id}/cancel", response_model=FlightBookingResponse)
async def cancel_flight_booking(
    booking_id:   str,
    current_user: dict         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db),
):
    """Cancel a flight booking."""
    svc = FlightService(db)

    try:
        booking = await svc.cancel_flight_booking(booking_id, current_user["uid"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()

    booking = await _load_flight_booking(db, booking_id)
    return FlightBookingResponse.from_booking(booking)
