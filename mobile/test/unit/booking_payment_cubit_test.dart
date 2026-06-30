import 'package:flutter_test/flutter_test.dart';

import 'package:tourmate/features/bookings/data/repository/booking_repository.dart';
import 'package:tourmate/features/bookings/data/models/booking_models.dart';
import 'package:tourmate/features/bookings/presentation/cubit/booking_payment_cubit.dart';

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

  int initiatePaymentCallCount = 0;
  int payBookingCallCount = 0;
  int getBookingCallCount = 0;

  FakeBookingRepository() {
    initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
        <String, dynamic>{'success': true, 'simulated': true};
    payBookingStub = ({required bookingId, required paymentMethod, currency}) async =>
        <String, dynamic>{'success': true, 'simulated': true};
    getBookingStub = (String bookingId) async => _defaultBooking();
  }

  @override
  Future<Map<String, dynamic>> initiateBookingPayment({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) async {
    initiatePaymentCallCount++;
    final result = await initiatePaymentStub(
        bookingId: bookingId,
        paymentMethod: paymentMethod,
        currency: currency);
    return result;
  }

  @override
  Future<Map<String, dynamic>> payBooking({
    required String bookingId,
    required String paymentMethod,
    String? currency,
  }) async {
    payBookingCallCount++;
    final result = await payBookingStub(
        bookingId: bookingId,
        paymentMethod: paymentMethod,
        currency: currency);
    return result;
  }

  @override
  late Future<InitiatePackagePaymentResponse> Function({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) initiateTripPackagePaymentStub;

  int initiateTripPackagePaymentCallCount = 0;

  Future<InitiatePackagePaymentResponse> initiateTripPackagePayment({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) async {
    initiateTripPackagePaymentCallCount++;
    return initiateTripPackagePaymentStub(
      tripId: tripId,
      paymentMethod: paymentMethod,
      currency: currency,
    );
  }

  @override
  Future<BookingResponse> getBooking(String bookingId) async {
    getBookingCallCount++;
    return getBookingStub(bookingId);
  }

  // ── Unused by the payment flow — required by the interface ─────────

  @override
  Future<TripPackageBookingResponse> bookTripPackage(String tripId) =>
      throw UnimplementedError('Not used in these tests');

  @override
  Future<List<BookingResponse>> listTripBookings(
    String tripId, {
    String? status,
  }) =>
      throw UnimplementedError('Not used in these tests');

  @override
  Future<TripPackagePaymentResponse> payTripPackage({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) =>
      throw UnimplementedError('Not used in these tests');
}

// ── Tests ──────────────────────────────────────────────────────────────────

void main() {
  group('BookingPaymentCubit', () {
    late FakeBookingRepository repository;
    late BookingPaymentCubit cubit;

    setUp(() {
      repository = FakeBookingRepository();
      cubit = BookingPaymentCubit(repository);
    });

    tearDown(() async {
      await cubit.close();
    });

    test('initial state is BookingPaymentStatus.initial', () {
      expect(cubit.state.status, BookingPaymentStatus.initial);
      expect(cubit.state.simulated, false);
      expect(cubit.state.error, isNull);
      expect(cubit.state.pollAttempts, 0);
    });

    test('initiate -> simulated -> immediate success (skips polling)',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          <String, dynamic>{
            'success': true,
            'simulated': true,
            'client_secret': null,
            'payment_id': 'pay_sim_001',
            'message': 'Payment initiated (simulated).',
          };

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.sheetOpen)
              .having((s) => s.simulated, 'simulated', true),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.success)
              .having((s) => s.simulated, 'simulated', true),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;

      expect(repository.initiatePaymentCallCount, 1);
      expect(repository.payBookingCallCount, 0);
      expect(repository.getBookingCallCount, 0);
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiate -> polling -> success (webhook confirms)',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          <String, dynamic>{
            'success': true,
            'simulated': false,
            'client_secret': 'pi_001_secret_abc123',
            'payment_id': 'pay_001',
            'message': 'Payment initiated. Complete via Stripe Payment Sheet.',
          };

      repository.getBookingStub = (String bookingId) async {
        if (repository.getBookingCallCount >= 2) {
          return _defaultBooking(status: 'confirmed');
        }
        return _defaultBooking(status: 'pending');
      };

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.sheetOpen)
              .having((s) => s.clientSecret, 'clientSecret', 'pi_001_secret_abc123'),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.polling)
              .having((s) => s.pollAttempts, 'pollAttempts', 0),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.polling)
              .having((s) => s.pollAttempts, 'pollAttempts', 1),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.success)
              .having((s) => s.message, 'message', 'Booking confirmed via webhook.'),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;

      expect(repository.initiatePaymentCallCount, 1);
      expect(repository.payBookingCallCount, 0);
      expect(repository.getBookingCallCount, greaterThanOrEqualTo(2));
    }, timeout: const Timeout(Duration(seconds: 20)));

    test('initiate throws -> fallback payBooking succeeds',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          Future.error(Exception('initiate endpoint unavailable'));

      repository.payBookingStub = ({required bookingId, required paymentMethod, currency}) async =>
          <String, dynamic>{
            'success': true,
            'simulated': true,
            'client_secret': null,
            'payment_id': 'pay_fallback_001',
            'message': 'Payment processed (fallback).',
          };

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.sheetOpen)
              .having((s) => s.simulated, 'simulated', true),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.success)
              .having((s) => s.message, 'message', 'Payment completed (simulated).'),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;

      expect(repository.initiatePaymentCallCount, 1);
      expect(repository.payBookingCallCount, 1);
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiate -> polling -> failure (booking cancelled)',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          <String, dynamic>{
            'success': true,
            'simulated': false,
            'client_secret': 'pi_002_secret_xyz789',
            'payment_id': 'pay_002',
            'message': 'Payment initiated.',
          };

      repository.getBookingStub = (String bookingId) async =>
          _defaultBooking(status: 'cancelled');

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.sheetOpen),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.polling),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.failure)
              .having((s) => s.error, 'error',
                  predicate((String? e) => e != null && e.contains('cancelled'))),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiate returns success:false -> failure state',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          <String, dynamic>{
            'success': false,
            'simulated': false,
            'client_secret': null,
            'payment_id': null,
            'message': 'Insufficient funds.',
          };

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.failure)
              .having((s) => s.error, 'error',
                  predicate((String? e) => e != null && e.contains('Insufficient funds'))),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('initiate + fallback both throw -> failure state',
        () async {
      repository.initiatePaymentStub = ({required bookingId, required paymentMethod, currency}) async =>
          Future.error(Exception('initiate failed'));

      repository.payBookingStub = ({required bookingId, required paymentMethod, currency}) async =>
          Future.error(Exception('payBooking also failed'));

      final matcher = expectLater(
        cubit.stream,
        emitsInOrder([
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.initiating),
          isA<BookingPaymentState>()
              .having((s) => s.status, 'status', BookingPaymentStatus.failure)
              .having((s) => s.error, 'error',
                  predicate((String? e) => e != null && e.contains('payBooking also failed'))),
        ]),
      );

      await cubit.startPayment(
        bookingId: 'bk-001',
        paymentMethod: 'credit_card',
        currency: 'USD',
      );

      await matcher;
    }, timeout: const Timeout(Duration(seconds: 15)));

    test('reset returns to initial state', () {
      cubit.reset();
      expect(cubit.state.status, BookingPaymentStatus.initial);
      expect(cubit.state.error, isNull);
      expect(cubit.state.pollAttempts, 0);
    });
  });
}
