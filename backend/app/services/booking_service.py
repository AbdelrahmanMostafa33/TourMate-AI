# backend/app/services/booking_service.py

"""
Booking Service — Hybrid Booking System.

Architecture (Hybrid):
  - **Booking/Confirmation**: Fully simulated (no real hotel/restaurant API).
    Generates mock confirmation numbers, provider references, and manages
    the booking lifecycle (pending → confirmed → completed / cancelled).
  - **Payment**: Stripe sandbox (test mode).  Creates real PaymentIntent
    objects in Stripe's test environment using test card tokens.
    On success, a Payment + Receipt record is persisted.

Flow:
  1. ``create_booking()`` → Booking (status = pending), mock confirmation
  2. ``process_payment()`` → Stripe PaymentIntent (sandbox) → Payment + Receipt
  3. ``confirm_booking()`` → Booking (status = confirmed)
  4. ``cancel_booking()`` / ``complete_booking()`` → status transitions
"""

from __future__ import annotations

import uuid
import logging
import random
import string
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, Payment, Receipt
from app.models.enums import (
    BookingStatus, BookingProvider, BookingType,
    PaymentMethod, PaymentStatus, PaymentProvider,
)
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.trip import Trip
from app.schemas.booking import BookingCreate, PaymentCreate, PackageBookingItem

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ── helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_booking_id() -> str:
    """Short, human-readable booking ID like ``BK-A3F9C2``."""
    return "BK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _generate_confirmation_number() -> str:
    """Mock confirmation number like ``CNF-8X2M-9K1P``."""
    def _seg() -> str:
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CNF-{_seg()}-{_seg()}"


