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
  final String? currency;

  const PaySingleBooking({
    required this.bookingId,
    required this.paymentMethod,
    this.currency,
  });

  @override
  List<Object?> get props => [bookingId, paymentMethod, currency];
}

/// Start payment for all pending bookings in a trip.
class PayAllBookings extends BookingPaymentEvent {
  final String tripId;
  final String paymentMethod;
  final String? currency;

  const PayAllBookings({
    required this.tripId,
    required this.paymentMethod,
    this.currency,
  });

  @override
  List<Object?> get props => [tripId, paymentMethod, currency];
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

    // Try initiate-payment first (async flow — opens Stripe Payment Sheet).
    // Falls back to payBooking (sync flow) if initiate fails.
    final result = await _paymentService.processBookingPayment(
      payFuture: () async {
        emit(const BookingPaymentSheetOpen());
        try {
          return await _bookingRepo.initiateBookingPayment(
            bookingId: event.bookingId,
            paymentMethod: event.paymentMethod,
            currency: event.currency,
          );
        } catch (_) {
          // Fallback: initiate not available, use sync pay endpoint
          return await _bookingRepo.payBooking(
            bookingId: event.bookingId,
            paymentMethod: event.paymentMethod,
            currency: event.currency,
          );
        }
      },
      bookingId: event.bookingId,
    );

    if (result.success) {
      // If we have a stripe payment intent, start polling for webhook confirmation
      if (result.stripePaymentIntentId != null && !result.simulated) {
        final confirmed = await _pollForBookingConfirmation(event.bookingId);
        if (!confirmed) {
          emit(BookingPaymentFailure(
            error: 'Booking confirmation timed out. Please check your bookings.',
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

  /// Pay all pending bookings in a trip via the bulk endpoint (synchronous).
  /// Note: Bulk pay does NOT use the Payment Sheet (no client_secret).
  Future<void> payAllBookings(PayAllBookings event) async {
    emit(const BookingPaymentInitiating());

    try {
      final response = await _bookingRepo.payTripPackage(
        tripId: event.tripId,
        paymentMethod: event.paymentMethod,
        currency: event.currency,
      );

      if (response.paidBookings.isNotEmpty) {
        emit(BookingPaymentSuccess(
          bookingId: event.tripId,
          simulated: false  // TripPackagePaymentResponse has no simulated field,
        ));
      } else {
        final reasons = response.skippedBookings
            .map((s) => s.reason)
            .whereType<String>()
            .join('; ');
        emit(BookingPaymentFailure(
          error: 'No bookings were paid. $reasons',
        ));
      }
    } catch (e) {
      emit(BookingPaymentFailure(error: e.toString()));
    }
  }

  /// Initiate async payments for all pending bookings via the async
  /// initiate-pay-all endpoint, then open the Stripe Payment Sheet for
  /// each non-simulated booking sequentially.
  ///
  /// Flow:
  /// 1. Calls initiateTripPackagePayment to create PaymentIntents for all
  ///    pending bookings, getting client_secret values for each.
  /// 2. Iterates through each initiated booking:
  ///    - Simulated/no client_secret: counts as completed immediately.
  ///    - Real: opens Stripe Payment Sheet, polls for webhook confirmation.
  /// 3. Emits success/failure after all bookings are processed.
  Future<void> initiatePayAllBookings(PayAllBookings event) async {
    emit(const BookingPaymentInitiating());

    try {
      final response = await _bookingRepo.initiateTripPackagePayment(
        tripId: event.tripId,
        paymentMethod: event.paymentMethod,
        currency: event.currency,
      );

      if (response.initiatedBookings.isEmpty) {
        emit(const BookingPaymentFailure(
          error: 'No bookings were initiated.',
        ));
        return;
      }

      emit(const BookingPaymentSheetOpen());

      int completed = 0;
      final total = response.initiatedBookings.length;
      final List<String> errors = [];

      // Process each initiated booking sequentially
      for (final item in response.initiatedBookings) {
        if (item.simulated || item.clientSecret == null || item.clientSecret!.isEmpty) {
          // Simulated or no client_secret — payment already done
          completed++;
          continue;
        }

        try {
          // Open Stripe Payment Sheet for this booking
          await _paymentService.payWithStripeSheet(
            clientSecret: item.clientSecret!,
          );

          // Poll for webhook confirmation
          if (item.stripePaymentIntentId != null) {
            final confirmed = await _pollForBookingConfirmation(item.bookingId);
            if (!confirmed) {
              errors.add('Booking ${item.bookingId}: confirmation timed out');
              continue;
            }
          }
          completed++;
        } catch (e) {
          errors.add('Booking ${item.bookingId}: $e');
          // Continue with next booking
        }
      }

      if (completed > 0) {
        emit(BookingPaymentSuccess(
          bookingId: event.tripId,
          simulated: completed == total,
          message: errors.isEmpty
              ? '$completed of $total payments completed.'
              : '$completed of $total completed (${errors.length} failed: ${errors.join('; ')})',
        ));
      } else {
        emit(BookingPaymentFailure(
          error: errors.isNotEmpty
              ? errors.join('; ')
              : 'All payment attempts failed.',
          initiatedCount: total,
          completedCount: completed,
        ));
      }
    } catch (e) {
      emit(BookingPaymentFailure(error: e.toString()));
    }
  }

  /// Reset to initial state.
  void reset() => emit(const BookingPaymentInitial());
}
