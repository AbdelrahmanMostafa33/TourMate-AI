"""
Unit tests for BookingService Stripe webhook handlers.

Tests cover:
  - ``find_payment_by_stripe_pi_id`` — found / not found
  - ``handle_webhook_payment_succeeded`` — normal flow + idempotency
  - ``handle_webhook_payment_failed`` — normal flow + idempotency
  - ``handle_webhook_charge_refunded`` — normal flow + idempotency
  - All error cases (payment not found, booking not found)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from app.models.booking import Booking, Payment, Receipt
from app.models.enums import (
    BookingStatus, BookingType, BookingProvider, BookingStatus,
    PaymentMethod, PaymentStatus, PaymentProvider, TripStatus,
)
from app.models.trip import Trip


# ═══════════════════════════════════════════════════════════════════════════════
# ── Factory helpers
# ═══════════════════════════════════════════════════════════════════════════════

def make_mock_payment(
    payment_id: str = "pay_001",
    booking_id: str = "BK-A3F9C2",
    stripe_pi_id: str = "pi_test_123456",
    status: PaymentStatus = PaymentStatus.completed,
) -> MagicMock:
    """Create a mock Payment record."""
    payment = MagicMock(spec=Payment)
    payment.payment_id = payment_id
    payment.booking_id = booking_id
    payment.stripe_payment_intent_id = stripe_pi_id
    payment.status = status
    payment.amount = 150.00
    payment.currency = "USD"
    payment.payment_method = PaymentMethod.credit_card
    payment.provider = PaymentProvider.stripe
    payment.transaction_reference = "TXN-TEST1234"
    payment.raw_response = {"simulated": True}
    payment.paid_at = datetime.utcnow()
    return payment


def make_mock_booking(
    booking_id: str = "BK-A3F9C2",
    trip_id: str = "trip_001",
    user_id: str = "user_001",
    status: BookingStatus = BookingStatus.pending,
    payment: MagicMock | None = None,
) -> MagicMock:
    """Create a mock Booking record."""
    booking = MagicMock(spec=Booking)
    booking.booking_id = booking_id
    booking.trip_id = trip_id
    booking.user_id = user_id
    booking.booking_type = BookingType.hotel
    booking.provider = BookingProvider.booking_com
    booking.provider_reference = "TXN-TEST1234"
    booking.confirmation_number = "CNF-TEST-TEST"
    booking.total_cost = 150.00
    booking.currency = "USD"
    booking.status = status
    booking.raw_response = {}
    booking.payment = payment
    return booking


def make_mock_trip(
    trip_id: str = "trip_001",
    status: TripStatus = TripStatus.payment_processing,
) -> MagicMock:
    """Create a mock Trip record."""
    trip = MagicMock(spec=Trip)
    trip.trip_id = trip_id
    trip.status = status
    return trip


def make_mock_db(execute_return_value=None) -> AsyncMock:
    """Create a mock AsyncSession with a configured execute return."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = execute_return_value
    db.execute.return_value = mock_result
    return db


def make_service(db: AsyncMock) -> object:
    """Create a BookingService instance with a mocked db and Stripe disabled.

    We need to avoid importing BookingService at module level because it
    triggers ``_get_stripe()`` which imports ``stripe`` at runtime.  Instead
    we import lazily inside each test.  This helper keeps the import in one
    place.
    """
    from app.services.booking_service import BookingService
    svc = BookingService(db)
    # Force Stripe to None so tests never attempt real API calls
    svc._stripe = None
    return svc


# ═══════════════════════════════════════════════════════════════════════════════
# ── Tests: find_payment_by_stripe_pi_id
# ═══════════════════════════════════════════════════════════════════════════════

