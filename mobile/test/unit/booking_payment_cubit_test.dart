import 'package:flutter_test/flutter_test.dart';

import 'package:tourmate/features/bookings/data/repository/booking_repository.dart';
import 'package:tourmate/features/bookings/data/models/booking_models.dart';
import 'package:tourmate/features/payments/data/datasource/payment_service.dart';
import 'package:tourmate/features/payments/presentation/cubit/booking_payment_cubit.dart';

// ── Helpers ────────────────────────────────────────────────────────────────

BookingResponse _defaultBooking({String status = 'pending'}) {
  return BookingResponse(
    bookingId: 'bk-001',
    tripId: 'trip-001',
    userId: 'user-001',
    bookingType: 'hotel',
    status: status,
    totalCost: 150.0,
    currency: 'USD',
    payment: null,
    createdAt: null,
  );
}

InitiatePackagePaymentResponse _defaultInitiateResponse({bool simulated = false}) {
  return InitiatePackagePaymentResponse(
    tripId: 'trip-001',
    currency: 'USD',
    initiatedCount: 1,
    skippedCount: 0,
    initiatedBookings: [
      InitiatedBookingItem(
        bookingId: 'bk-001',
        paymentId: 'pay-001',
        clientSecret: simulated ? null : 'pi_001_secret_abc123',
        stripePaymentIntentId: simulated ? null : 'pi_001',
        simulated: simulated,
        message: simulated ? 'Simulated' : 'Payment initiated',
      ),
    ],
    skippedBookings: [],
  );
}

// ── Fake repository (no mockito needed) ────────────────────────────────────

class FakeBookingRepository implements BookingRepository {
  late Future<Map<String, dynamic>> Function({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) initiatePaymentStub;

  late Future<Map<String, dynamic>> Function({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) payBookingStub;

  late Future<BookingResponse> Function(String bookingId) getBookingStub;

  late Future<InitiatePackagePaymentResponse> Function({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) initiateTripPackagePaymentStub;

  int initiatePaymentCallCount = 0;
  int payBookingCallCount = 0;
  int getBookingCallCount = 0;
  int initiateTripPackagePaymentCallCount = 0;

  FakeBookingRepository() {
    initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
        <String, dynamic>{'success': true, 'simulated': true};
    payBookingStub = ({required bookingId, required paymentMethod, currency}) async =>
        <String, dynamic>{'success': true, 'simulated': true};
    getBookingStub = (String bookingId) async => _defaultBooking();
    initiateTripPackagePaymentStub = ({
      required tripId,
      required paymentMethod,
      currency,
    }) async =>
        _defaultInitiateResponse(simulated: true);
  }

  @override
  Future<Map<String, dynamic>> initiateBookingPayment({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) async {
    initiatePaymentCallCount++;
    return initiatePaymentStub(
        bookingId: bookingId, paymentMethod: paymentMethod, currency: currency);
  }

  @override
  Future<Map<String, dynamic>> payBooking({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) async {
    payBookingCallCount++;
    return payBookingStub(
        bookingId: bookingId, paymentMethod: paymentMethod, currency: currency);
  }

  @override
  Future<BookingResponse> getBooking(String bookingId) async {
    getBookingCallCount++;
    return getBookingStub(bookingId);
  }

  @override
  Future<InitiatePackagePaymentResponse> initiateTripPackagePayment({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) async {
    initiateTripPackagePaymentCallCount++;
    return initiateTripPackagePaymentStub(
        tripId: tripId, paymentMethod: paymentMethod, currency: currency);
  }

  // ── Unused by the payment flow — required by the interface ─────────

  @override
  Future<TripPackageBookingResponse> bookTripPackage(String tripId) =>
      throw UnimplementedError('Not used in these tests');

  @override
  Future<List<BookingResponse>> listTripBookings(String tripId, {String? status}) =>
      throw UnimplementedError('Not used in these tests');

  @override
  Future<TripPackagePaymentResponse> payTripPackage({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) =>
      throw UnimplementedError('Not used in these tests');
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

    test('initiatePayAllBookings with simulated payments -> success',
        () async {
      repository.initiateTripPackagePaymentStub = ({
        required tripId,
        required paymentMethod,
        currency,
      }) async =>
          _defaultInitiateResponse(simulated: true);

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentInitiating>(),
          isA<BookingPaymentSheetOpen>(),
          isA<BookingPaymentSuccess>()
              .having((s) => s.simulated, 'simulated', true),
        ]),
      );

      cubit.initiatePayAllBookings(
        PayAllBookings(
          tripId: 'trip-001',
          paymentMethod: 'credit_card',
          currency: 'usd',
        ),
      );

      await matcher;
      expect(repository.initiateTripPackagePaymentCallCount, 1);
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiatePayAllBookings with no bookings -> failure', () async {
      repository.initiateTripPackagePaymentStub = ({
        required tripId,
        required paymentMethod,
        currency,
      }) async =>
          InitiatePackagePaymentResponse(
            tripId: 'trip-001',
            currency: 'USD',
            initiatedCount: 0,
            skippedCount: 0,
            initiatedBookings: [],
            skippedBookings: [],
          );

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentInitiating>(),
          isA<BookingPaymentFailure>()
              .having((s) => s.error, 'error',
                  predicate((String e) => e.contains('No bookings were initiated'))),
        ]),
      );

      cubit.initiatePayAllBookings(
        PayAllBookings(
          tripId: 'trip-001',
          paymentMethod: 'credit_card',
          currency: 'usd',
        ),
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiatePayAllBookings throws exception -> failure state', () async {
      repository.initiateTripPackagePaymentStub = ({
        required tripId,
        required paymentMethod,
        currency,
      }) async =>
          Future.error(Exception('Payment service unavailable'));

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentInitiating>(),
          isA<BookingPaymentFailure>()
              .having((s) => s.error, 'error',
                  predicate((String e) => e.contains('Payment service unavailable'))),
        ]),
      );

      cubit.initiatePayAllBookings(
        PayAllBookings(
          tripId: 'trip-001',
          paymentMethod: 'credit_card',
          currency: 'usd',
        ),
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('reset returns to initial state', () {
      cubit.initiatePayAllBookings(
        PayAllBookings(
          tripId: 'trip-001',
          paymentMethod: 'credit_card',
          currency: 'usd',
        ),
      );

      // Wait for processing to complete, then reset
      Future(() {
        cubit.reset();
        expect(cubit.state, isA<BookingPaymentInitial>());
      });
    });
  });
}
