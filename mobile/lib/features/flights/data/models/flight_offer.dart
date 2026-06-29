import 'package:equatable/equatable.dart';

/// Matches the backend FlightOfferItem schema from flight search results.
class FlightOffer extends Equatable {
  final int offerIndex;
  final String airlineCode;
  final String airlineName;
  final String flightNumber;
  final String originIata;
  final String destinationIata;
  final DateTime departureAt;
  final DateTime arrivalAt;
  final String cabinClass;
  final double totalPrice;
  final String currency;
  final double pricePerAdult;
  final Map<String, dynamic> rawOffer;

  const FlightOffer({
    required this.offerIndex,
    required this.airlineCode,
    required this.airlineName,
    required this.flightNumber,
    required this.originIata,
    required this.destinationIata,
    required this.departureAt,
    required this.arrivalAt,
    required this.cabinClass,
    required this.totalPrice,
    required this.currency,
    required this.pricePerAdult,
    required this.rawOffer,
  });

  factory FlightOffer.fromJson(Map<String, dynamic> json) {
    return FlightOffer(
      offerIndex: json['offer_index'] as int? ?? 0,
      airlineCode: json['airline_code'] as String? ?? '',
      airlineName: json['airline_name'] as String? ?? '',
      flightNumber: json['flight_number'] as String? ?? '',
      originIata: json['origin_iata'] as String? ?? '',
      destinationIata: json['destination_iata'] as String? ?? '',
      departureAt: DateTime.parse(json['departure_at'] as String),
      arrivalAt: DateTime.parse(json['arrival_at'] as String),
      cabinClass: json['cabin_class'] as String? ?? '',
      totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? 'USD',
      pricePerAdult: (json['price_per_adult'] as num?)?.toDouble() ?? 0.0,
      rawOffer: json['raw_offer'] as Map<String, dynamic>? ?? {},
    );
  }

  String get formattedPrice => '${currency == 'USD' ? '\$' : currency}${totalPrice.toStringAsFixed(2)}';

  String get duration {
    final diff = arrivalAt.difference(departureAt);
    return '${diff.inHours}h ${diff.inMinutes.remainder(60)}m';
  }

  @override
  List<Object?> get props => [
        offerIndex, airlineCode, airlineName, flightNumber,
        originIata, destinationIata, departureAt, arrivalAt,
        cabinClass, totalPrice, currency, pricePerAdult,
      ];
}
