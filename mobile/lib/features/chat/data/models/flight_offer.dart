/// Matches a single flight offer from the backend's flight_search_results.
///
/// The backend sends up to 3 offers with airline, route, times, pricing, etc.
/// These are rendered as a FlightOptionsCard in the chat for the user to pick.
class FlightOffer {
  final String airlineName;
  final String airlineCode;
  final String flightNumber;
  final String originIata;
  final String destinationIata;
  final String departureAtFormatted;
  final String arrivalAtFormatted;
  final double totalPrice;
  final String currency;
  final String? duration;
  final int? stops;
  final String? cabin;

  const FlightOffer({
    this.airlineName = '',
    this.airlineCode = '',
    this.flightNumber = '',
    this.originIata = '',
    this.destinationIata = '',
    this.departureAtFormatted = '',
    this.arrivalAtFormatted = '',
    this.totalPrice = 0,
    this.currency = 'USD',
    this.duration,
    this.stops,
    this.cabin,
  });

  factory FlightOffer.fromJson(Map<String, dynamic> json) {
    return FlightOffer(
      airlineName: (json['airline_name'] ?? '').toString(),
      airlineCode: (json['airline_code'] ?? '').toString(),
      flightNumber: (json['flight_number'] ?? '').toString(),
      originIata: (json['origin_iata'] ?? json['origin'] ?? '').toString(),
      destinationIata:
          (json['destination_iata'] ?? json['destination'] ?? '').toString(),
      departureAtFormatted:
          (json['departure_at_formatted'] ?? json['departure_at'] ?? '')
              .toString(),
      arrivalAtFormatted:
          (json['arrival_at_formatted'] ?? json['arrival_at'] ?? '').toString(),
      totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0,
      currency: (json['currency'] ?? 'USD').toString(),
      duration: json['duration']?.toString(),
      stops: (json['stops'] as num?)?.toInt(),
      cabin: json['cabin']?.toString(),
    );
  }

  String get airline => airlineName.isNotEmpty ? airlineName : airlineCode;
  String get route => '$originIata → $destinationIata';
  String get priceFormatted {
    final symbol = currency == 'USD'
        ? '\$'
        : (currency == 'EUR' ? '€' : '$currency ');
    if (totalPrice == totalPrice.roundToDouble()) {
      return '$symbol${totalPrice.toInt()}';
    }
    return '$symbol${totalPrice.toStringAsFixed(2)}';
  }
}

/// A payload containing multiple flight offers, sent from the backend
/// in the result event (flight_search_results).
class FlightOptionsPayload {
  final List<FlightOffer> offers;
  final String? message;
  final String? tripId;

  const FlightOptionsPayload({
    required this.offers,
    this.message,
    this.tripId,
  });

  factory FlightOptionsPayload.fromJson(Map<String, dynamic> json) {
    final rawOffers = json['offers'] ?? json['flight_search_results'] ?? [];
    final offers = <FlightOffer>[];
    if (rawOffers is List) {
      for (final raw in rawOffers) {
        if (raw is Map) {
          try {
            offers.add(FlightOffer.fromJson(Map<String, dynamic>.from(raw)));
          } catch (_) {}
        }
      }
    }
    return FlightOptionsPayload(
      offers: offers,
      message: json['message']?.toString(),
      tripId: json['trip_id']?.toString(),
    );
  }
}
