import '../../../../core/network/api_services.dart';
import '../models/booking_models.dart';

/// Repository for booking/payment operations.
/// Only uses endpoints that already exist on the backend.
class BookingRepository {
  final ApiServices _api;

  BookingRepository(this._api);

  /// Book all stops in a trip's itinerary as a package.
  Future<TripPackageBookingResponse> bookTripPackage(String tripId) async {
    return await _api.bookTripPackage(tripId);
  }

  /// Pay all pending bookings in a trip at once.
  Future<TripPackagePaymentResponse> payTripPackage({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) async {
    return await _api.payTripPackage(tripId, {
      'payment_method': paymentMethod,
      if (currency != null) 'currency': currency,
    });
  }

  /// List bookings for a trip.
  Future<List<BookingResponse>> listTripBookings(
    String tripId, {
    String? status,
  }) async {
    return await _api.listTripBookings(tripId, status);
  }

  /// Pay for a single booking via Stripe Payment Sheet.
  /// Returns a map with payment_id, client_secret, stripe_payment_intent_id, etc.
  Future<Map<String, dynamic>> payBooking({
    required String bookingId,
    required String paymentMethod,
    required double amount,
    String? currency,
  }) async {
    final result = await _api.payBooking(bookingId, {
      'payment_method': paymentMethod,
      'amount': amount,
      if (currency != null) 'currency': currency,
    });
    return result.data;
  }

  /// Initiate an async Stripe Payment Sheet payment.
  /// Creates a PaymentIntent without confirming it.
  /// Returns client_secret for the Payment Sheet.
  Future<Map<String, dynamic>> initiateBookingPayment({
    required String bookingId,
    required String paymentMethod,
    required double amount,
    String? currency,
  }) async {
    final result = await _api.initiateBookingPayment(bookingId, {
      'payment_method': paymentMethod,
      'amount': amount,
      if (currency != null) 'currency': currency,
    });
    return result.data;
  }

  /// Initiate async Stripe Payment Sheet payments for all pending bookings.
  /// Creates PaymentIntents without confirming them.
  /// Returns initiated (with client_secret) + skipped lists.
  Future<InitiatePackagePaymentResponse> initiateTripPackagePayment({
    required String tripId,
    required String paymentMethod,
    String? currency,
  }) async {
    return await _api.initiateTripPackagePayment(tripId, {
      'payment_method': paymentMethod,
      if (currency != null) 'currency': currency,
    });
  }

  /// Confirm a booking after the Payment Sheet succeeds.
  /// Calls POST /bookings/{bookingId}/confirm-after-payment.
  /// The backend verifies the PaymentIntent with Stripe directly.
  Future<Map<String, dynamic>> confirmAfterPayment({
    required String bookingId,
    required String stripePaymentIntentId,
  }) async {
    final result = await _api.confirmAfterPayment(bookingId, {
      'stripe_payment_intent_id': stripePaymentIntentId,
    });
    return result.data;
  }

  /// Get a single booking.
  Future<BookingResponse> getBooking(String bookingId) async {
    return await _api.getBooking(bookingId);
  }
}
