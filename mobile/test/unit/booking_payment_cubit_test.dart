import 'package:flutter_test/flutter_test.dart';

import 'package:tourmate/features/bookings/data/repository/booking_repository.dart';
import 'package:tourmate/features/bookings/data/models/booking_models.dart';
import 'package:tourmate/features/payments/data/datasource/payment_service.dart';
import 'package:tourmate/features/payments/presentation/cubit/booking_payment_cubit.dart';

// ── Helpers ────────────────────────────────────────────────────────────────

Future<Map<String, dynamic>> _successInitiateResult({bool simulated = false}) async {
  return {
    'success': true,
    'simulated': simulated,
    'client_secret': simulated ? null : 'pi_001_secret_abc123',
    'stripe_payment_intent_id': simulated ? null : 'pi_001',
    'payment_id': 'pay-001',
    'message': simulated ? 'Simulated' : 'Payment initiated',
  };
}

// ── Fake repository (no mockito needed) ────────────────────────────────────

class FakeBookingRepository implements BookingRepository {
  late Future<Map<String, dynamic>> Function({
    required String bookingId,
    required String paymentMethod,
    required double amount,
    String? currency,
  }) initiatePaymentStub;

  int initiatePaymentCallCount = 0;

  FakeBookingRepository() {
    initiatePaymentStub = ({required bookingId, required paymentMethod, required amount, currency}) async =>
        <String, dynamic>{'success': true, 'simulated': true};
  }

  @override
  Future<Map<String, dynamic>> initiateBookingPayment({
    required String bookingId,
    required String paymentMethod,
    required double amount,
    String? currency,
  }) async {
    initiatePaymentCallCount++;
    return initiatePaymentStub(
        bookingId: bookingId, paymentMethod: paymentMethod, amount: amount, currency: currency);
  }

  @override
  Future<List<BookingResponse>> listTripBookings(String tripId, {String? status}) =>
      throw UnimplementedError('Not used in these tests');

  @override
  Future<Map<String, dynamic>> confirmAfterPayment({
    required String bookingId,
    required String stripePaymentIntentId,
  }) async {
    return {'booking_id': bookingId, 'status': 'confirmed'};
  }
}

// ── Fake payment service ─────────────────────────────────────────────────

class FakePaymentService extends PaymentService {
  @override
  Future<bool> payWithStripeSheet({
    required String clientSecret,
    String merchantDisplayName = 'TourMate',
  }) async {
    return true; // Simulate successful payment sheet
  }
}

// ── Tests ──────────────────────────────────────────────────────────────────

void main() {
  group('BookingPaymentCubit', () {
    late FakeBookingRepository repository;
    late FakePaymentService paymentService;
    late BookingPaymentCubit cubit;

    setUp(() {
      repository = FakeBookingRepository();
      paymentService = FakePaymentService();
      cubit = BookingPaymentCubit(
        bookingRepo: repository,
        paymentService: paymentService,
      );
    });

    tearDown(() async {
      await cubit.close();
    });

    test('initial state is BookingPaymentInitial', () {
      expect(cubit.state, isA<BookingPaymentInitial>());
    });

    test('paySingleBooking with simulated payment -> success', () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, required amount, currency}) async =>
          _successInitiateResult(simulated: true);

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentInitiating>(),
          isA<BookingPaymentSheetOpen>(),
          isA<BookingPaymentSuccess>()
              .having((s) => s.simulated, 'simulated', true),
        ]),
      );

      cubit.paySingleBooking(
        PaySingleBooking(
          bookingId: 'bk-001',
          paymentMethod: 'credit_card',
          amount: 150.0,
          currency: 'usd',
        ),
      );

      await matcher;
      expect(repository.initiatePaymentCallCount, 1);
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('paySingleBooking throws exception -> failure state', () async {
      repository.initiatePaymentStub = ({
        required bookingId,
        required paymentMethod,
        required amount,
        currency,
      }) async =>
          Future.error(Exception('Payment service unavailable'));

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentInitiating>(),
          isA<BookingPaymentSheetOpen>(),
          isA<BookingPaymentFailure>()
              .having((s) => s.error, 'error',
                  predicate((String e) => e.contains('Payment service unavailable'))),
        ]),
      );

      cubit.paySingleBooking(
        PaySingleBooking(
          bookingId: 'bk-001',
          paymentMethod: 'credit_card',
          amount: 150.0,
          currency: 'usd',
        ),
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('reset returns to initial state', () {
      cubit.reset();
      expect(cubit.state, isA<BookingPaymentInitial>());
    });
  });
}
