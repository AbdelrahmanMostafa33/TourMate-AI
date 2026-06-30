import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repository/booking_repository.dart';

// ── State ──────────────────────────────────────────────────────────────────────

enum BookingPaymentStatus { initial, initiating, sheetOpen, polling, success, failure }

class BookingPaymentState {
  final BookingPaymentStatus status;
  final String? error;
  final String? bookingId;
  final String? paymentId;
  final String? clientSecret;
  final bool simulated;
  final String? message;
  final int pollAttempts;

  const BookingPaymentState({
    this.status = BookingPaymentStatus.initial,
    this.error,
    this.bookingId,
    this.paymentId,
    this.clientSecret,
    this.simulated = false,
    this.message,
    this.pollAttempts = 0,
  });

  BookingPaymentState copyWith({
    BookingPaymentStatus? status,
    String? error,
    String? bookingId,
    String? paymentId,
    String? clientSecret,
    bool? simulated,
    String? message,
    int? pollAttempts,
  }) {
    return BookingPaymentState(
      status: status ?? this.status,
      error: error ?? this.error,
      bookingId: bookingId ?? this.bookingId,
      paymentId: paymentId ?? this.paymentId,
      clientSecret: clientSecret ?? this.clientSecret,
      simulated: simulated ?? this.simulated,
      message: message ?? this.message,
      pollAttempts: pollAttempts ?? this.pollAttempts,
    );
  }
}

// ── Cubit ──────────────────────────────────────────────────────────────────────

class BookingPaymentCubit extends Cubit<BookingPaymentState> {
  final BookingRepository _repository;

  BookingPaymentCubit(this._repository) : super(const BookingPaymentState());

  /// Start the payment flow: initiate -> sheet -> poll
  Future<void> startPayment({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) async {
    emit(state.copyWith(status: BookingPaymentStatus.initiating));

    try {
      // Step 1: Try initiate-payment first (async flow)
      Map<String, dynamic> result;
      try {
        result = await _repository.initiateBookingPayment(
          bookingId: bookingId,
          paymentMethod: paymentMethod,
          currency: currency,
        );
      } catch (e) {
        // Fallback: use synchronous pay endpoint if initiate is unavailable
        result = await _repository.payBooking(
          bookingId: bookingId,
          paymentMethod: paymentMethod,
          currency: currency,
        );
      }

      final clientSecret = result['client_secret'] as String?;
      final isSimulated = result['simulated'] as bool? ?? false;
      final paymentId = result['payment_id'] as String?;
      final success = result['success'] as bool? ?? false;
      final message = result['message'] as String? ?? 'Payment initiated.';

      if (!success) {
        emit(state.copyWith(
          status: BookingPaymentStatus.failure,
          error: message,
        ));
        return;
      }

      // Step 2: Emit sheet-open state
      emit(state.copyWith(
        status: BookingPaymentStatus.sheetOpen,
        clientSecret: clientSecret,
        bookingId: bookingId,
        paymentId: paymentId,
        simulated: isSimulated,
        message: message,
      ));

      // Step 3: If simulated, skip polling and go straight to success
      if (isSimulated) {
        emit(state.copyWith(
          status: BookingPaymentStatus.success,
          message: 'Payment completed (simulated).',
        ));
        return;
      }

      // Start polling for real webhook flow
      emit(state.copyWith(status: BookingPaymentStatus.polling, pollAttempts: 0));
      await _pollForConfirmation(bookingId);

    } catch (e) {
      emit(state.copyWith(
        status: BookingPaymentStatus.failure,
        error: e.toString(),
      ));
    }
  }

  Future<void> _pollForConfirmation(String bookingId) async {
    const maxAttempts = 15; // 30 seconds at 2s interval

    for (int attempt = 1; attempt <= maxAttempts; attempt++) {
      await Future.delayed(const Duration(seconds: 2));

      try {
        final booking = await _repository.getBooking(bookingId);
        final status = booking.status;

        if (status == 'confirmed' || status == 'completed') {
          emit(state.copyWith(
            status: BookingPaymentStatus.success,
            pollAttempts: attempt,
            message: 'Booking confirmed via webhook.',
          ));
          return;
        }

        if (status == 'cancelled' || status == 'failed') {
          emit(state.copyWith(
            status: BookingPaymentStatus.failure,
            pollAttempts: attempt,
            error: 'Booking ended with status: $status',
          ));
          return;
        }

        emit(state.copyWith(pollAttempts: attempt));
      } catch (e) {
        // Network error during poll - retry
        emit(state.copyWith(pollAttempts: attempt));
      }
    }

    // Timed out
    emit(state.copyWith(
      status: BookingPaymentStatus.failure,
      pollAttempts: maxAttempts,
      error: 'Payment confirmation timed out. Check your bookings.',
    ));
  }

  /// Reset to initial state
  void reset() {
    emit(const BookingPaymentState());
  }
}
