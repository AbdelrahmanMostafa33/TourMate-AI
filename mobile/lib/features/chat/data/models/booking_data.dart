/// Matches the booking_data payload from the AI engine orchestrator.
///
/// Sent after hotel selection (``response_type: "booking"``) and when
/// the user approves in the BOOKING phase (``response_type: "booking_confirmed"``).
///
/// Contains flight, hotel, pricing, and trip summary info used to
/// render a booking confirmation card in the chat and to navigate to
/// the payment flow in trip detail.
class BookingData {
  final BookingFlight? flight;
  final BookingHotel? hotel;
  final TripSummary? tripSummary;
  final PricingData? pricing;
  final String? tripId;
  final bool hasFlight;
  final bool hasHotel;
  final bool isConfirmed;

  const BookingData({
    this.flight,
    this.hotel,
    this.tripSummary,
    this.pricing,
    this.tripId,
    this.hasFlight = false,
    this.hasHotel = false,
    this.isConfirmed = false,
  });

  factory BookingData.fromJson(Map<String, dynamic> json) {
    return BookingData(
      flight: json['flight'] != null
          ? BookingFlight.fromJson(json['flight'] as Map<String, dynamic>)
          : null,
      hotel: json['hotel'] != null
          ? BookingHotel.fromJson(json['hotel'] as Map<String, dynamic>)
          : null,
      tripSummary: json['trip_summary'] != null
          ? TripSummary.fromJson(json['trip_summary'] as Map<String, dynamic>)
          : null,
      pricing: json['pricing'] != null
          ? PricingData.fromJson(json['pricing'] as Map<String, dynamic>)
          : null,
      tripId: json['trip_id'] as String?,
      hasFlight: json['has_flight'] as bool? ?? false,
      hasHotel: json['has_hotel'] as bool? ?? false,
    );
  }

  /// Create a copy with optional field overrides.
  BookingData copyWith({
    BookingFlight? flight,
    BookingHotel? hotel,
    TripSummary? tripSummary,
    PricingData? pricing,
    String? tripId,
    bool? hasFlight,
    bool? hasHotel,
    bool? isConfirmed,
  }) {
    return BookingData(
      flight: flight ?? this.flight,
      hotel: hotel ?? this.hotel,
      tripSummary: tripSummary ?? this.tripSummary,
      pricing: pricing ?? this.pricing,
      tripId: tripId ?? this.tripId,
      hasFlight: hasFlight ?? this.hasFlight,
      hasHotel: hasHotel ?? this.hasHotel,
      isConfirmed: isConfirmed ?? this.isConfirmed,
    );
  }
}

class BookingFlight {
  final bool selected;
  final String? airline;
  final String? flightNumber;
  final String? originIata;
  final String? destinationIata;
  final String? departureAt;
  final String? arrivalAt;
  final double price;
  final String currency;

  const BookingFlight({
    this.selected = false,
    this.airline,
    this.flightNumber,
    this.originIata,
    this.destinationIata,
    this.departureAt,
    this.arrivalAt,
    this.price = 0,
    this.currency = 'USD',
  });

  factory BookingFlight.fromJson(Map<String, dynamic> json) {
    return BookingFlight(
      selected: json['selected'] as bool? ?? false,
      airline: json['airline'] as String?,
      flightNumber: json['flight_number'] as String?,
      originIata: json['origin_iata'] as String?,
      destinationIata: json['destination_iata'] as String?,
      departureAt: json['departure_at'] as String?,
      arrivalAt: json['arrival_at'] as String?,
      price: (json['price'] as num?)?.toDouble() ?? 0,
      currency: json['currency'] as String? ?? 'USD',
    );
  }
}

class BookingHotel {
  final bool selected;
  final String? name;
  final double rating;
  final double nightlyRate;
  final double totalCost;
  final String currency;

  const BookingHotel({
    this.selected = false,
    this.name,
    this.rating = 0,
    this.nightlyRate = 0,
    this.totalCost = 0,
    this.currency = 'USD',
  });

  factory BookingHotel.fromJson(Map<String, dynamic> json) {
    return BookingHotel(
      selected: json['selected'] as bool? ?? false,
      name: json['name'] as String?,
      rating: (json['rating'] as num?)?.toDouble() ?? 0,
      nightlyRate: (json['nightly_rate'] as num?)?.toDouble() ?? 0,
      totalCost: (json['total_cost'] as num?)?.toDouble() ?? 0,
      currency: json['currency'] as String? ?? 'USD',
    );
  }
}

class TripSummary {
  final String destination;
  final int durationDays;
  final int travelers;
  final String? originCity;

  const TripSummary({
    this.destination = '',
    this.durationDays = 0,
    this.travelers = 1,
    this.originCity,
  });

  factory TripSummary.fromJson(Map<String, dynamic> json) {
    return TripSummary(
      destination: json['destination'] as String? ?? '',
      durationDays: (json['duration_days'] as num?)?.toInt() ?? 0,
      travelers: (json['travelers'] as num?)?.toInt() ?? 1,
      originCity: json['origin_city'] as String?,
    );
  }
}

class PricingData {
  final double flightCost;
  final double hotelCost;
  final double totalEstimated;
  final String currency;

  const PricingData({
    this.flightCost = 0,
    this.hotelCost = 0,
    this.totalEstimated = 0,
    this.currency = 'USD',
  });

  factory PricingData.fromJson(Map<String, dynamic> json) {
    return PricingData(
      flightCost: (json['flight_cost'] as num?)?.toDouble() ?? 0,
      hotelCost: (json['hotel_cost'] as num?)?.toDouble() ?? 0,
      totalEstimated: (json['total_estimated'] as num?)?.toDouble() ?? 0,
      currency: json['currency'] as String? ?? 'USD',
    );
  }
}
