import '../../../../core/network/api_services.dart';
import '../models/city_search_result.dart';
import '../models/flight_booking_response.dart';

/// Repository for flight booking operations.
/// Only uses endpoints that already exist on the backend.
class FlightRepository {
  final ApiServices _api;

  FlightRepository(this._api);

  /// Search cities/airports for autocomplete.
  Future<List<CitySearchResult>> searchCities(String query, {int max = 10}) async {
    return await _api.searchFlightCities(query, max);
  }

  /// Smart search — resolves city names + searches flights.
  Future<SmartFlightSearchResponse> smartSearch({
    required String originCity,
    required String destinationCity,
    required String departureDate,
    int adults = 1,
    int maxResults = 5,
  }) async {
    return await _api.smartSearchFlights({
      'origin_city': originCity,
      'destination_city': destinationCity,
      'departure_date': departureDate,
      'adults': adults,
      'max_results': maxResults,
    });
  }

  /// Initiate a flight booking — prices the offer + creates Stripe PaymentIntent.
  Future<FlightBookInitiateResponse> initiateBooking({
    required Map<String, dynamic> rawOffer,
    required String tripId,
  }) async {
    return await _api.initiateFlightBooking({
      'raw_offer': rawOffer,
      'trip_id': tripId,
    });
  }

  /// Confirm a flight booking after Stripe payment succeeds.
  Future<FlightBookingConfirmResponse> confirmBooking({
    required String paymentIntentId,
    required Map<String, dynamic> pricedOffer,
    required String tripId,
    required String travelerFirstName,
    required String travelerLastName,
    required String travelerDateOfBirth,
    required String travelerGender,
    required String travelerEmail,
    required String travelerPhone,
  }) async {
    return await _api.confirmFlightBooking({
      'payment_intent_id': paymentIntentId,
      'priced_offer': pricedOffer,
      'trip_id': tripId,
      'traveler_first_name': travelerFirstName,
      'traveler_last_name': travelerLastName,
      'traveler_date_of_birth': travelerDateOfBirth,
      'traveler_gender': travelerGender,
      'traveler_email': travelerEmail,
      'traveler_phone': travelerPhone,
    });
  }

  /// Get trip flight context for pre-filling search form.
  Future<TripFlightContext> getTripFlightContext(String tripId) async {
    return await _api.getTripFlightContext(tripId);
  }

  /// Get flight bookings for a trip.
  Future<List<FlightBookingConfirmResponse>> getTripFlightBookings(String tripId) async {
    return await _api.listTripFlightBookings(tripId);
  }

  /// Cancel a flight booking.
  Future<FlightBookingConfirmResponse> cancelFlightBooking(String bookingId) async {
    return await _api.cancelFlightBooking(bookingId);
  }
}
