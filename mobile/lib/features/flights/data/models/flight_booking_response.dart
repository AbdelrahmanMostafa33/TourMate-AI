import 'package:equatable/equatable.dart';
import '../../../../features/bookings/data/models/booking_models.dart' show PaymentResponse;
import 'city_search_result.dart';
import 'flight_offer.dart';

/// Matches the backend SmartFlightSearchResponse schema.
class SmartFlightSearchResponse extends Equatable {
  final CitySearchResult origin;
  final CitySearchResult destination;
  final List<FlightOffer> offers;

  const SmartFlightSearchResponse({
    required this.origin,
    required this.destination,
    required this.offers,
  });

  factory SmartFlightSearchResponse.fromJson(Map<String, dynamic> json) {
    return SmartFlightSearchResponse(
      origin: CitySearchResult.fromJson(json['origin'] as Map<String, dynamic>),
      destination:
          CitySearchResult.fromJson(json['destination'] as Map<String, dynamic>),
      offers: (json['offers'] as List<dynamic>?)
              ?.map((e) => FlightOffer.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  @override
  List<Object?> get props => [origin, destination, offers];
}

/// Matches the backend FlightBookInitiateResponse schema.
class FlightBookInitiateResponse extends Equatable {
  final String clientSecret;
  final String paymentIntentId;
  final Map<String, dynamic> pricedOffer;
  final double amount;
  final String currency;
  final String originIata;
  final String destinationIata;
  final DateTime departureAt;
  final DateTime arrivalAt;
  final String airlineName;
  final String flightNumber;
  final String cabinClass;

  const FlightBookInitiateResponse({
    required this.clientSecret,
    required this.paymentIntentId,
    required this.pricedOffer,
    required this.amount,
    required this.currency,
    required this.originIata,
    required this.destinationIata,
    required this.departureAt,
    required this.arrivalAt,
    required this.airlineName,
    required this.flightNumber,
    required this.cabinClass,
  });

  factory FlightBookInitiateResponse.fromJson(Map<String, dynamic> json) {
    return FlightBookInitiateResponse(
      clientSecret: json['client_secret'] as String? ?? '',
      paymentIntentId: json['payment_intent_id'] as String? ?? '',
      pricedOffer: json['priced_offer'] as Map<String, dynamic>? ?? {},
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? 'USD',
      originIata: json['origin_iata'] as String? ?? '',
      destinationIata: json['destination_iata'] as String? ?? '',
      departureAt: DateTime.parse(json['departure_at'] as String),
      arrivalAt: DateTime.parse(json['arrival_at'] as String),
      airlineName: json['airline_name'] as String? ?? '',
      flightNumber: json['flight_number'] as String? ?? '',
      cabinClass: json['cabin_class'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        clientSecret, paymentIntentId, amount, currency,
        originIata, destinationIata, departureAt, arrivalAt,
        airlineName, flightNumber, cabinClass,
      ];
}

/// Matches the backend FlightBookingResponse schema (used for confirm + get + list responses).
class FlightBookingConfirmResponse extends Equatable {
  final String bookingId;
  final String tripId;
  final String userId;
  final String status;
  final double? totalCost;
  final String? currency;
  final String? confirmationNumber;
  final String? startDatetime;
  final String? endDatetime;
  final String? createdAt;
  final String? originIata;
  final String? destinationIata;
  final String? airlineName;
  final String? flightNumber;
  final String? cabinClass;
  final String? amadeusOrderId;
  final PaymentResponse? payment;

  const FlightBookingConfirmResponse({
    required this.bookingId,
    required this.tripId,
    required this.userId,
    required this.status,
    this.totalCost,
    this.currency,
    this.confirmationNumber,
    this.startDatetime,
    this.endDatetime,
    this.createdAt,
    this.originIata,
    this.destinationIata,
    this.airlineName,
    this.flightNumber,
    this.cabinClass,
    this.amadeusOrderId,
    this.payment,
  });

  factory FlightBookingConfirmResponse.fromJson(Map<String, dynamic> json) {
    return FlightBookingConfirmResponse(
      bookingId: json['booking_id'] as String? ?? '',
      tripId: json['trip_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      status: json['status'] as String? ?? '',
      totalCost: (json['total_cost'] as num?)?.toDouble(),
      currency: json['currency'] as String?,
      confirmationNumber: json['confirmation_number'] as String?,
      startDatetime: json['start_datetime'] as String?,
      endDatetime: json['end_datetime'] as String?,
      createdAt: json['created_at'] as String?,
      originIata: json['origin_iata'] as String?,
      destinationIata: json['destination_iata'] as String?,
      airlineName: json['airline_name'] as String?,
      flightNumber: json['flight_number'] as String?,
      cabinClass: json['cabin_class'] as String?,
      amadeusOrderId: json['amadeus_order_id'] as String?,
      payment: json['payment'] != null
          ? PaymentResponse.fromJson(json['payment'] as Map<String, dynamic>)
          : null,
    );
  }

  @override
  List<Object?> get props => [
        bookingId, tripId, userId, status, totalCost, currency,
        confirmationNumber, startDatetime, endDatetime, createdAt,
        originIata, destinationIata, airlineName, flightNumber,
        cabinClass, amadeusOrderId, payment,
      ];
}

// PaymentResponse is imported from booking_models.dart to avoid duplication.

/// Matches the backend TripFlightContext schema.
class TripFlightContext extends Equatable {
  final String tripId;
  final String? tripName;
  final String? homeCity;
  final String? homeCityIata;
  final String destinationCity;
  final String? destinationIata;
  final String? suggestedDepartureDate;
  final String? suggestedReturnDate;
  final int suggestedAdults;

  const TripFlightContext({
    required this.tripId,
    this.tripName,
    this.homeCity,
    this.homeCityIata,
    required this.destinationCity,
    this.destinationIata,
    this.suggestedDepartureDate,
    this.suggestedReturnDate,
    required this.suggestedAdults,
  });

  factory TripFlightContext.fromJson(Map<String, dynamic> json) {
    return TripFlightContext(
      tripId: json['trip_id'] as String? ?? '',
      tripName: json['trip_name'] as String?,
      homeCity: json['home_city'] as String?,
      homeCityIata: json['home_city_iata'] as String?,
      destinationCity: json['destination_city'] as String? ?? '',
      destinationIata: json['destination_iata'] as String?,
      suggestedDepartureDate: json['suggested_departure_date'] as String?,
      suggestedReturnDate: json['suggested_return_date'] as String?,
      suggestedAdults: (json['suggested_adults'] as num?)?.toInt() ?? 1,
    );
  }

  @override
  List<Object?> get props => [
        tripId, tripName, homeCity, homeCityIata,
        destinationCity, destinationIata,
        suggestedDepartureDate, suggestedReturnDate,
        suggestedAdults,
      ];
}