class TestFindPaymentByStripePiId:

    @pytest.mark.asyncio
    async def test_finds_existing_payment(self):
        """Should return the Payment when the Stripe PI ID matches."""
        payment = make_mock_payment(stripe_pi_id="pi_test_abc123")
        db = make_mock_db(execute_return_value=payment)
        svc = make_service(db)

        result = await svc.find_payment_by_stripe_pi_id("pi_test_abc123")

        assert result is payment
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Should return None when no Payment matches the Stripe PI ID."""
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        result = await svc.find_payment_by_stripe_pi_id("pi_nonexistent")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# ── Tests: handle_webhook_payment_succeeded
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandlePaymentSucceeded:

    @pytest.mark.asyncio
    async def test_confirms_booking_on_success(self):
        """Should mark payment completed and confirm the pending booking."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_ok",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.pending,
        )

        db = AsyncMock()
        r1 = MagicMock()  # find_payment → payment
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()  # get_booking → booking
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()  # confirm_booking internal re-fetch → booking
        r3.scalar_one_or_none.return_value = booking
        r4 = MagicMock()  # _check_and_transition_trip_confirmed → trip (planning, not payment_processing)
        r4.scalar_one_or_none.return_value = make_mock_trip(status=TripStatus.planning)

        db.execute.side_effect = [r1, r2, r3, r4]

        svc = make_service(db)

        result = await svc.handle_webhook_payment_succeeded("pi_test_ok")

        assert result["booking_id"] == booking.booking_id
        assert result["status"] == BookingStatus.confirmed.value

        # Payment status updated
        assert payment.status == PaymentStatus.completed

        # Booking confirmed
        assert booking.status == BookingStatus.confirmed

    @pytest.mark.asyncio
    async def test_idempotent_when_already_completed(self):
        """Should return early without error when payment is already completed."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_dup",
            status=PaymentStatus.completed,  # already completed
        )
        db = make_mock_db(execute_return_value=payment)
        svc = make_service(db)

        result = await svc.handle_webhook_payment_succeeded("pi_test_dup")

        assert result["status"] == "already_completed"

    @pytest.mark.asyncio
    async def test_idempotent_when_booking_already_confirmed(self):
        """Should handle case where payment is pending but booking is already confirmed."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_dup2",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.confirmed,  # already confirmed
        )

        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()  # _check_and_transition_trip_confirmed → trip (planning)
        r3.scalar_one_or_none.return_value = make_mock_trip(status=TripStatus.planning)
        db.execute.side_effect = [r1, r2, r3]
        svc = make_service(db)

        result = await svc.handle_webhook_payment_succeeded("pi_test_dup2")

        assert result["status"] == BookingStatus.confirmed.value

    @pytest.mark.asyncio
    async def test_transitions_trip_to_confirmed_when_all_pending_paid(self):
        """Should transition trip from payment_processing → booking_confirmed when
        all pending bookings are confirmed via webhook."""
        payment = make_mock_payment(
            stripe_pi_id="pi_transition",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.pending,
        )
        trip = make_mock_trip(status=TripStatus.payment_processing)

        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()
        r3.scalar_one_or_none.return_value = booking  # confirm_booking re-fetch
        r4 = MagicMock()  # _check_and_transition_trip_confirmed → trip
        r4.scalar_one_or_none.return_value = trip
        r5 = MagicMock()  # list_trip_bookings → no pending remaining
        r5.scalars.return_value.all.return_value = []

        db.execute.side_effect = [r1, r2, r3, r4, r5]
        svc = make_service(db)

        result = await svc.handle_webhook_payment_succeeded("pi_transition")

        assert result["status"] == BookingStatus.confirmed.value
        # Trip should be transitioned to booking_confirmed
        assert trip.status == TripStatus.booking_confirmed

    @pytest.mark.asyncio
    async def test_does_not_transition_trip_when_pending_remain(self):
        """Should NOT transition trip when there are still pending bookings."""
        payment = make_mock_payment(
            stripe_pi_id="pi_partial",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.pending,
        )
        trip = make_mock_trip(status=TripStatus.payment_processing)

        # Simulate one remaining pending booking
        other_pending = make_mock_booking(
            booking_id="BK-OTHER",
            status=BookingStatus.pending,
        )

        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()
        r3.scalar_one_or_none.return_value = booking
        r4 = MagicMock()
        r4.scalar_one_or_none.return_value = trip
        r5 = MagicMock()  # list_trip_bookings → one pending remains
        r5.scalars.return_value.all.return_value = [other_pending]

        db.execute.side_effect = [r1, r2, r3, r4, r5]
        svc = make_service(db)

        result = await svc.handle_webhook_payment_succeeded("pi_partial")

        assert result["status"] == BookingStatus.confirmed.value
        # Trip should stay in payment_processing since other bookings are still pending
        assert trip.status == TripStatus.payment_processing

    @pytest.mark.asyncio
    async def test_raises_error_when_payment_not_found(self):
        """Should raise ValueError when Stripe PI ID doesn't match any Payment."""
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="No Payment found"):
            await svc.handle_webhook_payment_succeeded("pi_unknown")

    @pytest.mark.asyncio
    async def test_raises_error_when_booking_not_found(self):
        """Should raise ValueError when the linked booking doesn't exist."""
        payment = make_mock_payment(stripe_pi_id="pi_test_orphan", status=PaymentStatus.pending)
        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = None  # booking not found
        db.execute.side_effect = [r1, r2]
        svc = make_service(db)

        with pytest.raises(ValueError, match="Booking"):
            await svc.handle_webhook_payment_succeeded("pi_test_orphan")


