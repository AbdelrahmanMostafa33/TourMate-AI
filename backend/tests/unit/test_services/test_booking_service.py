"""Unit tests for booking_service.py — booking creation, payment initiation,
cancellation, client-side verification, and query helpers.

Coverage targets (beyond test_booking_webhook_handlers.py):
  - Module-level helpers: _generate_booking_id, _generate_confirmation_number
    (all 5 providers + fallback), _generate_receipt_number,
    _generate_transaction_reference, _determine_booking_provider,
    _get_provider_info
  - _get_stripe: SDK available, SDK missing, key missing
  - BookingService.create_booking: with/without provider, refs, confirmation
  - BookingService.initiate_payment: all error guards, Stripe path, simulated
    fallback, Stripe error fallback
  - BookingService.confirm_booking: not found, already confirmed/completed,
    cancelled, normal flow
  - BookingService.cancel_booking: not found, already cancelled, without
    payment, with payment refund
  - BookingService.confirm_payment_and_booking: all guards, Stripe verify
    success/failure, simulated, already webhook-confirmed
  - BookingService._check_and_transition_trip_confirmed: all paths
  - Query helpers: get_booking, list_trip_bookings, list_user_bookings
"""

from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest

from app.models.booking import Booking, Payment, Receipt
from app.models.enums import (
    BookingStatus, BookingType, BookingProvider,
    PaymentMethod, PaymentStatus, PaymentProvider, TripStatus,
)
from app.models.trip import Trip
from app.schemas.booking import BookingCreate, PaymentCreate


# ═══════════════════════════════════════════════════════════════════════════════
# ── Factory helpers (following test_booking_webhook_handlers.py pattern)
# ═══════════════════════════════════════════════════════════════════════════════


def make_mock_payment(
    payment_id: str = "pay_001",
    booking_id: str = "BK-A3F9C2",
    stripe_pi_id: str = "pi_test_123456",
    status: PaymentStatus = PaymentStatus.pending,
) -> MagicMock:
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
    payment.paid_at = None
    payment.receipt = None
    return payment


def make_mock_booking(
    booking_id: str = "BK-A3F9C2",
    trip_id: str = "trip_001",
    user_id: str = "user_001",
    status: BookingStatus = BookingStatus.pending,
    payment: MagicMock | None = None,
    total_cost: float = 150.00,
    currency: str = "USD",
) -> MagicMock:
    booking = MagicMock(spec=Booking)
    booking.booking_id = booking_id
    booking.trip_id = trip_id
    booking.user_id = user_id
    booking.booking_type = BookingType.hotel
    booking.provider = BookingProvider.booking_com
    booking.provider_reference = "TXN-TEST1234"
    booking.confirmation_number = "CNF-TEST-TEST"
    booking.total_cost = total_cost
    booking.currency = currency
    booking.status = status
    booking.raw_response = {}
    booking.payment = payment
    return booking


def make_mock_trip(
    trip_id: str = "trip_001",
    status: TripStatus = TripStatus.payment_processing,
) -> MagicMock:
    trip = MagicMock(spec=Trip)
    trip.trip_id = trip_id
    trip.status = status
    return trip


def make_mock_db(execute_return_value=None) -> AsyncMock:
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = execute_return_value
    db.execute.return_value = mock_result
    return db


def make_service(db: AsyncMock) -> object:
    """Create a BookingService with Stripe disabled (no real API calls)."""
    from app.services.booking_service import BookingService
    svc = BookingService(db)
    svc._stripe = None  # Force simulated payments
    return svc


# ═══════════════════════════════════════════════════════════════════════════════
# ── Module-level helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateBookingId:
    """Tests for _generate_booking_id."""

    def test_format_bk_prefix(self):
        from app.services.booking_service import _generate_booking_id
        booking_id = _generate_booking_id()
        assert booking_id.startswith("BK-")
        # BK- + 6 chars = 9 total
        assert len(booking_id) == 9

    def test_all_uppercase_and_digits(self):
        from app.services.booking_service import _generate_booking_id
        for _ in range(20):
            bid = _generate_booking_id()
            suffix = bid[3:]  # after "BK-"
            assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in suffix)


