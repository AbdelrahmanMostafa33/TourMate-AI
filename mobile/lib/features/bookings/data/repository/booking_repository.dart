import '../../../../core/network/api_services.dart';
import '../models/booking_models.dart';

/// Repository for booking/payment operations.
/// Only uses endpoints that already exist on the backend.
class BookingRepository {
  final ApiServices _api;

  BookingRepository(this._api);

  /// List bookings for a trip.
  Future<List<BookingResponse>> listTripBookings(
    String tripId, {
    String? status,
  }) async {
    return await _api.listTripBookings(tripId, status);
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