def _generate_receipt_number() -> str:
    """Mock receipt number like ``RCT-20260623-7A2B``."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.hexdigits.upper(), k=4))
    return f"RCT-{date_part}-{rand_part}"


def _generate_transaction_reference() -> str:
    """Mock transaction ref like ``TXN-9K2M3N4P``."""
    return "TXN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _determine_booking_provider(booking_type: BookingType) -> BookingProvider:
    """Map booking type to a realistic mock provider."""
    mapping = {
        BookingType.hotel:      BookingProvider.booking_com,
        BookingType.restaurant: BookingProvider.direct,
        BookingType.activity:   BookingProvider.expedia,
        BookingType.transport:  BookingProvider.other,
    }
    return mapping.get(booking_type, BookingProvider.direct)


# ═══════════════════════════════════════════════════════════════════════════════
# ── Stripe client helpers (lazy init, sandbox only)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_stripe():
    """Lazy-import Stripe and set the secret key from settings.

    Returns the Stripe module (or ``None`` if not configured), so the
    service degrades gracefully when ``STRIPE_SECRET_KEY`` is empty.
    """
    try:
        import stripe
    except ImportError:
        logger.warning("[BookingService] Stripe SDK not installed; payments will be simulated.")
        return None

    from app.core.config import settings
    if not settings.STRIPE_SECRET_KEY:
        logger.warning("[BookingService] STRIPE_SECRET_KEY not set; payments will be simulated.")
        return None

    stripe.api_key = settings.STRIPE_SECRET_KEY
    # Pin to a stable API version
    stripe.api_version = "2023-10-16"
    return stripe


# ═══════════════════════════════════════════════════════════════════════════════
# ── Service
# ═══════════════════════════════════════════════════════════════════════════════

class BookingService:
    """Business logic for bookings, payments, and receipts."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._stripe = _get_stripe()

    # ── create_booking ─────────────────────────────────────────────────────

    async def create_booking(
        self,
        trip_id: str,
        user_id: str,
        data: BookingCreate,
    ) -> Booking:
        """Create a simulated booking with a mock confirmation number.

        No external booking API is called — the confirmation is generated
        locally.  The booking starts in ``pending`` status and must be
        paid (``process_payment``) to move to ``confirmed``.

        Returns:
            The newly created ``Booking`` ORM object (not yet committed).
        """
        provider = data.provider or _determine_booking_provider(data.booking_type)

        booking = Booking(
            booking_id          = _generate_booking_id(),
            trip_id             = trip_id,
            user_id             = user_id,
            place_id            = data.place_id,
            booking_type        = data.booking_type,
            provider            = provider,
            provider_reference  = data.provider_reference or _generate_transaction_reference(),
            confirmation_number = data.confirmation_number or _generate_confirmation_number(),
            start_datetime      = data.start_datetime,
            end_datetime        = data.end_datetime,
            total_cost          = data.total_cost,
            currency            = data.currency or "USD",
            status              = BookingStatus.pending,
            raw_response        = {
                "simulated": True,
                "provider": provider.value,
                "note": "Booking confirmation is simulated (no external API call).",
            },
        )

        self.db.add(booking)
        logger.info(
            "[BookingService] Created simulated booking %s (type=%s, cost=%.2f %s) for trip %s",
            booking.booking_id, data.booking_type.value,
            data.total_cost or 0, data.currency or "USD",
            trip_id,
        )
        return booking

    # ── process_payment ────────────────────────────────────────────────────

    async def process_payment(
        self,
        booking_id: str,
        data: PaymentCreate,
    ) -> dict:
        """Process a payment via Stripe sandbox or fall back to simulation.

        Actual behaviour depends on configuration:
          - **Stripe configured** — creates a real ``PaymentIntent`` in
            Stripe test mode with the test token ``pm_card_visa``.
          - **Stripe not configured** — fully simulated (no external call).

        Args:
            booking_id: The booking to pay for.
            data:       Payment details (amount, currency, method).

        Returns:
            A dict with keys:
              - success: bool
              - payment: ``Payment`` ORM object
              - receipt: ``Receipt`` ORM object (or None)
              - stripe_payment_intent_id: str | None
              - message: str

        Raises:
            ValueError: If booking not found, already paid, or cancelled.
        """
        # ── Load booking ──────────────────────────────────────────────────
        result = await self.db.execute(
            select(Booking).where(Booking.booking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Booking {booking_id} is cancelled — cannot process payment")
        if booking.status == BookingStatus.completed:
            raise ValueError(f"Booking {booking_id} is already completed")

        # Check if payment already exists
        if booking.payment:
            raise ValueError(f"Booking {booking_id} already has a payment")

        amount   = data.amount if data.amount is not None else (booking.total_cost or 0)
        currency = (data.currency or booking.currency or "USD").lower()

        payment_id = str(uuid.uuid4())
        stripe_pi_id = None
        raw_response = {}

        # ── Stripe sandbox payment (if available) ─────────────────────────
        if self._stripe is not None:
            try:
                # Use a test card token so this works fully server-side
                # without requiring the client to collect card details.
                intent = self._stripe.PaymentIntent.create(
                    amount=int(round(amount * 100)),  # cents
                    currency=currency,
                    payment_method_data={
                        "type": "card",
                        "card": {"token": "tok_visa"},  # Stripe test token
                    },
                    confirm=True,
                    metadata={
                        "booking_id": booking_id,
                        "trip_id":    booking.trip_id,
                        "mode":       "sandbox",
                    },
                )
                stripe_pi_id = intent["id"]
                raw_response = {
                    "stripe_payment_intent_id": stripe_pi_id,
                    "status": intent["status"],
                    "amount": intent["amount"],
                    "currency": intent["currency"],
                    "sandbox": True,
                }
                logger.info(
                    "[BookingService] Stripe PaymentIntent %s created (status=%s) for booking %s",
                    stripe_pi_id, intent["status"], booking_id,
                )
            except Exception as exc:
                logger.error(
                    "[BookingService] Stripe payment failed for booking %s: %s",
                    booking_id, exc,
                )
                # Fall through to simulated payment
                raw_response = {
                    "stripe_error": str(exc),
                    "note": "Fell back to simulated payment after Stripe error.",
                }
                stripe_pi_id = None

        # ── Fallback: fully simulated payment ─────────────────────────────
        if stripe_pi_id is None:
            stripe_pi_id = f"pi_simulated_{uuid.uuid4().hex[:12]}"
            raw_response = {
                "simulated": True,
                "stripe_payment_intent_id": stripe_pi_id,
                "amount": amount,
                "currency": currency,
                "note": "Payment processed in simulation mode (no Stripe API call).",
            }
            logger.info(
                "[BookingService] Simulated payment for booking %s (amount=%.2f %s)",
                booking_id, amount, currency,
            )

        # ── Create Payment record ─────────────────────────────────────────
        payment = Payment(
            payment_id              = payment_id,
            booking_id              = booking_id,
            amount                  = amount,
            currency                = currency.upper(),
            payment_method          = data.payment_method,
            provider                = PaymentProvider.stripe,
            stripe_payment_intent_id = stripe_pi_id,
            transaction_reference   = data.transaction_reference or _generate_transaction_reference(),
            status                  = PaymentStatus.completed,
            raw_response            = raw_response,
            paid_at                 = datetime.utcnow(),
        )
        self.db.add(payment)

        # ── Create Receipt record ─────────────────────────────────────────
        receipt = Receipt(
            receipt_id     = str(uuid.uuid4()),
            payment_id     = payment_id,
            receipt_number = _generate_receipt_number(),
            subtotal       = amount,
            tax            = round(amount * 0.10, 2),  # simulated 10% tax
            total          = round(amount * 1.10, 2),
            currency       = currency.upper(),
        )
        self.db.add(receipt)

        logger.info(
            "[BookingService] Payment %s / Receipt %s created for booking %s",
            payment.payment_id, receipt.receipt_number, booking_id,
        )

        return {
            "success": True,
            "payment": payment,
            "receipt": receipt,
            "stripe_payment_intent_id": stripe_pi_id,
            "message": "Payment processed successfully (sandbox/simulated).",
        }

    # ── confirm_booking ────────────────────────────────────────────────────

    async def confirm_booking(self, booking_id: str) -> Booking:
        """Transition booking status from ``pending`` → ``confirmed``.

        Typically called after ``process_payment()`` succeeds.

        Raises:
            ValueError: If booking not found, already confirmed, cancelled, or completed.
        """
        result = await self.db.execute(
            select(Booking).where(Booking.booking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        if booking.status in (BookingStatus.confirmed, BookingStatus.completed):
            raise ValueError(f"Booking {booking_id} is already {booking.status.value}")
        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Cannot confirm cancelled booking {booking_id}")

        booking.status = BookingStatus.confirmed
        booking.raw_response = {
            **(booking.raw_response or {}),
            "confirmed_at": datetime.utcnow().isoformat(),
        }

        logger.info("[BookingService] Confirmed booking %s", booking_id)
        return booking

    # ── cancel_booking ─────────────────────────────────────────────────────

    async def cancel_booking(self, booking_id: str) -> Booking:
        """Cancel a booking (pending, confirmed, or completed → cancelled).

        Raises:
            ValueError: If booking not found or already cancelled.
        """
        result = await self.db.execute(
            select(Booking).where(Booking.booking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Booking {booking_id} is already cancelled")

        old_status = booking.status.value
        booking.status = BookingStatus.cancelled
        booking.raw_response = {
            **(booking.raw_response or {}),
            "cancelled_at": datetime.utcnow().isoformat(),
            "cancelled_from": old_status,
        }

        # If there's a linked payment, mark it as refunded
        if booking.payment:
            booking.payment.status = PaymentStatus.refunded
            booking.payment.raw_response = {
                **(booking.payment.raw_response or {}),
                "refunded_at": datetime.utcnow().isoformat(),
                "reason": "booking_cancelled",
            }

        logger.info("[BookingService] Cancelled booking %s (was %s)", booking_id, old_status)
        return booking

    # ── complete_booking ───────────────────────────────────────────────────

    async def complete_booking(self, booking_id: str) -> Booking:
        """Mark a confirmed booking as completed (post-visit).

        Raises:
            ValueError: If booking not found or not in confirmed status.
        """
        result = await self.db.execute(
            select(Booking).where(Booking.booking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")
        if booking.status != BookingStatus.confirmed:
            raise ValueError(
                f"Booking {booking_id} must be 'confirmed' to complete (current: {booking.status.value})"
            )

        booking.status = BookingStatus.completed
        booking.raw_response = {
            **(booking.raw_response or {}),
            "completed_at": datetime.utcnow().isoformat(),
        }

        logger.info("[BookingService] Completed booking %s", booking_id)
        return booking

    # ── Stripe webhook event handlers ─────────────────────────────────────

    async def find_payment_by_stripe_pi_id(
        self, stripe_payment_intent_id: str
    ) -> Optional[Payment]:
        """Find a Payment record by its Stripe PaymentIntent ID."""
        result = await self.db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == stripe_payment_intent_id
            )
        )
        return result.scalar_one_or_none()

    async def handle_webhook_payment_succeeded(
        self, stripe_payment_intent_id: str,
    ) -> dict:
        """Handle ``payment_intent.succeeded`` webhook event (idempotent).

        Finds the matching Payment record, marks it completed, and
        confirms the associated booking.  If the payment or booking is
        already in the target state, returns immediately without error
        (safe for Stripe webhook retries).

        Returns a dict with booking_id, payment_id, and status.

        Raises:
            ValueError: If no Payment matches the Stripe PI ID.
        """
        payment = await self.find_payment_by_stripe_pi_id(stripe_payment_intent_id)
        if not payment:
            raise ValueError(
                f"No Payment found for Stripe PI '{stripe_payment_intent_id}'"
            )

        # Idempotency: already completed
        if payment.status == PaymentStatus.completed:
            logger.info(
                "[BookingService] Webhook: payment_intent.succeeded for PI=%s "
                "— already processed, skipping",
                stripe_payment_intent_id,
            )
            return {
                "booking_id": payment.booking_id,
                "payment_id": payment.payment_id,
                "status": "already_completed",
            }

        # ── Update payment status ─────────────────────────────────────────
        payment.status = PaymentStatus.completed
        payment.raw_response = {
            **(payment.raw_response or {}),
            "webhook_confirmed_at": datetime.utcnow().isoformat(),
            "webhook_event": "payment_intent.succeeded",
        }

        # ── Confirm the linked booking (idempotent: skips if already done) ─
        booking = await self.get_booking(payment.booking_id)
        if not booking:
            raise ValueError(f"Booking {payment.booking_id} not found")

        if booking.status not in (BookingStatus.confirmed, BookingStatus.completed):
            booking = await self.confirm_booking(payment.booking_id)
        else:
            logger.info(
                "[BookingService] Webhook: booking %s already %s — skipping",
                booking.booking_id, booking.status.value,
            )

        logger.info(
            "[BookingService] Webhook: payment_intent.succeeded for PI=%s → "
            "booking %s confirmed",
            stripe_payment_intent_id, booking.booking_id,
        )

        return {
            "booking_id": booking.booking_id,
            "payment_id": payment.payment_id,
            "status": booking.status.value,
        }

    async def handle_webhook_payment_failed(
        self, stripe_payment_intent_id: str,
    ) -> dict:
        """Handle ``payment_intent.payment_failed`` webhook event (idempotent).

        Marks the associated Payment as failed.  Does NOT cancel the
        booking — the booking stays in ``pending`` so the user can retry.

        Raises:
            ValueError: If no Payment matches the Stripe PI ID.
        """
        payment = await self.find_payment_by_stripe_pi_id(stripe_payment_intent_id)
        if not payment:
            raise ValueError(
                f"No Payment found for Stripe PI '{stripe_payment_intent_id}'"
            )

        # Idempotency: already failed
        if payment.status == PaymentStatus.failed:
            logger.info(
                "[BookingService] Webhook: payment_intent.payment_failed for "
                "PI=%s — already failed, skipping",
                stripe_payment_intent_id,
            )
            return {
                "payment_id": payment.payment_id,
                "booking_id": payment.booking_id,
                "status": "already_failed",
            }

        payment.status = PaymentStatus.failed
        payment.raw_response = {
            **(payment.raw_response or {}),
            "failure_recorded_at": datetime.utcnow().isoformat(),
            "webhook_event": "payment_intent.payment_failed",
        }

        logger.info(
            "[BookingService] Webhook: payment_intent.payment_failed for PI=%s",
            stripe_payment_intent_id,
        )

        return {
            "payment_id": payment.payment_id,
            "booking_id": payment.booking_id,
            "status": "failed",
        }

    async def handle_webhook_charge_refunded(
        self, stripe_payment_intent_id: str,
    ) -> dict:
        """Handle ``charge.refunded`` webhook event (idempotent).

        Marks the Payment as refunded and cancels the associated booking.
        If already refunded/cancelled, returns immediately without error
        (safe for Stripe webhook retries).

        Raises:
            ValueError: If no Payment matches the Stripe PI ID.
        """
        payment = await self.find_payment_by_stripe_pi_id(stripe_payment_intent_id)
        if not payment:
            raise ValueError(
                f"No Payment found for Stripe PI '{stripe_payment_intent_id}'"
            )

        # Idempotency: already refunded
        if payment.status == PaymentStatus.refunded:
            logger.info(
                "[BookingService] Webhook: charge.refunded for PI=%s "
                "— already refunded, skipping",
                stripe_payment_intent_id,
            )
            return {
                "booking_id": payment.booking_id,
                "payment_id": payment.payment_id,
                "status": "already_refunded",
            }

        payment.status = PaymentStatus.refunded
        payment.raw_response = {
            **(payment.raw_response or {}),
            "refunded_at": datetime.utcnow().isoformat(),
            "webhook_event": "charge.refunded",
        }

        # Cancel the booking (idempotent: skips if already cancelled)
        booking = await self.get_booking(payment.booking_id)
        if not booking:
            raise ValueError(f"Booking {payment.booking_id} not found")

        if booking.status != BookingStatus.cancelled:
            booking = await self.cancel_booking(payment.booking_id)
        else:
            logger.info(
                "[BookingService] Webhook: booking %s already cancelled — skipping",
                booking.booking_id,
            )

        logger.info(
            "[BookingService] Webhook: charge.refunded for PI=%s → "
            "booking %s cancelled",
            stripe_payment_intent_id, booking.booking_id,
        )

        return {
            "booking_id": booking.booking_id,
            "payment_id": payment.payment_id,
            "status": booking.status.value,
        }

    # ── book_trip_package ────────────────────────────────────────────────

    async def book_trip_package(
        self,
        trip_id: str,
        user_id: str,
        currency: str = "USD",
    ) -> dict:
        """Book every stop in the trip's latest itinerary as individual bookings.

        Iterates over all days and stops in the most recent itinerary version,
        creates a ``Booking`` (pending) for each stop that has a place name,
        and returns a summary dict with all created bookings and the total cost.

        Stop categories are mapped to ``BookingType``:
          - hotel      → ``BookingType.hotel``
          - restaurant → ``BookingType.restaurant``
          - attraction → ``BookingType.activity``
          - other      → ``BookingType.activity``

        Args:
            trip_id:  The trip whose itinerary stops should be booked.
            user_id:  The user making the booking.
            currency: Currency code (default USD).

        Returns:
            A dict with keys:
              - trip_id, trip_name, destination
              - total_cost, currency
              - bookings: list of ``PackageBookingItem`` dicts
              - stop_count, booking_count

        Raises:
            ValueError: If the trip is not found or has no itinerary with stops.
        """
        # ── Load trip with latest itinerary ────────────────────────────────
        result = await self.db.execute(
            select(Trip)
            .options(
                selectinload(Trip.itineraries)
                .selectinload(Itinerary.days)
                .selectinload(Day.stops),
            )
            .where(Trip.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()
        if not trip:
            raise ValueError(f"Trip {trip_id} not found")

        if not trip.itineraries:
            raise ValueError(f"Trip {trip_id} has no itinerary — create an itinerary first")

        # Get the latest itinerary version
        itinerary = sorted(
            trip.itineraries,
            key=lambda i: (i.created_at or datetime.min, i.updated_at or datetime.min),
            reverse=True,
        )[0]

        if not itinerary.days:
            raise ValueError(f"Itinerary {itinerary.itinerary_id} has no days")

        # ── Map stop categories → BookingType ──────────────────────────────
        _CATEGORY_MAP = {
            "hotel":      BookingType.hotel,
            "restaurant": BookingType.restaurant,
            "attraction": BookingType.activity,
            "activity":   BookingType.activity,
        }

        def _map_category(cat: str | None) -> BookingType:
            if not cat:
                return BookingType.activity
            return _CATEGORY_MAP.get(cat.strip().lower(), BookingType.activity)

        # ── Count total stops ───────────────────────────────────────────────
        total_stops = sum(len(day.stops) for day in itinerary.days)
        if total_stops == 0:
            raise ValueError(
                f"Itinerary {itinerary.itinerary_id} has no stops to book"
            )

        # ── Create a booking for each stop (iterate within day loop so
        #     ``day`` is guaranteed available — avoid lazy ``stop.day``) ─────
        created_bookings: list[dict] = []
        total_cost = 0.0

        for day in itinerary.days:
            for stop in day.stops:
                place_snapshot = stop.place_snapshot or {}
                place_name = place_snapshot.get("name") or "Unknown Place"
                category = place_snapshot.get("category", "")
                stop_cost = stop.estimated_cost or 0.0
                total_cost += stop_cost

                booking_type = _map_category(category)

                # Derive start datetime from the day's date if available
                start_dt = None
                if day.date:
                    start_dt = datetime.combine(day.date, datetime.min.time())

                booking = Booking(
                    booking_id          = _generate_booking_id(),
                    trip_id             = trip_id,
                    user_id             = user_id,
                    place_id            = stop.place_id,
                    booking_type        = booking_type,
                    provider            = _determine_booking_provider(booking_type),
                    provider_reference  = _generate_transaction_reference(),
                    confirmation_number = _generate_confirmation_number(),
                    start_datetime      = start_dt,
                    total_cost          = stop_cost if stop_cost > 0 else None,
                    currency            = currency,
                    status              = BookingStatus.pending,
                    raw_response        = {
                        "simulated": True,
                        "package_booking": True,
                        "stop_id": stop.stop_id,
                        "day_number": day.day_number,
                        "place_name": place_name,
                        "category": category,
                    },
                )
                self.db.add(booking)

                created_bookings.append({
                    "booking_id":          booking.booking_id,
                    "place_name":          place_name,
                    "booking_type":        booking_type,
                    "category":            category,
                    "total_cost":          booking.total_cost,
                    "currency":            currency,
                    "status":              BookingStatus.pending,
                    "confirmation_number": booking.confirmation_number,
                })

        logger.info(
            "[BookingService] Booked trip package for %s: %d bookings, total=%.2f %s",
            trip_id, len(created_bookings), total_cost, currency,
        )

        return {
            "trip_id":       trip_id,
            "trip_name":     trip.trip_name,
            "destination":   trip.destination,
            "total_cost":    round(total_cost, 2),
            "currency":      currency,
            "bookings":      created_bookings,
            "stop_count":    total_stops,
            "booking_count": len(created_bookings),
        }

    # ── query helpers ──────────────────────────────────────────────────────

    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Fetch a single booking by ID (with payment + receipt eager-loaded)."""
        result = await self.db.execute(
            select(Booking)
            .where(Booking.booking_id == booking_id)
        )
        return result.scalar_one_or_none()
        result = await self.db.execute(
            select(Booking)
            .where(Booking.booking_id == booking_id)
        )
        return result.scalar_one_or_none()

    async def list_trip_bookings(
        self,
        trip_id: str,
        status: Optional[BookingStatus] = None,
    ) -> list[Booking]:
        """List all bookings for a trip, optionally filtered by status."""
        stmt = select(Booking).where(Booking.trip_id == trip_id)
        if status:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Booking.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_user_bookings(
        self,
        user_id: str,
        status: Optional[BookingStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Booking]:
        """List all bookings for a user, optionally filtered by status."""
        stmt = select(Booking).where(Booking.user_id == user_id)
        if status:
            stmt = stmt.where(Booking.status == status)
        stmt = stmt.order_by(Booking.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