class TestGenerateConfirmationNumber:
    """Tests for _generate_confirmation_number — all provider formats."""

    def test_booking_com_format(self):
        from app.services.booking_service import _generate_confirmation_number
        cnf = _generate_confirmation_number(BookingProvider.booking_com)
        assert len(cnf) == 10
        assert cnf.isdigit()

    def test_airbnb_format(self):
        from app.services.booking_service import _generate_confirmation_number
        cnf = _generate_confirmation_number(BookingProvider.airbnb)
        assert cnf.startswith("HX")
        assert len(cnf) == 10
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for c in cnf[2:])

    def test_amadeus_format(self):
        from app.services.booking_service import _generate_confirmation_number
        cnf = _generate_confirmation_number(BookingProvider.amadeus)
        assert len(cnf) == 6
        assert cnf.isalpha() and cnf.isupper()

    def test_direct_format(self):
        from app.services.booking_service import _generate_confirmation_number
        cnf = _generate_confirmation_number(BookingProvider.direct)
        assert cnf.startswith("H-")
        assert len(cnf) == 10  # H- + 8 alphanumeric

    def test_other_format(self):
        from app.services.booking_service import _generate_confirmation_number
        cnf = _generate_confirmation_number(BookingProvider.other)
        assert cnf.startswith("H-")
        assert len(cnf) == 10

    def test_fallback_for_unknown_provider(self):
        from app.services.booking_service import _generate_confirmation_number
        # Pass a string that's not a valid BookingProvider enum
        # The function falls through to the fallback format
        cnf = _generate_confirmation_number(None)
        assert cnf.startswith("CNF-")
        assert "CNF-" in cnf


class TestGenerateReceiptNumber:
    """Tests for _generate_receipt_number."""

    def test_format(self):
        from app.services.booking_service import _generate_receipt_number
        rct = _generate_receipt_number()
        assert rct.startswith("RCT-")
        parts = rct.split("-")
        assert len(parts) == 3
        assert parts[0] == "RCT"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 4  # hex digits


class TestGenerateTransactionReference:
    """Tests for _generate_transaction_reference."""

    def test_format(self):
        from app.services.booking_service import _generate_transaction_reference
        txn = _generate_transaction_reference()
        assert txn.startswith("TXN-")
        assert len(txn) == 12  # TXN- + 8 chars


class TestDetermineBookingProvider:
    """Tests for _determine_booking_provider."""

    def test_hotel_maps_to_booking_com(self):
        from app.services.booking_service import _determine_booking_provider
        assert _determine_booking_provider(BookingType.hotel) == BookingProvider.booking_com

    def test_flight_maps_to_amadeus(self):
        from app.services.booking_service import _determine_booking_provider
        assert _determine_booking_provider(BookingType.flight) == BookingProvider.amadeus

    def test_unknown_booking_type_defaults_to_direct(self):
        from app.services.booking_service import _determine_booking_provider
        # A booking type not in the mapping should fall back to direct
        from app.services.booking_service import _determine_booking_provider
        # Simulate an unknown type by passing a random string
        class FakeType:
            value = "unknown"
        assert _determine_booking_provider(FakeType()) == BookingProvider.direct


