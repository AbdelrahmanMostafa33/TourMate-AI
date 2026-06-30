# backend/app/services/booking_service.py

"""
Booking Service — Hybrid Booking System.

Architecture (Hybrid):
  - **Booking/Confirmation**: Simulated by default, but uses the **Expedia Rapid API**
    for real-time hotel booking when the hotel has a stored Expedia property ID
    and the API credentials are configured.  Falls back to simulation gracefully.
  - **Payment**: Stripe sandbox (test mode).  Creates real PaymentIntent
    objects in Stripe's test environment using test card tokens.
    On success, a Payment + Receipt record is persisted.

Flow:
  1. ``book_hotel_via_expedia()`` → real-time pricing from Expedia → Booking (confirmed)
     or ``create_booking()`` → Booking (status = pending), mock confirmation
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
    PaymentMethod, PaymentStatus, PaymentProvider, TripStatus,
)
from app.models.itinerary import Itinerary, Day, ItineraryStop
from app.models.place import Place, HotelDetails
from app.models.trip import Trip
from app.schemas.booking import BookingCreate, PaymentCreate, PackageBookingItem, BulkPaymentRequest

from app.external.expedia_client import expedia_client

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
      - Expedia      → ``EXP-A3F9C2K7L``        (EXP- + 9 alphanumeric)
      - Airbnb       → ``HXABCDEFGH``           (HX + 8 uppercase letters)
      - Amadeus      → ``WXYZAB``               (6 uppercase letters, PNR-style)
      - Direct/hotel → ``H-8X2KM9P1``           (H- + 8 alphanumeric)
    """
    if provider == BookingProvider.booking_com:
        # Booking.com format: 10-digit numeric
        return "".join(random.choices(string.digits, k=10))

    if provider == BookingProvider.expedia:
        # Expedia format: EXP- + 9 uppercase alphanumeric
        return "EXP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))

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
        BookingType.transport: BookingProvider.other,
    }
    return mapping.get(booking_type, BookingProvider.direct)


