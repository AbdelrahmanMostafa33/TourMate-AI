"""
Integration tests for the full booking lifecycle.

Tests the complete Booking → Payment → Receipt flow with a real in-memory
SQLite database.  Stripe is forced to ``None`` so all payments are simulated
(no external API calls).

Lifecycle tested:
  1. Seed: User + Trip + Place
  2. Create  booking (status = pending)
  3. Process payment (simulated) → Payment + Receipt created, booking → confirmed
  4. Simulate Stripe webhook ``payment_intent.succeeded`` (idempotent)
  5. List trip bookings
  6. Cancel booking → Payment refunded, booking → cancelled
  7. Verify all DB state at each step
"""

import uuid
import pytest
from datetime import datetime, date
from unittest.mock import patch
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.trip import Trip
from app.models.place import Place, HotelDetails
from app.models.booking import Booking, Payment, Receipt
from app.models.enums import (
    BookingType, BookingStatus, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider,
    PlaceCategory, AccommodationType,
)
from app.schemas.booking import BookingCreate, PaymentCreate
from app.services.booking_service import BookingService


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


async def _seed_db(db_session) -> dict:
    """Seed the in-memory database with a User, Trip, and Place.

    Returns dict with the created ORM objects for use in tests.
    """
    # ── User ───────────────────────────────────────────────────────────────
    user = User(
        user_id="booking_test_user",
        email="booking_test@example.com",
        full_name="Booking Test User",
    )
    db_session.add(user)

    # ── Trip ───────────────────────────────────────────────────────────────
    trip = Trip(
        trip_id="booking_test_trip",
        user_id="booking_test_user",
        trip_name="Cairo Booking Test",
        destination="Cairo, Egypt",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 5),
        number_of_travelers=2,
    )
    db_session.add(trip)

    # ── Place (Hotel) ──────────────────────────────────────────────────────
    place = Place(
        place_id="booking_test_hotel",
        name="Marriott Mena House",
        category=PlaceCategory.hotel,
        rating=4.6,
        city="Cairo",
        country="Egypt",
        lat=29.9758,
        lng=31.1334,
    )
    db_session.add(place)

    hotel_details = HotelDetails(
        place_id="booking_test_hotel",
        star_class=5,
        nightly_rate=250.00,
        amenities=["pool", "spa", "restaurant", "free_wifi"],
        accommodation_type=AccommodationType.luxury,
    )
    db_session.add(hotel_details)

    await db_session.commit()
    return {"user": user, "trip": trip, "place": place}


async def _assert_booking_state(
    db_session,
    booking_id: str,
    expected_status: BookingStatus,
    expected_payment_status: PaymentStatus | None = None,
    expected_receipt_exists: bool = False,
) -> Booking:
    """Helper: load a booking with payment+receipt and assert state."""
    result = await db_session.execute(
        select(Booking).where(Booking.booking_id == booking_id)
    )
    booking = result.scalar_one_or_none()
    assert booking is not None, f"Booking {booking_id} not found"
    assert booking.status == expected_status, (
        f"Expected status {expected_status.value}, got {booking.status.value}"
    )

    if expected_payment_status is not None:
        assert booking.payment is not None, "Expected payment to exist"
        assert booking.payment.status == expected_payment_status, (
            f"Expected payment status {expected_payment_status.value}, "
            f"got {booking.payment.status.value}"
        )

        if expected_receipt_exists:
            assert booking.payment.receipt is not None, "Expected receipt to exist"
            assert booking.payment.receipt.receipt_number is not None
            assert booking.payment.receipt.total > 0

    return booking


def _make_booking_create() -> BookingCreate:
    """Standard BookingCreate for tests."""
    return BookingCreate(
        trip_id="booking_test_trip",
        booking_type=BookingType.hotel,
        place_id="booking_test_hotel",
        total_cost=250.00,
        currency="USD",
    )


