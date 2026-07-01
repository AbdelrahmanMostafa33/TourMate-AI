import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:equatable/equatable.dart';

import '../../../bookings/data/repository/booking_repository.dart';
import '../../data/datasource/payment_service.dart';

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

  const BookingPaymentFailure({
    required this.error,
  });

  @override
  List<Object?> get props => [error];
}

// ── Cubit ─────────────────────────────────────────────────────────────────

/// Orchestrates the full Stripe Payment Sheet flow for a booking.
///
/// Flow:
/// 1. Calls the backend to initiate payment → gets client_secret
/// 2. Opens the Stripe Payment Sheet for card entry
/// 3. On success: calls confirm-after-payment → emits [BookingPaymentSuccess]
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
      // verify with confirm-after-payment (backend checks Stripe directly).
      if (result.stripePaymentIntentId != null && !result.simulated) {
        try {
          await _bookingRepo.confirmAfterPayment(
            bookingId: event.bookingId,
            stripePaymentIntentId: result.stripePaymentIntentId!,
          );
        } catch (e) {
          emit(BookingPaymentFailure(
            error: 'Payment went through successfully, but booking '
                'confirmation failed. '
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

  /// Reset to initial state.
  void reset() => emit(const BookingPaymentInitial());
}