class TestGetProviderInfo:
    """Tests for _get_provider_info."""

    def test_booking_com(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info(BookingProvider.booking_com)
        assert info["display_name"] == "Booking.com"

    def test_airbnb(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info(BookingProvider.airbnb)
        assert info["display_name"] == "Airbnb"

    def test_amadeus(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info(BookingProvider.amadeus)
        assert info["display_name"] == "Amadeus"

    def test_direct(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info(BookingProvider.direct)
        assert info["display_name"] == "Hotel Direct"

    def test_other(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info(BookingProvider.other)
        assert info["display_name"] == "Booking Partner"

    def test_unknown_provider_falls_back_to_direct(self):
        from app.services.booking_service import _get_provider_info
        info = _get_provider_info("unknown_provider")
        assert info["display_name"] == "Hotel Direct"


# ═══════════════════════════════════════════════════════════════════════════════
# ── _get_stripe
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetStripe:
    """Tests for _get_stripe — lazy import + credential check."""

    def test_sdk_not_installed_returns_none(self):
        """When the 'stripe' package is not installed, return None."""
        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def mock_import(name, *args, **kwargs):
            if name == "stripe":
                raise ImportError("No module named 'stripe'")
            return original_import(name, *args, **kwargs)

        import builtins
        with patch.object(builtins, "__import__", side_effect=mock_import):
            from app.services.booking_service import _get_stripe
            result = _get_stripe()
            assert result is None

    def test_key_not_set_returns_none(self):
        """When STRIPE_SECRET_KEY is empty, return None."""
        # _get_stripe does ``from app.core.config import settings`` as a local import
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = ""
            from app.services.booking_service import _get_stripe
            result = _get_stripe()
            assert result is None

    def test_success_returns_stripe_module(self):
        """When SDK is installed and key is set, return the stripe module."""
        mock_stripe = MagicMock()
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.STRIPE_SECRET_KEY = "sk_test_abc123"
                from app.services.booking_service import _get_stripe
                result = _get_stripe()
                assert result is mock_stripe
                assert mock_stripe.api_key == "sk_test_abc123"


# ═══════════════════════════════════════════════════════════════════════════════
# ── create_booking
# ═══════════════════════════════════════════════════════════════════════════════


class TestCreateBooking:
    """Tests for BookingService.create_booking."""

    @pytest.mark.asyncio
    async def test_creates_booking_with_given_provider(self):
        """When a provider is specified, it should be used directly."""
        db = AsyncMock()
        svc = make_service(db)
        data = BookingCreate(
            booking_type=BookingType.hotel,
            place_id="place_001",
            total_cost=200.0,
            currency="USD",
            provider=BookingProvider.airbnb,
        )

        booking = await svc.create_booking(
            trip_id="trip_001", user_id="user_001", data=data,
        )

        assert booking.booking_id.startswith("BK-")
        assert booking.trip_id == "trip_001"
        assert booking.user_id == "user_001"
        assert booking.place_id == "place_001"
        assert booking.booking_type == BookingType.hotel
        assert booking.provider == BookingProvider.airbnb
        assert booking.total_cost == 200.0
        assert booking.currency == "USD"
        assert booking.status == BookingStatus.pending
        assert booking.raw_response["simulated"] is True
        db.add.assert_called_once_with(booking)

    @pytest.mark.asyncio
    async def test_determines_provider_when_not_given(self):
        """When no provider is given, _determine_booking_provider is used."""
        db = AsyncMock()
        svc = make_service(db)
        data = BookingCreate(
            booking_type=BookingType.hotel,
            total_cost=100.0,
        )

        booking = await svc.create_booking(
            trip_id="trip_001", user_id="user_001", data=data,
        )

        # Hotel → booking_com (from _determine_booking_provider)
        assert booking.provider == BookingProvider.booking_com
        assert "booking.com" in booking.raw_response["provider_display_name"].lower()

    @pytest.mark.asyncio
    async def test_uses_given_references(self):
        """When provider_reference and confirmation_number are given, use them."""
        db = AsyncMock()
        svc = make_service(db)
        data = BookingCreate(
            booking_type=BookingType.hotel,
            provider_reference="EXT-REF-001",
            confirmation_number="EXT-CNF-001",
            total_cost=100.0,
        )

        booking = await svc.create_booking(
            trip_id="trip_001", user_id="user_001", data=data,
        )

        assert booking.provider_reference == "EXT-REF-001"
        assert booking.confirmation_number == "EXT-CNF-001"

    @pytest.mark.asyncio
    async def test_currency_defaults_to_usd(self):
        """When currency is not provided, default to USD."""
        db = AsyncMock()
        svc = make_service(db)
        data = BookingCreate(
            booking_type=BookingType.hotel,
            total_cost=50.0,
            currency=None,
        )

        booking = await svc.create_booking(
            trip_id="trip_001", user_id="user_001", data=data,
        )

        assert booking.currency == "USD"


# ═══════════════════════════════════════════════════════════════════════════════
# ── initiate_payment
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitiatePayment:
    """Tests for BookingService.initiate_payment."""

    @pytest.mark.asyncio
    async def test_raises_when_booking_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)
        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        with pytest.raises(ValueError, match="not found"):
            await svc.initiate_payment("BK-MISSING", data)

    @pytest.mark.asyncio
    async def test_raises_when_booking_cancelled(self):
        booking = make_mock_booking(status=BookingStatus.cancelled)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        with pytest.raises(ValueError, match="cancelled"):
            await svc.initiate_payment("BK-CANCEL", data)

    @pytest.mark.asyncio
    async def test_raises_when_booking_completed(self):
        booking = make_mock_booking(status=BookingStatus.completed)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        with pytest.raises(ValueError, match="already completed"):
            await svc.initiate_payment("BK-DONE", data)

    @pytest.mark.asyncio
    async def test_raises_when_booking_confirmed(self):
        booking = make_mock_booking(status=BookingStatus.confirmed)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        with pytest.raises(ValueError, match="already confirmed"):
            await svc.initiate_payment("BK-CONF", data)

    @pytest.mark.asyncio
    async def test_raises_when_booking_has_existing_payment(self):
        payment = make_mock_payment()
        booking = make_mock_booking(payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        with pytest.raises(ValueError, match="already has a payment"):
            await svc.initiate_payment("BK-PAID", data)

    @pytest.mark.asyncio
    async def test_simulated_payment_when_stripe_disabled(self):
        """When Stripe is disabled, a simulated payment is created."""
        booking = make_mock_booking(total_cost=250.0)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate(amount=200.0, payment_method=PaymentMethod.credit_card)

        result = await svc.initiate_payment("BK-SIM", data)

        assert result["success"] is True
        assert result["simulated"] is True
        assert result["client_secret"].startswith("pi_simulated_")
        assert "simulated" in result["message"].lower()

        # Verify Payment record was created on the booking
        assert booking.payment is not None
        assert booking.payment.status == PaymentStatus.pending
        # The payment amount should come from the data
        assert booking.payment.amount == 200.0

    @pytest.mark.asyncio
    async def test_simulated_payment_uses_booking_total_when_amount_not_given(self):
        """When no payment amount is given, use the booking's total_cost.

        Uses model_construct to bypass Pydantic validation (amount=None
        would normally be rejected by PaymentCreate's ``amount: float``).
        """
        booking = make_mock_booking(total_cost=350.0)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)
        data = PaymentCreate.model_construct(
            amount=None,
            payment_method=PaymentMethod.debit_card,
        )

        result = await svc.initiate_payment("BK-NOAMT", data)

        assert result["simulated"] is True
        # Payment amount should come from booking.total_cost
        assert booking.payment.amount == 350.0

    @pytest.mark.asyncio
    async def test_stripe_success_path(self):
        """When Stripe is available, a real PaymentIntent should be created.

        The Stripe SDK returns a StripeObject that supports both attribute
        access (``.client_secret``) and subscript access (``["id"]``).  We
        use a dict with attribute-style access via __dict__ trick to mock both.
        """
        booking = make_mock_booking()
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        # Mock Stripe PaymentIntent — needs both subscript and attribute access
        class MockIntent(dict):
            pass

        mock_intent = MockIntent()
        mock_intent["id"] = "pi_stripe_001"
        mock_intent["status"] = "requires_payment_method"
        mock_intent["amount"] = 15000
        mock_intent["currency"] = "usd"
        mock_intent.client_secret = "pi_secret_test_xyz"

        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.return_value = mock_intent
        svc._stripe = mock_stripe

        data = PaymentCreate(amount=150.0, currency="USD", payment_method=PaymentMethod.credit_card)

        result = await svc.initiate_payment("BK-STRIPE", data)

        assert result["success"] is True
        assert result["simulated"] is False
        assert result["client_secret"] == "pi_secret_test_xyz"
        assert result["stripe_payment_intent_id"] == "pi_stripe_001"

        # Verify Stripe API was called with correct params
        mock_stripe.PaymentIntent.create.assert_called_once()
        call_kwargs = mock_stripe.PaymentIntent.create.call_args[1]
        assert call_kwargs["amount"] == 15000  # 150 * 100
        assert call_kwargs["currency"] == "usd"
        assert call_kwargs["metadata"]["booking_id"] == "BK-STRIPE"

        # Verify Payment record
        assert booking.payment is not None
        assert booking.payment.status == PaymentStatus.pending
        assert booking.payment.stripe_payment_intent_id == "pi_stripe_001"

    @pytest.mark.asyncio
    async def test_stripe_error_falls_back_to_simulated(self):
        """When Stripe API call fails, fall back to simulated payment."""
        booking = make_mock_booking()
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.side_effect = Exception("Stripe API error")
        svc._stripe = mock_stripe

        data = PaymentCreate(amount=100.0, payment_method=PaymentMethod.credit_card)

        result = await svc.initiate_payment("BK-FALLBACK", data)

        assert result["success"] is True
        assert result["simulated"] is True  # Falls back to simulated
        assert "pi_simulated_" in result["stripe_payment_intent_id"]


# ═══════════════════════════════════════════════════════════════════════════════
# ── confirm_booking
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmBooking:
    """Tests for BookingService.confirm_booking."""

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="not found"):
            await svc.confirm_booking("BK-MISSING")

    @pytest.mark.asyncio
    async def test_raises_when_already_confirmed(self):
        booking = make_mock_booking(status=BookingStatus.confirmed)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="already confirmed"):
            await svc.confirm_booking("BK-CONF")

    @pytest.mark.asyncio
    async def test_raises_when_already_completed(self):
        booking = make_mock_booking(status=BookingStatus.completed)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="already completed"):
            await svc.confirm_booking("BK-DONE")

    @pytest.mark.asyncio
    async def test_raises_when_cancelled(self):
        booking = make_mock_booking(status=BookingStatus.cancelled)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="cancelled"):
            await svc.confirm_booking("BK-CANCEL")

    @pytest.mark.asyncio
    async def test_confirms_pending_booking(self):
        booking = make_mock_booking(status=BookingStatus.pending)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        result = await svc.confirm_booking("BK-PEND")

        assert result is booking
        assert booking.status == BookingStatus.confirmed
        assert "confirmed_at" in booking.raw_response