def _make_payment_create() -> PaymentCreate:
    """Standard PaymentCreate for tests."""
    return PaymentCreate(
        amount=250.00,
        currency="USD",
        payment_method=PaymentMethod.credit_card,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Booking Lifecycle Tests
# ═════════════════════════════════════════════════════════════════════════════


class TestBookingLifecycle:
    """Full booking lifecycle: create → pay → webhook → list → cancel."""

    @pytest.mark.asyncio
    async def test_full_booking_lifecycle(self, db_session):
        """
        Complete lifecycle end-to-end:

        1. Seed User + Trip + Place
        2. Create booking (pending)
        3. Pay via simulated payment (confirmed)
        4. Webhook payment_intent.succeeded (idempotent → no-op)
        5. List trip bookings
        6. Cancel booking (cancelled + refunded)
        7. Final state verification
        """
        svc = BookingService(db_session)
        svc._stripe = None  # Force simulated mode

        # ═══════════════════════════════════════════════════════════════════
        # Phase 1: Seed
        # ═══════════════════════════════════════════════════════════════════
        data = await _seed_db(db_session)
        trip = data["trip"]
        place = data["place"]

        # ═══════════════════════════════════════════════════════════════════
        # Phase 2: Create booking
        # ═══════════════════════════════════════════════════════════════════
        booking = await svc.create_booking(
            trip_id=trip.trip_id,
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        await db_session.commit()

        # Verify booking created with pending status
        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.pending,
        )
        assert booking.booking_type == BookingType.hotel
        assert booking.total_cost == 250.00
        assert booking.currency == "USD"
        assert booking.provider == BookingProvider.booking_com
        assert booking.confirmation_number.startswith("CNF-")
        assert booking.raw_response["simulated"] is True

        # ═══════════════════════════════════════════════════════════════════
        # Phase 3: Process payment (simulated)
        # ═══════════════════════════════════════════════════════════════════
        result = await svc.process_payment(
            booking_id=booking.booking_id,
            data=_make_payment_create(),
        )
        # Auto-confirm (as the pay endpoint does)
        await svc.confirm_booking(booking.booking_id)
        await db_session.commit()

        # Verify payment result
        assert result["success"] is True
        assert result["payment"] is not None
        assert result["receipt"] is not None
        assert result["stripe_payment_intent_id"].startswith("pi_simulated_")

        payment = result["payment"]
        receipt = result["receipt"]
        assert payment.amount == 250.00
        assert payment.currency == "USD"
        assert payment.status == PaymentStatus.completed
        assert payment.provider == PaymentProvider.stripe
        assert payment.payment_method == PaymentMethod.credit_card

        assert receipt.receipt_number.startswith("RCT-")
        assert receipt.subtotal == 250.00
        assert receipt.tax == 25.00  # 10%
        assert receipt.total == 275.00  # 250 + 25
        assert receipt.currency == "USD"

        # Verify booking confirmed
        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.confirmed,
            expected_payment_status=PaymentStatus.completed,
            expected_receipt_exists=True,
        )
        assert booking.payment.payment_id == payment.payment_id
        assert booking.payment.receipt.receipt_id == receipt.receipt_id

        # ═══════════════════════════════════════════════════════════════════
        # Phase 4: Webhook payment_intent.succeeded (idempotent)
        # ═══════════════════════════════════════════════════════════════════
        webhook_result = await svc.handle_webhook_payment_succeeded(
            result["stripe_payment_intent_id"],
        )

        # Should return already_completed — not change anything
        assert webhook_result["status"] == "already_completed"
        assert webhook_result["booking_id"] == booking.booking_id

        # Verify no changes from idempotent webhook
        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.confirmed,
            expected_payment_status=PaymentStatus.completed,
        )

        # ═══════════════════════════════════════════════════════════════════
        # Phase 5: List trip bookings
        # ═══════════════════════════════════════════════════════════════════
        trip_bookings = await svc.list_trip_bookings(trip_id=trip.trip_id)
        assert len(trip_bookings) == 1
        assert trip_bookings[0].booking_id == booking.booking_id

        # Filter by status
        confirmed_bookings = await svc.list_trip_bookings(
            trip_id=trip.trip_id,
            status=BookingStatus.confirmed,
        )
        assert len(confirmed_bookings) == 1

        pending_bookings = await svc.list_trip_bookings(
            trip_id=trip.trip_id,
            status=BookingStatus.pending,
        )
        assert len(pending_bookings) == 0

        # List user bookings
        user_bookings = await svc.list_user_bookings(user_id="booking_test_user")
        assert len(user_bookings) == 1

        # ═══════════════════════════════════════════════════════════════════
        # Phase 6: Cancel booking
        # ═══════════════════════════════════════════════════════════════════
        cancelled = await svc.cancel_booking(booking.booking_id)
        await db_session.commit()

        assert cancelled.status == BookingStatus.cancelled
        assert cancelled.raw_response["cancelled_from"] == "confirmed"

        # Verify payment was refunded
        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.cancelled,
            expected_payment_status=PaymentStatus.refunded,
        )
        assert booking.payment.raw_response["reason"] == "booking_cancelled"

        # ═══════════════════════════════════════════════════════════════════
        # Phase 7: Verify cannot pay or complete a cancelled booking
        # ═══════════════════════════════════════════════════════════════════
        with pytest.raises(ValueError, match="cancelled"):
            await svc.process_payment(
                booking_id=booking.booking_id,
                data=_make_payment_create(),
            )

        with pytest.raises(ValueError, match="must be 'confirmed'"):
            await svc.complete_booking(booking.booking_id)


