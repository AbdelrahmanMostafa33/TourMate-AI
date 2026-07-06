import 'package:flutter/foundation.dart';
import 'package:equatable/equatable.dart';

/// Matches a single flight offer from the backend's flight search results
/// or smart-search API.
///
/// Handles two JSON formats:
///   - **Chat format** (flight_search_results / flight_options):
///     ``departure_at_formatted`` and ``arrival_at_formatted`` are pre-formatted
///     display strings; ``duration``, ``stops``, ``cabin`` are present.
///   - **Flights API format** (smart-search):
///     ``departure_at`` / ``arrival_at`` are ISO-8601 DateTime strings;
///     ``offer_index``, ``cabin_class``, ``price_per_adult``, ``raw_offer``
///     are present; ``departure_at_formatted`` / ``arrival_at_formatted`` are
///     derived from the DateTime fields.
class FlightOffer extends Equatable {
  /// Display name (e.g. "EgyptAir")
  final String airlineName;

  /// IATA code (e.g. "MS")
  final String airlineCode;

  /// Flight number (e.g. "MS777")
  final String flightNumber;

  /// Origin IATA code
  final String originIata;

  /// Destination IATA code
  final String destinationIata;

  /// Pre-formatted departure time string for display ("08:30")
  final String departureAtFormatted;

  /// Pre-formatted arrival time string for display ("11:45")
  final String arrivalAtFormatted;

  /// Total price
  final double totalPrice;

  /// Currency (e.g. "USD", "EGP")
  final String currency;

  /// Human-readable duration ("2h 15m")
  final String? duration;

  /// Number of stops (0 = non-stop)
  final int? stops;

  /// Cabin type (e.g. "ECONOMY")
  final String? cabin;

  /// Offer index within the search results (flights API format)
  final int offerIndex;

  /// Parsed departure DateTime (flights API format)
  final DateTime? departureAt;

  /// Parsed arrival DateTime (flights API format)
  final DateTime? arrivalAt;

  /// Cabin class string (flights API format)
  final String? cabinClass;

  /// Price per adult (flights API format)
  final double pricePerAdult;

  /// Return (inbound) segments for round-trip offers.
  /// Each segment has: airline_code, flight_number, origin_iata,
  /// destination_iata, departure_at_formatted, arrival_at_formatted.
  final List<Map<String, dynamic>> returnSegments;

  /// Raw offer JSON for downstream booking (flights API format)
  final Map<String, dynamic> rawOffer;

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
    this.offerIndex = 0,
    this.departureAt,
    this.arrivalAt,
    this.cabinClass,
    this.pricePerAdult = 0,
    this.returnSegments = const [],
    this.rawOffer = const {},
  });

  /// Parse from either chat-format or flights-API-format JSON.
  factory FlightOffer.fromJson(Map<String, dynamic> json) {
    // ── Parse display times ───────────────────────────────────────────
    // Chat format: departure_at_formatted / arrival_at_formatted
    // Flights API format: departure_at / arrival_at (ISO-8601)
    String depFormatted = (json['departure_at_formatted'] as String? ?? '').toString();
    String arrFormatted = (json['arrival_at_formatted'] as String? ?? '').toString();
    DateTime? depDt;
    DateTime? arrDt;

    // Try to parse DateTime from departure_at / arrival_at
    final rawDep = json['departure_at'];
    final rawArr = json['arrival_at'];
    if (rawDep is String && rawDep.isNotEmpty) {
      try {
        depDt = DateTime.parse(rawDep);
        if (depFormatted.isEmpty) {
          // Derive display time from DateTime
          depFormatted =
              '${depDt.hour.toString().padLeft(2, '0')}:${depDt.minute.toString().padLeft(2, '0')}';
        }
      } catch (_) {
        // Not an ISO datetime — use as formatted string if no explicit formatted field
        if (depFormatted.isEmpty) depFormatted = rawDep;
      }
    }
    if (rawArr is String && rawArr.isNotEmpty) {
      try {
        arrDt = DateTime.parse(rawArr);
        if (arrFormatted.isEmpty) {
          arrFormatted =
              '${arrDt.hour.toString().padLeft(2, '0')}:${arrDt.minute.toString().padLeft(2, '0')}';
        }
      } catch (_) {
        if (arrFormatted.isEmpty) arrFormatted = rawArr;
      }
    }

    // DEBUG: Log raw_offer parsing details
    final rawOfferRaw = json['raw_offer'];
    final rawKeyExists = json.containsKey('raw_offer');
    final rawIsMap = rawOfferRaw is Map<String, dynamic>;
    debugPrint(
      '[FlightOffer.fromJson] raw_offer: keyExists=$rawKeyExists, '
      'type=${rawOfferRaw.runtimeType}, isMap=$rawIsMap, '
      'keys=${rawIsMap ? rawOfferRaw.keys.take(10).toList() : "N/A"}',
    );

    return FlightOffer(
      airlineName: (json['airline_name'] ?? '').toString(),
      airlineCode: (json['airline_code'] ?? '').toString(),
      flightNumber: (json['flight_number'] ?? '').toString(),
      originIata: (json['origin_iata'] ?? json['origin'] ?? '').toString(),
      destinationIata:
          (json['destination_iata'] ?? json['destination'] ?? '').toString(),
      departureAtFormatted: depFormatted,
      arrivalAtFormatted: arrFormatted,
      totalPrice: (json['total_price'] as num?)?.toDouble() ?? 0,
      currency: (json['currency'] ?? 'USD').toString(),
      duration: json['duration']?.toString(),
      stops: (json['stops'] as num?)?.toInt(),
      cabin: json['cabin']?.toString() ?? json['cabin_class']?.toString(),
      offerIndex: (json['offer_index'] as num?)?.toInt() ?? 0,
      departureAt: depDt,
      arrivalAt: arrDt,
      cabinClass: json['cabin_class']?.toString(),
      pricePerAdult: (json['price_per_adult'] as num?)?.toDouble() ?? 0,
      returnSegments: (json['return_segments'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          const [],
      rawOffer: rawOfferRaw as Map<String, dynamic>? ?? {},
    );
  }

  /// Computed: display-friendly airline name (prefers name over code).
  String get airline => airlineName.isNotEmpty ? airlineName : airlineCode;

  /// Computed: route string ("CAI → LHR").
  String get route => '$originIata → $destinationIata';

  /// Computed: price with currency symbol.
  String get priceFormatted {
    final symbol = currency == 'USD'
        ? '\$'
        : (currency == 'EUR' ? '€' : '$currency ');
    if (totalPrice == totalPrice.roundToDouble()) {
      return '$symbol${totalPrice.toInt()}';
    }
    return '$symbol${totalPrice.toStringAsFixed(2)}';
  }

  /// Computed: human-readable duration.
  /// Uses the explicit ``duration`` field if present, otherwise derives
  /// from ``departureAt`` / ``arrivalAt`` DateTime fields.
  String get computedDuration {
    if (duration != null && duration!.isNotEmpty) return duration!;
    if (departureAt != null && arrivalAt != null) {
      final diff = arrivalAt!.difference(departureAt!);
      return '${diff.inHours}h ${diff.inMinutes.remainder(60)}m';
    }
    return '';
  }

  @override
  List<Object?> get props => [
        airlineName,
        airlineCode,
        flightNumber,
        originIata,
        destinationIata,
        totalPrice,
        currency,
        offerIndex,
        departureAt,
        arrivalAt,
        cabinClass,
        pricePerAdult,
        stops,
        cabin,
        returnSegments,
      ];
}