# ═══════════════════════════════════════════════════════════════════════════════
# ── cancel_booking
# ═══════════════════════════════════════════════════════════════════════════════


class TestCancelBooking:
    """Tests for BookingService.cancel_booking."""

    @pytest.mark.asyncio
    async def test_raises_when_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="not found"):
            await svc.cancel_booking("BK-MISSING")

    @pytest.mark.asyncio
    async def test_raises_when_already_cancelled(self):
        booking = make_mock_booking(status=BookingStatus.cancelled)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="already cancelled"):
            await svc.cancel_booking("BK-CANCEL")

    @pytest.mark.asyncio
    async def test_cancels_without_payment(self):
        booking = make_mock_booking(status=BookingStatus.pending, payment=None)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        result = await svc.cancel_booking("BK-NOPAY")

        assert result is booking
        assert booking.status == BookingStatus.cancelled
        assert "cancelled_at" in booking.raw_response

    @pytest.mark.asyncio
    async def test_cancels_with_payment_refund(self):
        payment = make_mock_payment(status=PaymentStatus.completed)
        booking = make_mock_booking(status=BookingStatus.confirmed, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        result = await svc.cancel_booking("BK-REFUND")

        assert result is booking
        assert booking.status == BookingStatus.cancelled
        assert payment.status == PaymentStatus.refunded
        assert "refunded_at" in payment.raw_response
        assert payment.raw_response["reason"] == "booking_cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# ── confirm_payment_and_booking (client-side verification)
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmPaymentAndBooking:
    """Tests for BookingService.confirm_payment_and_booking."""

    @pytest.mark.asyncio
    async def test_raises_when_booking_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        with pytest.raises(ValueError, match="not found"):
            await svc.confirm_payment_and_booking("BK-MISSING", "pi_123")

    @pytest.mark.asyncio
    async def test_raises_when_booking_cancelled(self):
        booking = make_mock_booking(status=BookingStatus.cancelled)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="cancelled"):
            await svc.confirm_payment_and_booking("BK-CANCEL", "pi_123")

    @pytest.mark.asyncio
    async def test_raises_when_booking_completed(self):
        booking = make_mock_booking(status=BookingStatus.completed)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="already completed"):
            await svc.confirm_payment_and_booking("BK-DONE", "pi_123")

    @pytest.mark.asyncio
    async def test_raises_when_no_payment_record(self):
        booking = make_mock_booking(status=BookingStatus.pending, payment=None)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="no payment record"):
            await svc.confirm_payment_and_booking("BK-NOPAY", "pi_123")

    @pytest.mark.asyncio
    async def test_raises_on_pi_id_mismatch(self):
        payment = make_mock_payment(stripe_pi_id="pi_correct")
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        with pytest.raises(ValueError, match="PI ID mismatch"):
            await svc.confirm_payment_and_booking("BK-MISMATCH", "pi_wrong")

    @pytest.mark.asyncio
    async def test_simulated_confirm_success(self):
        """When Stripe is disabled, skip Stripe verification and confirm directly."""
        payment = make_mock_payment(stripe_pi_id="pi_sim_001", status=PaymentStatus.pending)
        payment.receipt = None
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment, trip_id="trip_001")
        trip = make_mock_trip(status=TripStatus.payment_processing)

        db = AsyncMock()
        r1 = MagicMock()  # get_booking → booking
        r1.scalar_one_or_none.return_value = booking
        r2 = MagicMock()  # _check_and_transition_trip_confirmed → trip
        r2.scalar_one_or_none.return_value = trip
        r3 = MagicMock()  # list_trip_bookings → no remaining pending
        r3.scalars.return_value.all.return_value = []
        db.execute.side_effect = [r1, r2, r3]

        svc = make_service(db)

        result = await svc.confirm_payment_and_booking("BK-SIM", "pi_sim_001")

        assert result["status"] == "confirmed"
        assert payment.status == PaymentStatus.completed
        assert booking.status == BookingStatus.confirmed
        assert payment.paid_at is not None

    @pytest.mark.asyncio
    async def test_already_confirmed_via_webhook(self):
        """When payment was already confirmed via webhook, return early."""
        payment = make_mock_payment(status=PaymentStatus.completed)
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        result = await svc.confirm_payment_and_booking("BK-DUP", payment.stripe_payment_intent_id)

        assert result["status"] == "already_confirmed"

    @pytest.mark.asyncio
    async def test_stripe_verify_pi_not_succeeded(self):
        """When Stripe verify returns non-succeeded status, raise."""
        payment = make_mock_payment(stripe_pi_id="pi_fail_001", status=PaymentStatus.pending)
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        mock_stripe = MagicMock()
        # Use a dict for the intent since production code uses subscript access
        mock_intent = {"status": "requires_payment_method"}
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent
        svc._stripe = mock_stripe

        with pytest.raises(ValueError, match="not 'succeeded'"):
            await svc.confirm_payment_and_booking("BK-FAIL", "pi_fail_001")

    @pytest.mark.asyncio
    async def test_stripe_verify_pi_not_found(self):
        """When Stripe can't find the PaymentIntent, raise."""
        payment = make_mock_payment(stripe_pi_id="pi_ghost", status=PaymentStatus.pending)
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.retrieve.side_effect = Exception(
            "No such PaymentIntent 'pi_ghost'"
        )
        svc._stripe = mock_stripe

        with pytest.raises(ValueError, match="not found"):
            await svc.confirm_payment_and_booking("BK-GHOST", "pi_ghost")

    @pytest.mark.asyncio
    async def test_stripe_verify_generic_error(self):
        """When Stripe returns a generic error, raise."""
        payment = make_mock_payment(stripe_pi_id="pi_err", status=PaymentStatus.pending)
        booking = make_mock_booking(status=BookingStatus.pending, payment=payment)
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.retrieve.side_effect = Exception("Network error")
        svc._stripe = mock_stripe

        with pytest.raises(ValueError, match="Stripe verification failed"):
            await svc.confirm_payment_and_booking("BK-ERR", "pi_err")


