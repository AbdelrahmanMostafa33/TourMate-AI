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
      'currency': ?currency,
    });
  }

  /// List bookings for a trip.
  Future<List<BookingResponse>> listTripBookings(
    String tripId, {
    String? status,
  }) async {
    return await _api.listTripBookings(tripId, status);
  }

  /// Get a single booking.
  Future<BookingResponse> getBooking(String bookingId) async {
    return await _api.getBooking(bookingId);
  }
}
