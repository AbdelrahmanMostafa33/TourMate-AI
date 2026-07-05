# backend/app/services/booking_service.py

"""
Booking Service — Booking & Payment System.

Architecture:
  - **Booking/Confirmation**: Simulated by default — generates mock confirmation
    numbers and provider info locally.  No external hotel booking API is called.
  - **Payment**: Stripe sandbox (test mode).  Creates real PaymentIntent
    objects in Stripe's test environment using test card tokens.
    On success, a Payment + Receipt record is persisted.

Flow:
  1. ``create_booking()`` → Booking (status = pending), mock confirmation
  2. ``initiate_payment()`` → Stripe PaymentIntent → Payment (pending)
  3. ``confirm_payment_and_booking()`` or webhook → Payment (completed) + Booking (confirmed)
  4. ``cancel_booking()`` → Booking cancelled, Payment refunded
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
    PaymentMethod, PaymentStatus, PaymentProvider, TripStatus,
)
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.place import HotelDetails
from app.models.trip import Trip
from app.schemas.booking import BookingCreate, PaymentCreate


logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ── helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_booking_id() -> str:
    """Short, human-readable booking ID like ``BK-A3F9C2``."""
    return "BK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ── OTA-specific confirmation formats ────────────────────────────────────────


def _generate_confirmation_number(provider: BookingProvider = BookingProvider.direct) -> str:
    """Generate a confirmation number that looks like the provider's real format.

    Format per provider:
      - Booking.com  → ``1234567890``           (10-digit numeric)
      - Airbnb       → ``HXABCDEFGH``           (HX + 8 uppercase letters)
      - Amadeus      → ``WXYZAB``               (6 uppercase letters, PNR-style)
      - Direct/hotel → ``H-8X2KM9P1``           (H- + 8 alphanumeric)
    """
    if provider == BookingProvider.booking_com:
        # Booking.com format: 10-digit numeric
        return "".join(random.choices(string.digits, k=10))

    if provider == BookingProvider.airbnb:
        # Airbnb format: HX + 8 uppercase letters
        return "HX" + "".join(random.choices(string.ascii_uppercase, k=8))

    if provider == BookingProvider.amadeus:
        # Amadeus PNR format: 6 uppercase letters (like airline record locator)
        return "".join(random.choices(string.ascii_uppercase, k=6))

    if provider == BookingProvider.other or provider == BookingProvider.direct:
        # Generic hotel chain format: H- + 8 alphanumeric
        return "H-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Fallback: classic format
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
        BookingType.hotel:     BookingProvider.booking_com,
        BookingType.flight:    BookingProvider.amadeus,
    }
    return mapping.get(booking_type, BookingProvider.direct)


# ── Provider display info ─────────────────────────────────────────────────────

# ── Payment method display names ─────────────────────────────────────────────

_PAYMENT_METHOD_NAMES: dict[PaymentMethod, str] = {
    PaymentMethod.credit_card: "Credit Card (Visa/Mastercard)",
    PaymentMethod.debit_card:  "Debit Card",
    PaymentMethod.paypal:      "PayPal",
    PaymentMethod.cash:        "Cash",
}


_PROVIDER_DISPLAY: dict[BookingProvider, dict[str, str]] = {
    BookingProvider.booking_com: {
        "display_name":   "Booking.com",
        "website":        "https://www.booking.com",
        "support_url":    "https://www.booking.com/help",
        "logo_url":       "https://logos.example.com/bookingcom.png",
    },
    BookingProvider.airbnb: {
        "display_name":   "Airbnb",
        "website":        "https://www.airbnb.com",
        "support_url":    "https://www.airbnb.com/help",
        "logo_url":       "https://logos.example.com/airbnb.png",
    },
    BookingProvider.amadeus: {
        "display_name":   "Amadeus",
        "website":        "https://www.amadeus.com",
        "support_url":    "https://www.amadeus.com/help",
        "logo_url":       "https://logos.example.com/amadeus.png",
    },
    BookingProvider.direct: {
        "display_name":   "Hotel Direct",
        "website":        "https://www.hoteldirect.com",
        "support_url":    "https://www.hoteldirect.com/help",
        "logo_url":       "https://logos.example.com/hoteldirect.png",
    },
    BookingProvider.other: {
        "display_name":   "Booking Partner",
        "website":        "https://www.bookingpartner.com",
        "support_url":    "https://www.bookingpartner.com/help",
        "logo_url":       "https://logos.example.com/bookingpartner.png",
    },
}


def _get_provider_info(provider: BookingProvider) -> dict[str, str]:
    """Get rich display info for a booking provider.

    Returns a dict with: ``display_name``, ``website``, ``support_url``, ``logo_url``.
    Falls back to a generic entry for unknown providers.
    """
    return _PROVIDER_DISPLAY.get(provider, _PROVIDER_DISPLAY[BookingProvider.direct])


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
    stripe.api_version = "2026-06-24.dahlia"
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
        provider_info = _get_provider_info(provider)

        booking = Booking(
            booking_id          = _generate_booking_id(),
            trip_id             = trip_id,
            user_id             = user_id,
            place_id            = data.place_id,
            booking_type        = data.booking_type,
            provider            = provider,
            provider_reference  = data.provider_reference or _generate_transaction_reference(),
            confirmation_number = data.confirmation_number or _generate_confirmation_number(provider),
            start_datetime      = data.start_datetime,
            end_datetime        = data.end_datetime,
            total_cost          = data.total_cost,
            currency            = data.currency or "USD",
            status              = BookingStatus.pending,
            raw_response        = {
                "simulated": True,
                "provider": provider.value,
                "provider_display_name": provider_info["display_name"],
                "provider_website":      provider_info["website"],
                "provider_logo_url":     provider_info["logo_url"],
                "cancellation_policy":   "Free cancellation within 24 hours",
                "check_in_time":         "14:00",
                "check_out_time":        "11:00",
                "note":                  "Booking confirmation is simulated (no external API call).",
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

    # ── initiate_payment ──────────────────────────────────────────────────

    async def initiate_payment(
        self,
        booking_id: str,
        data: PaymentCreate,
    ) -> dict:
        """Initiate an async Stripe Payment Sheet flow.

        Creates a Stripe PaymentIntent in ``requires_payment_method`` status
        and a Payment record in ``pending`` status.  Does NOT confirm the
        booking — the Stripe webhook handler
        (``handle_webhook_payment_succeeded``) will do that when the user
        completes the Payment Sheet on the client.

        Args:
            booking_id: The booking to initiate payment for.
            data:       Payment details (amount, currency, method).

        Returns:
            A dict with keys:
              - success: bool
              - client_secret: str | None (for Stripe Payment Sheet)
              - stripe_payment_intent_id: str | None
              - payment_id: str
              - simulated: bool
              - message: str

        Raises:
            ValueError: If booking not found, already paid, or cancelled.
        """
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.payment))
            .where(Booking.booking_id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Booking {booking_id} is cancelled")
        if booking.status == BookingStatus.completed:
            raise ValueError(f"Booking {booking_id} is already completed")
        if booking.status == BookingStatus.confirmed:
            raise ValueError(f"Booking {booking_id} is already confirmed")
        if booking.payment:
            raise ValueError(f"Booking {booking_id} already has a payment")

        amount = data.amount if data.amount is not None else (booking.total_cost or 0)
        currency = (data.currency or booking.currency or "USD").lower()
        payment_id = str(uuid.uuid4())
        stripe_pi_id = None
        client_secret = None
        simulated = False
        raw_response = {}

        # ── Create Stripe PaymentIntent (unconfirmed) ──────────────────
        if self._stripe is not None:
            try:
                intent = self._stripe.PaymentIntent.create(
                    amount=int(round(amount * 100)),
                    currency=currency,
                    automatic_payment_methods={"enabled": True},
                    metadata={
                        "booking_id": booking_id,
                        "trip_id": booking.trip_id,
                        "mode": "sandbox",
                        "initiated": "true",
                    },
                )
                stripe_pi_id = intent["id"]
                # Stripe SDK v15+ StripeObject supports attribute access, NOT .get()
                client_secret = intent.client_secret

                # ══ DEBUG: if client_secret is unexpectedly None, log the full Stripe response ══
                if client_secret is None:
                    logger.warning(
                        "[BookingService] ⚠️ client_secret is NULL for PaymentIntent %s! "
                        "Full Stripe response follows:\n%s",
                        stripe_pi_id, intent.to_dict(),
                    )
                else:
                    logger.info(
                        "[BookingService] client_secret OK for PI %s (len=%d)",
                        stripe_pi_id, len(client_secret),
                    )

                raw_response = {
                    "stripe_payment_intent_id": stripe_pi_id,
                    "status": intent["status"],
                    "amount": intent["amount"],
                    "currency": intent["currency"],
                    "sandbox": True,
                    "client_secret": client_secret,
                    "initiated": True,
                }
                logger.info(
                    "[BookingService] Initiated PaymentIntent %s (status=%s) for booking %s",
                    stripe_pi_id, intent["status"], booking_id,
                )
            except Exception as exc:
                logger.error(
                    "[BookingService] Stripe initiate failed for booking %s: %s",
                    booking_id, exc,
                )
                raw_response = {
                    "stripe_error": str(exc),
                    "note": "Fell back to simulated payment after Stripe error.",
                }

        # ── Fallback: simulated payment initiation ─────────────────────
        if stripe_pi_id is None:
            stripe_pi_id = f"pi_simulated_{uuid.uuid4().hex[:12]}"
            client_secret = f"pi_simulated_{uuid.uuid4().hex[:16]}_secret_{uuid.uuid4().hex[:8]}"
            simulated = True
            raw_response = {
                "simulated": True,
                "stripe_payment_intent_id": stripe_pi_id,
                "client_secret": client_secret,
                "amount": amount,
                "currency": currency,
                "note": "Simulated payment initiation (no Stripe API call).",
            }
            logger.info(
                "[BookingService] Simulated payment initiation for booking %s (amount=%.2f %s)",
                booking_id, amount, currency,
            )

        # ── Create Payment record (pending — not completed) ────────────
        payment = Payment(
            payment_id               = payment_id,
            booking_id               = booking_id,
            amount                   = amount,
            currency                 = currency.upper(),
            payment_method           = data.payment_method,
            provider                 = PaymentProvider.stripe,
            stripe_payment_intent_id = stripe_pi_id,
            transaction_reference    = data.transaction_reference or _generate_transaction_reference(),
            status                   = PaymentStatus.pending,  # NOT completed yet
            raw_response             = raw_response,
            paid_at                  = None,  # paid when webhook confirms
        )
        self.db.add(payment)
        booking.payment = payment

        logger.info(
            "[BookingService] Initiated payment %s for booking %s (simulated=%s)",
            payment_id, booking_id, simulated,
        )

        return {
            "success": True,
            "payment_id": payment_id,
            "client_secret": client_secret,
            "stripe_payment_intent_id": stripe_pi_id,
            "simulated": simulated,
            "message": "Payment initiated. Complete via Stripe Payment Sheet."
                       if not simulated
                       else "Payment initiated (simulated).",
        }

    # ── confirm_booking ────────────────────────────────────────────────────

    async def confirm_booking(self, booking_id: str) -> Booking:
        """Transition booking status from ``pending`` → ``confirmed``.

        Typically called after ``process_payment()`` succeeds.

        Raises:
            ValueError: If booking not found, already confirmed, cancelled, or completed.
        """
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.payment))
            .where(Booking.booking_id == booking_id)
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
            select(Booking)
            .options(selectinload(Booking.payment))
            .where(Booking.booking_id == booking_id)
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

    # ── Stripe webhook event handlers ─────────────────────────────────────

    async def find_payment_by_stripe_pi_id(
        self, stripe_payment_intent_id: str
    ) -> Optional[Payment]:
        """Find a Payment record by its Stripe PaymentIntent ID."""
        result = await self.db.execute(
            select(Payment)
            .options(selectinload(Payment.receipt))
            .where(
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

        # ── Create Receipt if this payment was initiated (pending → completed) ─
        # In the async flow (initiate_payment), no Receipt was created yet.
        # The sync flow (process_payment) already created one.
        if not payment.receipt:
            tax_amount = round((payment.amount or 0) * 0.10, 2)
            total_amount = round((payment.amount or 0) * 1.10, 2)
            receipt = Receipt(
                receipt_id     = str(uuid.uuid4()),
                payment_id     = payment.payment_id,
                receipt_number = _generate_receipt_number(),
                subtotal       = payment.amount or 0,
                tax            = tax_amount,
                total          = total_amount,
                currency       = payment.currency or "USD",
            )
            self.db.add(receipt)
            payment.receipt = receipt

            # Enrich payment.raw_response with receipt_detail (same as process_payment)
            payment_method_display = _PAYMENT_METHOD_NAMES.get(
                payment.payment_method, (payment.payment_method or "card") if isinstance(payment.payment_method, str) else "card"
            )
            payment.raw_response = {
                **(payment.raw_response or {}),
                "receipt_detail": {
                    "payment_method":      payment_method_display,
                    "payment_method_type": payment.payment_method.value if hasattr(payment.payment_method, 'value') else str(payment.payment_method),
                    "subtotal":            payment.amount or 0,
                    "tax_rate":            "10%",
                    "tax_amount":          tax_amount,
                    "total":               total_amount,
                    "line_items": [
                        {
                            "description": "Accommodation (per night)",
                            "quantity":    1,
                            "unit_price":  payment.amount or 0,
                            "total":       payment.amount or 0,
                        },
                        {
                            "description": "Service fee",
                            "quantity":    1,
                            "unit_price":  tax_amount,
                            "total":       tax_amount,
                        },
                    ],
                    "billing_address": {
                        "line1":       "123 Demo Street",
                        "city":        "Cairo",
                        "country":     "Egypt",
                        "postal_code": "12345",
                    },
                    "issuer": {
                        "name":         "TourMate AI Booking Services",
                        "email":        "receipts@tourmate.ai",
                        "support_url":  "https://tourmate.ai/support",
                    },
                },
            }
            logger.info(
                "[BookingService] Webhook: Created receipt %s for async payment %s",
                receipt.receipt_number, payment.payment_id,
            )

        # ── Update payment status ─────────────────────────────────────────
        payment.status = PaymentStatus.completed
        payment.paid_at = datetime.utcnow()
        payment.raw_response = {
            **(payment.raw_response or {}),
            "webhook_confirmed_at": datetime.utcnow().isoformat(),
            "webhook_event": "payment_intent.succeeded",
        }

        # ── Confirm the linked booking (idempotent: skips if already done) ─
        booking = await self.get_booking(payment.booking_id)
        if not booking:
            raise ValueError(f"Booking {payment.booking_id} not found")

        if booking.status == BookingStatus.cancelled:
            # Payment.succeeded after cancellation (e.g. out-of-order webhooks).
            # The booking stays cancelled; don't error since Stripe webhooks
            # can be delivered out of order.
            logger.info(
                "[BookingService] Webhook: payment_intent.succeeded for PI=%s "
                "— booking %s is cancelled, keeping as-is",
                stripe_payment_intent_id, booking.booking_id,
            )
        elif booking.status not in (BookingStatus.confirmed, BookingStatus.completed):
            booking = await self.confirm_booking(payment.booking_id)
        else:
            logger.info(
                "[BookingService] Webhook: booking %s already %s — skipping",
                booking.booking_id, booking.status.value,
            )

        # ── If this was part of a trip, check if all bookings are now confirmed ──
        if booking.trip_id:
            await self._check_and_transition_trip_confirmed(booking.trip_id)

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

        # ── Revert trip to payment_failed immediately ──────────────────────
        booking = await self.get_booking(payment.booking_id)
        if booking and booking.trip_id:
            trip_result = await self.db.execute(
                select(Trip).where(Trip.trip_id == booking.trip_id)
            )
            trip = trip_result.scalar_one_or_none()
            if trip and trip.status == TripStatus.payment_processing:
                trip.status = TripStatus.payment_failed
                logger.info(
                    "[BookingService] Webhook: payment_intent.payment_failed for PI=%s "
                    "→ trip %s → payment_failed",
                    stripe_payment_intent_id, trip.trip_id,
                )

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

        # ── If the trip was confirmed, revert to booking_pending ────────────
        if booking.trip_id:
            trip_result = await self.db.execute(
                select(Trip).where(Trip.trip_id == booking.trip_id)
            )
            trip = trip_result.scalar_one_or_none()
            if trip and trip.status == TripStatus.booking_confirmed:
                trip.status = TripStatus.booking_pending
                logger.info(
                    "[BookingService] Webhook: charge.refunded for PI=%s "
                    "→ trip %s → booking_pending (refunded booking %s)",
                    stripe_payment_intent_id, trip.trip_id, booking.booking_id,
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

    # ── confirm_payment_and_booking (client-side verification) ──────────

    async def confirm_payment_and_booking(
        self,
        booking_id: str,
        stripe_payment_intent_id: str,
    ) -> dict:
        """Confirm a booking after the client reports the Payment Sheet succeeded.

        This is the **client-side verification** alternative to waiting for the
        Stripe webhook.  The Flutter app calls this endpoint after the Payment
        Sheet completes successfully.  The backend verifies the PaymentIntent
        status with Stripe's API directly (not trusting the client) and, if
        confirmed, marks the payment complete and confirms the booking.

        The webhook handler (``handle_webhook_payment_succeeded``) also does
        the same work, so whichever arrives first wins (idempotent).

        Args:
            booking_id: The booking to confirm.
            stripe_payment_intent_id: The Stripe PaymentIntent ID to verify.

        Returns:
            A dict with keys: booking_id, payment_id, status.

        Raises:
            ValueError: If booking not found, no payment matches, or Stripe
                        verification fails.
        """
        # ── 1. Load booking with payment ──────────────────────────────────
        booking = await self.get_booking(booking_id)
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        if booking.status == BookingStatus.cancelled:
            raise ValueError(f"Booking {booking_id} is cancelled")
        if booking.status == BookingStatus.completed:
            raise ValueError(f"Booking {booking_id} is already completed")

        payment = booking.payment
        if not payment:
            raise ValueError(
                f"Booking {booking_id} has no payment record — initiate payment first"
            )

        # ── 2. Verify the stored PI ID matches what the client passed ─────
        if payment.stripe_payment_intent_id != stripe_payment_intent_id:
            raise ValueError(
                f"Stripe PI ID mismatch: booking has '{payment.stripe_payment_intent_id}', "
                f"client passed '{stripe_payment_intent_id}'"
            )

        # ── 3. Verify with Stripe directly that the PaymentIntent succeeded ─
        if self._stripe is not None:
            try:
                intent = self._stripe.PaymentIntent.retrieve(
                    stripe_payment_intent_id,
                )
                pi_status = intent["status"]
                if pi_status != "succeeded":
                    raise ValueError(
                        f"PaymentIntent status is '{pi_status}', not 'succeeded' — "
                        "the payment has not completed yet."
                    )
            except Exception as exc:
                err_str = str(exc)
                if "No such PaymentIntent" in err_str:
                    raise ValueError(
                        f"PaymentIntent '{stripe_payment_intent_id}' not found in Stripe. "
                        "It may have been created in a different environment."
                    )
                raise ValueError(
                    f"Stripe verification failed for '{stripe_payment_intent_id}': {exc}"
                )
            logger.info(
                "[BookingService] Verified PaymentIntent %s → status=%s",
                stripe_payment_intent_id, pi_status,
            )

        # ── 4. If already confirmed via webhook, return early ─────────────
        if payment.status == PaymentStatus.completed:
            logger.info(
                "[BookingService] confirm_payment_and_booking: booking %s already confirmed — skipping",
                booking_id,
            )
            return {
                "booking_id": booking_id,
                "payment_id": payment.payment_id,
                "status": "already_confirmed",
            }

        # ── 5. Create Receipt (same logic as handle_webhook) ──────────────
        if not payment.receipt:
            tax_amount = round((payment.amount or 0) * 0.10, 2)
            total_amount = round((payment.amount or 0) * 1.10, 2)
            receipt = Receipt(
                receipt_id     = str(uuid.uuid4()),
                payment_id     = payment.payment_id,
                receipt_number = _generate_receipt_number(),
                subtotal       = payment.amount or 0,
                tax            = tax_amount,
                total          = total_amount,
                currency       = payment.currency or "USD",
            )
            self.db.add(receipt)
            payment.receipt = receipt

            payment_method_display = _PAYMENT_METHOD_NAMES.get(
                payment.payment_method,
                (payment.payment_method or "card") if isinstance(payment.payment_method, str) else "card"
            )
            payment.raw_response = {
                **(payment.raw_response or {}),
                "receipt_detail": {
                    "payment_method":      payment_method_display,
                    "payment_method_type": payment.payment_method.value if hasattr(payment.payment_method, 'value') else str(payment.payment_method),
                    "subtotal":            payment.amount or 0,
                    "tax_rate":            "10%",
                    "tax_amount":          tax_amount,
                    "total":               total_amount,
                },
            }

        # ── 6. Complete the payment ───────────────────────────────────────
        payment.status = PaymentStatus.completed
        payment.paid_at = datetime.utcnow()
        payment.raw_response = {
            **(payment.raw_response or {}),
            "confirmed_via": "client_verify",
            "confirmed_at": datetime.utcnow().isoformat(),
        }

        # ── 7. Confirm the booking ────────────────────────────────────────
        if booking.status not in (BookingStatus.confirmed, BookingStatus.completed):
            booking.status = BookingStatus.confirmed
            booking.raw_response = {
                **(booking.raw_response or {}),
                "confirmed_at": datetime.utcnow().isoformat(),
                "confirmed_via": "client_verify",
            }

        # ── 8. Check if trip can transition ───────────────────────────────
        if booking.trip_id:
            await self._check_and_transition_trip_confirmed(booking.trip_id)

        logger.info(
            "[BookingService] confirm_payment_and_booking: confirmed booking %s (PI=%s)",
            booking_id, stripe_payment_intent_id,
        )

        return {
            "booking_id": booking_id,
            "payment_id": payment.payment_id,
            "status": "confirmed",
        }

    # ── Trip status helpers ──────────────────────────────────────────────

    async def _check_and_transition_trip_confirmed(
        self,
        trip_id: str,
    ) -> bool:
        """Check if all bookings for a trip are confirmed, and if so,
        transition the trip from ``payment_processing`` → ``booking_confirmed``.

        Called after each ``payment_intent.succeeded`` webhook to see if the
        async batch payment flow has completed.

        Returns:
            ``True`` if the trip was transitioned, ``False`` otherwise.
        """
        # Load trip
        result = await self.db.execute(
            select(Trip).where(Trip.trip_id == trip_id)
        )
        trip = result.scalar_one_or_none()
        if not trip:
            return False
        # Accept both payment_processing (individual flow via initiate-payment)
        # and awaiting_booking (direct confirm without prior initiate)
        if trip.status not in (TripStatus.payment_processing, TripStatus.awaiting_booking):
            return False

        # Check if any pending bookings remain
        remaining = await self.list_trip_bookings(
            trip_id, status=BookingStatus.pending
        )
        if remaining:
            logger.info(
                "[BookingService] Trip %s still has %d pending booking(s) — staying in payment_processing",
                trip_id, len(remaining),
            )
            return False

        # All bookings are confirmed or cancelled — transition trip
        trip.status = TripStatus.booking_confirmed
        logger.info(
            "[BookingService] All bookings confirmed for trip %s → booking_confirmed",
            trip_id,
        )
        return True

    # ── query helpers ──────────────────────────────────────────────────────

    async def get_booking(self, booking_id: str) -> Optional[Booking]:
        """Fetch a single booking by ID (with payment + receipt eager-loaded)."""
        result = await self.db.execute(
            select(Booking)
            .options(
                selectinload(Booking.payment).selectinload(Payment.receipt),
            )
            .where(Booking.booking_id == booking_id)
        )
        return result.scalar_one_or_none()

    async def list_trip_bookings(
        self,
        trip_id: str,
        status: Optional[BookingStatus] = None,
    ) -> list[Booking]:
        """List all bookings for a trip, optionally filtered by status.

        Uses ``selectinload`` for the ``payment`` relationship to avoid
        ``MissingGreenlet`` errors in async sessions when FastAPI serializes
        the response via Pydantic after the session closes.
        """
        stmt = (
            select(Booking)
            .options(
                selectinload(Booking.payment).selectinload(Payment.receipt),
            )
            .where(Booking.trip_id == trip_id)
        )
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