class TestBookingEdgeCases:
    """Edge cases around the booking lifecycle."""

    @pytest.mark.asyncio
    async def test_create_multiple_bookings_for_same_trip(self, db_session):
        """A trip can have multiple bookings (different places)."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        # Create 2 bookings for the same trip
        booking1 = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        booking2 = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=BookingCreate(
                trip_id="booking_test_trip",
                booking_type=BookingType.restaurant,
                total_cost=75.00,
                currency="USD",
            ),
        )
        await db_session.commit()

        bookings = await svc.list_trip_bookings(trip_id="booking_test_trip")
        assert len(bookings) == 2

        # Verify both bookings have unique IDs
        assert booking1.booking_id != booking2.booking_id

    @pytest.mark.asyncio
    async def test_cancel_before_payment(self, db_session):
        """Cancelling a pending booking should not error on refund (no payment)."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        await db_session.commit()

        cancelled = await svc.cancel_booking(booking.booking_id)
        await db_session.commit()

        assert cancelled.status == BookingStatus.cancelled

        # No payment to refund — no crash
        assert cancelled.payment is None

    @pytest.mark.asyncio
    async def test_complete_booking(self, db_session):
        """A confirmed booking can be marked as completed."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        await svc.process_payment(booking.booking_id, _make_payment_create())
        await svc.confirm_booking(booking.booking_id)
        await db_session.commit()

        # Complete the booking
        completed = await svc.complete_booking(booking.booking_id)
        await db_session.commit()

        assert completed.status == BookingStatus.completed

    @pytest.mark.asyncio
    async def test_webhook_payment_failed(self, db_session):
        """A payment failure webhook should mark the payment as failed without cancelling."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        # Process payment to get a simulated PI ID
        result = await svc.process_payment(booking.booking_id, _make_payment_create())
        await db_session.commit()

        pi_id = result["stripe_payment_intent_id"]

        # Simulate failure webhook
        fail_result = await svc.handle_webhook_payment_failed(pi_id)
        await db_session.commit()

        assert fail_result["status"] == "failed"

        # Booking should still be pending (not cancelled)
        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.pending,
            expected_payment_status=PaymentStatus.failed,
        )

    @pytest.mark.asyncio
    async def test_webhook_charge_refunded(self, db_session):
        """A charge.refunded webhook should mark payment refunded and cancel booking."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        result = await svc.process_payment(booking.booking_id, _make_payment_create())
        await svc.confirm_booking(booking.booking_id)
        await db_session.commit()

        pi_id = result["stripe_payment_intent_id"]

        # Simulate refund webhook
        refund_result = await svc.handle_webhook_charge_refunded(pi_id)
        await db_session.commit()

        assert refund_result["status"] == BookingStatus.cancelled.value

        booking = await _assert_booking_state(
            db_session, booking.booking_id,
            expected_status=BookingStatus.cancelled,
            expected_payment_status=PaymentStatus.refunded,
        )

    @pytest.mark.asyncio
    async def test_get_single_booking(self, db_session):
        """Verify get_booking returns the booking with payment and receipt."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        await svc.process_payment(booking.booking_id, _make_payment_create())
        await svc.confirm_booking(booking.booking_id)
        await db_session.commit()

        loaded = await svc.get_booking(booking.booking_id)
        assert loaded is not None
        assert loaded.booking_id == booking.booking_id
        assert loaded.payment is not None
        assert loaded.payment.receipt is not None
        assert loaded.payment.receipt.total == 275.00

    @pytest.mark.asyncio
    async def test_webhook_idempotency_retry_flow(self, db_session):
        """Simulate Stripe retry: calling succeeded → failed → succeeded is safe."""
        svc = BookingService(db_session)
        svc._stripe = None
        await _seed_db(db_session)

        booking = await svc.create_booking(
            trip_id="booking_test_trip",
            user_id="booking_test_user",
            data=_make_booking_create(),
        )
        result = await svc.process_payment(booking.booking_id, _make_payment_create())
        await svc.confirm_booking(booking.booking_id)
        await db_session.commit()

        pi_id = result["stripe_payment_intent_id"]

        # First webhook: succeeded
        r1 = await svc.handle_webhook_payment_succeeded(pi_id)
        assert r1["status"] == "already_completed"

        # Then failed (should work because webhooks are unordered)
        r2 = await svc.handle_webhook_payment_failed(pi_id)
        assert r2["status"] == "failed"

        # Then refunded
        r3 = await svc.handle_webhook_charge_refunded(pi_id)
        assert r3["status"] == BookingStatus.cancelled.value

        # Second succeeded webhook after refund (edge case - should not crash)
        r4 = await svc.handle_webhook_payment_succeeded(pi_id)
        assert r4["status"] == "already_completed"