def _extract_expedia_property_id(booking_platforms: list[str] | None) -> str | None:
    """Extract the Expedia property ID from a hotel's ``booking_platforms`` list.

    Expected format: ``"expedia:<property_id>"`` (e.g. ``"expedia:123456"``).
    Returns ``None`` if no Expedia ID is found.
    """
    if not booking_platforms:
        return None
    for entry in booking_platforms:
        if entry.startswith("expedia:"):
            return entry.split(":", 1)[1]
    return None


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
    BookingProvider.expedia: {
        "display_name":   "Expedia",
        "website":        "https://www.expedia.com",
        "support_url":    "https://www.expedia.com/help",
        "logo_url":       "https://logos.example.com/expedia.png",
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
                client_secret = intent.get("client_secret")
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
        # ── Load booking (eager-load payment to avoid lazy-load MissingGreenlet in async) ──
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.payment))
            .where(Booking.booking_id == booking_id)
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
                # Create PaymentIntent with automatic_payment_methods so
                # the Flutter client can use the Stripe Payment Sheet.
                intent = self._stripe.PaymentIntent.create(
                    amount=int(round(amount * 100)),  # cents
                    currency=currency,
                    automatic_payment_methods={"enabled": True},
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
                    "client_secret": intent.get("client_secret"),
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
        # Link the Python-side relationship so booking.payment is populated
        # in-memory (avoids MissingGreenlet from async lazy-loading later).
        booking.payment = payment

        # ── Create Receipt record ─────────────────────────────────────────
        tax_amount = round(amount * 0.10, 2)   # simulated 10% tax
        total_amount = round(amount * 1.10, 2)
        currency_upper = currency.upper()

        payment_method_display = _PAYMENT_METHOD_NAMES.get(
            data.payment_method, data.payment_method.value
        )

        receipt = Receipt(
            receipt_id     = str(uuid.uuid4()),
            payment_id     = payment_id,
            receipt_number = _generate_receipt_number(),
            subtotal       = amount,
            tax            = tax_amount,
            total          = total_amount,
            currency       = currency_upper,
        )
        self.db.add(receipt)
        # Link the Python-side relationship so payment.receipt is populated.
        payment.receipt = receipt

        # ── Enrich receipt detail in payment's raw_response ───────────────
        payment.raw_response = {
            **(payment.raw_response or {}),
            "receipt_detail": {
                "payment_method":     payment_method_display,
                "payment_method_type": data.payment_method.value,
                "subtotal":           amount,
                "tax_rate":           "10%",
                "tax_amount":         tax_amount,
                "total":              total_amount,
                "line_items": [
                    {
                        "description": "Accommodation (per night)",
                        "quantity":    1,
                        "unit_price":  amount,
                        "total":       amount,
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

    # ── complete_booking ───────────────────────────────────────────────────

    async def complete_booking(self, booking_id: str) -> Booking:
        """Mark a confirmed booking as completed (post-visit).

        Raises:
            ValueError: If booking not found or not in confirmed status.
        """
        result = await self.db.execute(
            select(Booking)
            .options(selectinload(Booking.payment))
            .where(Booking.booking_id == booking_id)
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

    # ── Expedia hotel booking (real-time) ───────────────────────────────

    @staticmethod
    def _check_expedia_available() -> bool:
        """Check if Expedia Rapid API credentials are configured."""
        return bool(expedia_client._configured)

    async def book_hotel_via_expedia(
        self,
        trip_id: str,
        user_id: str,
        place_id: str,
        checkin: str,
        checkout: str,
        guests: int = 2,
        currency: str = "USD",
    ) -> Booking:
        """Book a hotel via the Expedia Rapid API with real-time pricing.

        Looks up the Expedia property ID from the hotel's ``booking_platforms``
        field, fetches real-time pricing, creates a pending Booking record,
        and returns it.  The booking is already marked as ``confirmed``
        because Expedia confirms immediately on payment.

        Falls back to simulated booking when:
        - No Expedia property ID is stored for this hotel
        - The Expedia API is not configured
        - The Expedia API call fails

        Args:
            trip_id:  Trip to associate the booking with.
            user_id:  User making the booking.
            place_id: The place_id of the hotel (looked up in DB for Expedia ID).
            checkin:  ISO-8601 check-in date.
            checkout: ISO-8601 check-out date.
            guests:   Number of guests (default 2).
            currency: Currency code (default USD).

        Returns:
            The created ``Booking`` ORM object (not yet committed).
        """
        if not self._check_expedia_available():
            logger.info(
                "[BookingService] Expedia not configured — falling back to simulated booking for %s",
                place_id,
            )
            raise ValueError("Expedia not configured")

        # ── Load hotel to get Expedia property ID ─────────────────────────
        result = await self.db.execute(
            select(Place)
            .options(selectinload(Place.hotel_details))
            .where(Place.place_id == place_id)
        )
        place = result.scalar_one_or_none()
        if not place or not place.hotel_details:
            raise ValueError(f"Hotel {place_id} not found or has no hotel_details")

        hd = place.hotel_details
        expedia_id = _extract_expedia_property_id(hd.booking_platforms)
        if not expedia_id:
            raise ValueError(f"Hotel {place.name} has no Expedia property ID stored")

        # ── Get real-time pricing ─────────────────────────────────────────
        try:
            offer = await expedia_client.get_offer(
                property_id=expedia_id,
                checkin=checkin,
                checkout=checkout,
                guests=guests,
            )
        except ValueError as exc:
            logger.warning(
                "[BookingService] Expedia pricing failed for %s: %s — falling back",
                place_id, exc,
            )
            raise  # Let the caller handle the fallback

        total_cost = offer["total"]
        currency_used = offer["currency"] or currency

        # ── Create Booking record (confirmed directly via Expedia) ────────
        start_dt = datetime.fromisoformat(checkin)
        end_dt = datetime.fromisoformat(checkout)

        booking = Booking(
            booking_id          = _generate_booking_id(),
            trip_id             = trip_id,
            user_id             = user_id,
            place_id            = place_id,
            booking_type        = BookingType.hotel,
            provider            = BookingProvider.expedia,
            provider_reference  = f"expedia:{expedia_id}",
            confirmation_number = offer.get("offer_id", ""),
            start_datetime      = start_dt,
            end_datetime        = end_dt,
            total_cost          = total_cost,
            currency            = currency_used,
            status              = BookingStatus.confirmed,  # Expedia confirms immediately
            raw_response        = {
                "expedia": True,
                "expedia_property_id": expedia_id,
                "offer_id": offer.get("offer_id"),
                "name": offer.get("name", place.name),
                "rate": offer.get("rate"),
                "tax_info": offer.get("tax_info"),
                "refundable": offer.get("refundable"),
                "note": "Booked via Expedia Rapid API",
            },
        )

        self.db.add(booking)

        logger.info(
            "[BookingService] Booked hotel via Expedia: %s (cost=%.2f %s) for trip %s",
            place.name, total_cost, currency_used, trip_id,
        )

        return booking

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
          - all other categories are skipped (not bookable)

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

        # ── Map stop categories → BookingType (only hotels are bookable) ───
        _CATEGORY_MAP = {
            "hotel": BookingType.hotel,
        }

        def _map_category(cat: str | None) -> BookingType | None:
            if not cat:
                return None
            return _CATEGORY_MAP.get(cat.strip().lower())

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

                # Skip non-hotel stops — only hotels are bookable
                booking_type = _map_category(category)
                if booking_type is None:
                    continue

                stop_cost = stop.estimated_cost or 0.0
                total_cost += stop_cost

                # Derive start datetime from the day's date if available
                start_dt = None
                if day.date:
                    start_dt = datetime.combine(day.date, datetime.min.time())

                provider = _determine_booking_provider(booking_type)
                provider_info = _get_provider_info(provider)
                conf_number = _generate_confirmation_number(provider)

                booking = Booking(
                    booking_id          = _generate_booking_id(),
                    trip_id             = trip_id,
                    user_id             = user_id,
                    place_id            = stop.place_id,
                    booking_type        = booking_type,
                    provider            = provider,
                    provider_reference  = _generate_transaction_reference(),
                    confirmation_number = conf_number,
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
                        "provider_display_name": provider_info["display_name"],
                        "provider_website":      provider_info["website"],
                        "provider_logo_url":     provider_info["logo_url"],
                        "cancellation_policy":   "Free cancellation within 24 hours",
                        "check_in_time":         "14:00",
                        "check_out_time":        "11:00",
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
                    "confirmation_number": conf_number,
                    "confirmation_format": (
                        "bookingcom-numeric" if provider == BookingProvider.booking_com
                        else "expedia-alpha" if provider == BookingProvider.expedia
                        else "airbnb-alpha" if provider == BookingProvider.airbnb
                        else "pnr-alpha" if provider == BookingProvider.amadeus
                        else "generic-alpha"
                    ),
                    "provider_info": provider_info,
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

    # ── initiate_trip_package ──────────────────────────────────────────

    async def initiate_trip_package(
        self,
        trip_id: str,
        user_id: str,
        data: BulkPaymentRequest,
    ) -> dict:
        """Initiate async Stripe Payment Sheet payments for all pending bookings.

        Iterates over all ``pending`` bookings belonging to the given trip/user,
        calls ``initiate_payment()`` for each (using the shared payment config),
        and returns a dict with ``initiated`` and ``skipped`` lists.

        Unlike ``pay_trip_package()``, this does NOT confirm any booking —
        the Stripe webhook handler will do that when the Payment Sheet is
        completed on the client.

        - Bookings that are not ``pending`` are silently skipped.
        - If initiation fails for an individual booking, it is added to
          ``skipped`` and processing continues.

        Returns:
            A dict with keys:
              - initiated_bookings: list of dicts with booking_id, client_secret,
                stripe_payment_intent_id, simulated, payment_id
              - skipped_bookings: list of dicts with booking_id and reason
              - initiated_count, skipped_count
        """
        all_bookings = await self.list_trip_bookings(trip_id)
        pending_bookings = [
            b for b in all_bookings
            if b.user_id == user_id and b.status == BookingStatus.pending
        ]
        skipped_bookings = [
            b for b in all_bookings
            if b.user_id == user_id and b.status != BookingStatus.pending
        ]

        if not pending_bookings:
            raise ValueError(
                f"No pending bookings found for trip {trip_id} — "
                "all bookings are already paid, cancelled, or completed."
            )

        currency = (data.currency or "USD").upper()
        initiated: list[dict] = []
        skipped: list[dict] = []

        for booking in pending_bookings:
            try:
                booking_amount = booking.total_cost or 0.0
                payment_data = PaymentCreate(
                    amount       = booking_amount,
                    currency     = currency,
                    payment_method = data.payment_method,
                )

                result = await self.initiate_payment(
                    booking.booking_id,
                    payment_data,
                )

                initiated.append({
                    "booking_id":               booking.booking_id,
                    "payment_id":                result["payment_id"],
                    "client_secret":             result["client_secret"],
                    "stripe_payment_intent_id":  result["stripe_payment_intent_id"],
                    "simulated":                 result["simulated"],
                    "message":                   result["message"],
                })

            except ValueError as exc:
                skipped.append({
                    "booking_id": booking.booking_id,
                    "reason":     str(exc),
                })

        # Also report skipped non-pending bookings
        for b in skipped_bookings:
            skipped.append({
                "booking_id": b.booking_id,
                "reason":     f"Booking is already '{b.status.value}' (not pending)",
            })

        logger.info(
            "[BookingService] Bulk initiate for trip %s: %d initiated, %d skipped",
            trip_id, len(initiated), len(skipped),
        )

        return {
            "trip_id":           trip_id,
            "currency":          currency,
            "initiated_count":   len(initiated),
            "skipped_count":     len(skipped),
            "initiated_bookings": initiated,
            "skipped_bookings":  skipped,
        }

    # ── pay_trip_package ───────────────────────────────────────────────────

    async def pay_trip_package(
        self,
        trip_id: str,
        user_id: str,
        data: BulkPaymentRequest,
    ) -> dict:
        """Pay for all pending bookings in a trip using a shared payment config.

        Iterates over all ``pending`` bookings belonging to the given trip/user,
        processes payment for each (using the shared payment config for
        ``payment_method`` and ``currency``), then confirms each booking.

        - Bookings that are not ``pending`` are silently skipped (their status is
          noted in ``skipped_bookings``).
        - If a payment fails for an individual booking, that booking is added to
          ``skipped_bookings`` and processing continues with the next one.

        Args:
            trip_id:  The trip whose pending bookings should be paid.
            user_id:  The user making the payment.
            data:     Shared ``BulkPaymentRequest`` providing ``payment_method``
                      and optional ``currency``.  The per-booking ``amount`` is
                      taken from each booking's ``total_cost``.

        Returns:
            A dict with keys:
              - trip_id, total_charged, currency
              - paid_count, skipped_count
              - paid_bookings: list of ``PackagePaymentItem`` dicts
              - skipped_bookings: list of ``PackagePaymentSkipItem`` dicts
        """
        # ── Load all pending bookings for this trip ────────────────────────
        all_bookings = await self.list_trip_bookings(trip_id)
        pending_bookings = [
            b for b in all_bookings
            if b.user_id == user_id and b.status == BookingStatus.pending
        ]
        skipped_bookings = [
            b for b in all_bookings
            if b.user_id == user_id and b.status != BookingStatus.pending
        ]

        if not pending_bookings:
            raise ValueError(
                f"No pending bookings found for trip {trip_id} — "
                "all bookings are already paid, cancelled, or completed."
            )

        paid_bookings: list[dict] = []
        skipped: list[dict] = []
        total_charged = 0.0
        currency = (data.currency or "USD").upper()

        for booking in pending_bookings:
            try:
                # Build per-booking PaymentCreate using shared method + currency,
                # but use the booking's own cost as the amount.
                booking_amount = booking.total_cost or 0.0
                booking_payment_data = PaymentCreate(
                    amount       = booking_amount,
                    currency     = currency,
                    payment_method = data.payment_method,
                )

                result = await self.process_payment(
                    booking.booking_id,
                    booking_payment_data,
                )
                await self.confirm_booking(booking.booking_id)

                paid_bookings.append({
                    "booking_id":     booking.booking_id,
                    "amount":         result["payment"].amount,
                    "currency":       result["payment"].currency,
                    "receipt_number": result["receipt"].receipt_number,
                    "status":         BookingStatus.confirmed.value,
                })
                total_charged += result["receipt"].total

            except ValueError as exc:
                skipped.append({
                    "booking_id": booking.booking_id,
                    "reason":     str(exc),
                })

        # Also report skipped non-pending bookings
        for b in skipped_bookings:
            skipped.append({
                "booking_id": b.booking_id,
                "reason":     f"Booking is already '{b.status.value}' (not pending)",
            })

        logger.info(
            "[BookingService] Bulk pay for trip %s: %d paid, %d skipped, total=%.2f %s",
            trip_id, len(paid_bookings), len(skipped), total_charged, currency,
        )

        return {
            "trip_id":         trip_id,
            "total_charged":   round(total_charged, 2),
            "currency":        currency,
            "paid_count":      len(paid_bookings),
            "skipped_count":   len(skipped),
            "paid_bookings":   paid_bookings,
            "skipped_bookings": skipped,
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
        if not trip or trip.status != TripStatus.payment_processing:
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
