import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../../bookings/data/repository/booking_repository.dart';
import '../../data/datasource/payment_service.dart';

const _kPollInterval = Duration(seconds: 2);
const _kPollTimeout = Duration(seconds: 30);

// ── Events ─────────────────────────────────────────────────────────────────

/// Events for the booking payment flow.
abstract class BookingPaymentEvent extends Equatable {
  const BookingPaymentEvent();

  @override
  List<Object?> get props => [];
}

/// Start payment for a single booking.
class PaySingleBooking extends BookingPaymentEvent {
  final String bookingId;
  final String paymentMethod;
  final double amount;
  final String? currency;

  const PaySingleBooking({
    required this.bookingId,
    required this.paymentMethod,
    required this.amount,
    this.currency,
  });

  @override
  List<Object?> get props => [bookingId, paymentMethod, amount, currency];
}

/// Reset the payment state (e.g., after navigating away).
class PaymentSheetOpened extends BookingPaymentEvent {
  const PaymentSheetOpened();
}

class ResetPayment extends BookingPaymentEvent {
  const ResetPayment();
}

// ── States ────────────────────────────────────────────────────────────────

/// State for the booking payment flow.
abstract class BookingPaymentState extends Equatable {
  const BookingPaymentState();

  @override
  List<Object?> get props => [];
}

/// Initial state — no payment in progress.
class BookingPaymentInitial extends BookingPaymentState {
  const BookingPaymentInitial();
}

/// Payment is being initiated (calling the backend).
class BookingPaymentInitiating extends BookingPaymentState {
  const BookingPaymentInitiating();
}

/// Stripe Payment Sheet is open — user is entering card details.
class BookingPaymentSheetOpen extends BookingPaymentState {
  const BookingPaymentSheetOpen();
}

/// Payment succeeded on Stripe, waiting for webhook to confirm booking.
class BookingPaymentPolling extends BookingPaymentState {
  final int secondsElapsed;

  const BookingPaymentPolling({this.secondsElapsed = 0});

  @override
  List<Object?> get props => [secondsElapsed];
}

/// Payment succeeded.
class BookingPaymentSuccess extends BookingPaymentState {
  final String bookingId;
  final String? paymentId;
  final String? receiptNumber;
  final bool simulated;
  final String? message;

  const BookingPaymentSuccess({
    required this.bookingId,
    this.paymentId,
    this.receiptNumber,
    this.simulated = false,
    this.message,
  });

  @override
  List<Object?> get props => [bookingId, paymentId, receiptNumber, simulated, message];
}

/// Payment failed.
class BookingPaymentFailure extends BookingPaymentState {
  final String error;
  final int? initiatedCount;
  final int? completedCount;

  const BookingPaymentFailure({
    required this.error,
    this.initiatedCount,
    this.completedCount,
  });

  @override
  List<Object?> get props => [error, initiatedCount, completedCount];
}

// ── Cubit ─────────────────────────────────────────────────────────────────

/// Orchestrates the full Stripe Payment Sheet flow for a booking.
///
/// Flow:
/// 1. Calls the backend to initiate payment → gets client_secret
/// 2. Opens the Stripe Payment Sheet for card entry
/// 3. On success: emits [BookingPaymentSuccess]
/// 4. On failure: emits [BookingPaymentFailure]
class BookingPaymentCubit extends Cubit<BookingPaymentState> {
  final BookingRepository _bookingRepo;
  final PaymentService _paymentService;

  BookingPaymentCubit({
    required BookingRepository bookingRepo,
    required PaymentService paymentService,
  })  : _bookingRepo = bookingRepo,
        _paymentService = paymentService,
        super(const BookingPaymentInitial());

  /// Pay for a single booking via the Stripe Payment Sheet.
  Future<void> paySingleBooking(PaySingleBooking event) async {
    emit(const BookingPaymentInitiating());

    final result = await _paymentService.processBookingPayment(
      payFuture: () async {
        emit(const BookingPaymentSheetOpen());
        return await _bookingRepo.initiateBookingPayment(
          bookingId: event.bookingId,
          paymentMethod: event.paymentMethod,
          amount: event.amount,
          currency: event.currency,
        );
      },
      bookingId: event.bookingId,
    );

    if (result.success) {
      // If we have a stripe payment intent and it's not simulated,
      // try server-side verification first, fall back to polling
      if (result.stripePaymentIntentId != null && !result.simulated) {
        final confirmed = await _confirmViaApiOrPoll(
          bookingId: event.bookingId,
          stripePaymentIntentId: result.stripePaymentIntentId!,
        );
        if (!confirmed) {
          emit(BookingPaymentFailure(
            error: 'Payment went through successfully, but booking '
                'confirmation timed out. '
                'Your card has been charged — the booking will be '
                'confirmed automatically once the webhook arrives. '
                'Please check your bookings later.',
          ));
          return;
        }
      }
      emit(BookingPaymentSuccess(
        bookingId: result.bookingId,
        paymentId: result.paymentId,
        simulated: result.simulated,
        message: result.message,
      ));
    } else {
      emit(BookingPaymentFailure(
        error: result.error ?? 'Payment failed unexpectedly.',
      ));
    }
  }

  /// Try server-side verification first (confirm-after-payment), then fall back to polling.
  /// Returns true if booking was confirmed, false if not.
  Future<bool> _confirmViaApiOrPoll({
    required String bookingId,
    required String stripePaymentIntentId,
  }) async {
    // Step 1: Try server-side verification — backend checks Stripe directly
    try {
      await _bookingRepo.confirmAfterPayment(
        bookingId: bookingId,
        stripePaymentIntentId: stripePaymentIntentId,
      );
      return true; // Booking confirmed immediately!
    } catch (e) {
      print('[BookingPaymentCubit] confirm-after-payment failed: $e — falling back to polling');
    }

    // Step 2: Fall back to polling for webhook confirmation
    return await _pollForBookingConfirmation(bookingId);
  }

  /// Poll GET /bookings/{id} until the booking is confirmed or timeout.
  /// Returns true if confirmed, false if timed out.
  Future<bool> _pollForBookingConfirmation(String bookingId) async {
    final stopwatch = Stopwatch()..start();
    while (stopwatch.elapsed < _kPollTimeout) {
      emit(BookingPaymentPolling(
        secondsElapsed: stopwatch.elapsed.inSeconds,
      ));
      await Future.delayed(_kPollInterval);
      try {
        final booking = await _bookingRepo.getBooking(bookingId);
        if (booking.status == 'confirmed' || booking.status == 'completed') {
          return true; // Booking confirmed!
        }
      } catch (_) {
        // Network error during poll — keep trying
      }
    }
    // Timeout — booking wasn't confirmed by webhook
    return false;
  }

  /// Reset to initial state.
  void reset() => emit(const BookingPaymentInitial());
}