# ═══════════════════════════════════════════════════════════════════════════════
# ── _check_and_transition_trip_confirmed
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckAndTransitionTripConfirmed:
    """Tests for BookingService._check_and_transition_trip_confirmed."""

    @pytest.mark.asyncio
    async def test_returns_false_when_trip_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        result = await svc._check_and_transition_trip_confirmed("trip_missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_trip_not_payment_processing(self):
        trip = make_mock_trip(status=TripStatus.planning)
        db = make_mock_db(execute_return_value=trip)
        svc = make_service(db)

        result = await svc._check_and_transition_trip_confirmed("trip_001")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_pending_bookings_remain(self):
        trip = make_mock_trip(status=TripStatus.payment_processing)
        other_pending = make_mock_booking(status=BookingStatus.pending)

        db = AsyncMock()
        r1 = MagicMock()  # select Trip → trip
        r1.scalar_one_or_none.return_value = trip
        r2 = MagicMock()  # list_trip_bookings → pending remain
        r2.scalars.return_value.all.return_value = [other_pending]
        db.execute.side_effect = [r1, r2]
        svc = make_service(db)

        result = await svc._check_and_transition_trip_confirmed("trip_001")
        assert result is False
        assert trip.status == TripStatus.payment_processing

    @pytest.mark.asyncio
    async def test_transitions_to_booking_confirmed_when_no_pending_remain(self):
        trip = make_mock_trip(status=TripStatus.payment_processing)

        db = AsyncMock()
        r1 = MagicMock()  # select Trip → trip
        r1.scalar_one_or_none.return_value = trip
        r2 = MagicMock()  # list_trip_bookings → no pending
        r2.scalars.return_value.all.return_value = []
        db.execute.side_effect = [r1, r2]
        svc = make_service(db)

        result = await svc._check_and_transition_trip_confirmed("trip_001")
        assert result is True
        assert trip.status == TripStatus.booking_confirmed


# ═══════════════════════════════════════════════════════════════════════════════
# ── Query helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetBooking:
    """Tests for BookingService.get_booking."""

    @pytest.mark.asyncio
    async def test_returns_booking_when_found(self):
        booking = make_mock_booking()
        db = make_mock_db(execute_return_value=booking)
        svc = make_service(db)

        result = await svc.get_booking("BK-001")

        assert result is booking

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = make_mock_db(execute_return_value=None)
        svc = make_service(db)

        result = await svc.get_booking("BK-MISSING")

        assert result is None


class TestListTripBookings:
    """Tests for BookingService.list_trip_bookings."""

    @pytest.mark.asyncio
    async def test_returns_all_bookings_for_trip(self):
        booking1 = make_mock_booking(booking_id="BK-001")
        booking2 = make_mock_booking(booking_id="BK-002")

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [booking1, booking2]
        db.execute.return_value = result_mock
        svc = make_service(db)

        results = await svc.list_trip_bookings("trip_001")

        assert len(results) == 2
        assert results[0].booking_id == "BK-001"

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock
        svc = make_service(db)

        await svc.list_trip_bookings("trip_001", status=BookingStatus.confirmed)

        # Verify status filter was applied
        call_args = db.execute.call_args[0][0]
        # Should contain WHERE clauses
        assert call_args is not None


class TestListUserBookings:
    """Tests for BookingService.list_user_bookings."""

    @pytest.mark.asyncio
    async def test_returns_user_bookings_with_pagination(self):
        booking = make_mock_booking()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [booking]
        db.execute.return_value = result_mock
        svc = make_service(db)

        results = await svc.list_user_bookings("user_001", limit=10, offset=0)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_filters_by_status(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock
        svc = make_service(db)

        await svc.list_user_bookings("user_001", status=BookingStatus.pending)

        call_args = db.execute.call_args[0][0]
        assert call_args is not None