# ═══════════════════════════════════════════════════════════════════════════════
# ── Tests: handle_webhook_payment_failed
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandlePaymentFailed:

    @pytest.mark.asyncio
    async def test_marks_payment_failed_and_reverts_trip(self):
        """Should mark payment as failed and revert trip to payment_failed."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_fail",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.pending,
        )
        trip = make_mock_trip(status=TripStatus.payment_processing)

        db = AsyncMock()
        r1 = MagicMock()  # find_payment → payment
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()  # get_booking → booking
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()  # select Trip → trip
        r3.scalar_one_or_none.return_value = trip
        db.execute.side_effect = [r1, r2, r3]
        svc = make_service(db)

        result = await svc.handle_webhook_payment_failed("pi_test_fail")

        assert result["payment_id"] == payment.payment_id
        assert result["status"] == "failed"
        assert payment.status == PaymentStatus.failed
        assert trip.status == TripStatus.payment_failed

    @pytest.mark.asyncio
    async def test_idempotent_when_already_failed(self):
        """Should return early when payment is already marked as failed."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_fail_dup",
            status=PaymentStatus.failed,
        )
        db = make_mock_db(execute_return_value=payment)
        svc = make_service(db)

        result = await svc.handle_webhook_payment_failed("pi_test_fail_dup")

        assert result["status"] == "already_failed"

    @pytest.mark.asyncio
    async def test_raises_error_when_payment_not_found(self):
        """Should raise ValueError when Stripe PI ID doesn't match any Payment."""
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="No Payment found"):
            await svc.handle_webhook_payment_failed("pi_unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# ── Tests: handle_webhook_charge_refunded
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleChargeRefunded:

    @pytest.mark.asyncio
    async def test_refunds_payment_and_cancels_booking(self):
        """Should mark payment refunded, cancel the booking, and revert trip to booking_pending."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_refund",
            status=PaymentStatus.completed,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.confirmed,
            payment=payment,
        )
        trip = make_mock_trip(status=TripStatus.booking_confirmed)

        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()
        r3.scalar_one_or_none.return_value = booking  # cancel_booking re-fetches
        r4 = MagicMock()
        r4.scalar_one_or_none.return_value = trip  # trip revert query
        db.execute.side_effect = [r1, r2, r3, r4]
        svc = make_service(db)

        result = await svc.handle_webhook_charge_refunded("pi_test_refund")

        assert result["booking_id"] == booking.booking_id
        assert result["status"] == BookingStatus.cancelled.value
        assert payment.status == PaymentStatus.refunded
        assert booking.status == BookingStatus.cancelled
        assert trip.status == TripStatus.booking_pending

    @pytest.mark.asyncio
    async def test_idempotent_when_already_refunded(self):
        """Should return early when payment is already refunded."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_refund_dup",
            status=PaymentStatus.refunded,
        )
        db = make_mock_db(execute_return_value=payment)
        svc = make_service(db)

        result = await svc.handle_webhook_charge_refunded("pi_test_refund_dup")

        assert result["status"] == "already_refunded"

    @pytest.mark.asyncio
    async def test_idempotent_when_booking_already_cancelled(self):
        """Should handle case where booking was already cancelled."""
        payment = make_mock_payment(
            stripe_pi_id="pi_test_refund_dup2",
            status=PaymentStatus.pending,
        )
        booking = make_mock_booking(
            booking_id=payment.booking_id,
            status=BookingStatus.cancelled,  # already cancelled
        )

        db = AsyncMock()
        r1 = MagicMock()
        r1.scalar_one_or_none.return_value = payment
        r2 = MagicMock()
        r2.scalar_one_or_none.return_value = booking
        r3 = MagicMock()  # trip query (booking.trip_id exists)
        r3.scalar_one_or_none.return_value = make_mock_trip(status=TripStatus.booking_confirmed)
        db.execute.side_effect = [r1, r2, r3]
        svc = make_service(db)

        result = await svc.handle_webhook_charge_refunded("pi_test_refund_dup2")

        assert result["status"] == BookingStatus.cancelled.value

    @pytest.mark.asyncio
    async def test_raises_error_when_payment_not_found(self):
        """Should raise ValueError when Stripe PI ID doesn't match any Payment."""
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="No Payment found"):
            await svc.handle_webhook_charge_refunded("pi_unknown")
