import 'package:flutter/foundation.dart';
import '../../../flights/data/models/flight_offer.dart';

/// A payload containing multiple flight offers, sent from the backend
/// in the result event (flight_search_results) or flight_options event.
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
            // DEBUG: Check if raw_offer is present in the raw map
            if (raw.containsKey('raw_offer')) {
              final ro = raw['raw_offer'];
              debugPrint('[FlightOptionsPayload] raw_offer present: type=${ro.runtimeType}, null=${ro == null}, isEmpty=${ro is Map ? ro.isEmpty : "N/A"}, keys=${ro is Map ? ro.keys.take(10).toList() : "N/A"}');
            } else {
              debugPrint('[FlightOptionsPayload] raw_offer MISSING from raw. Keys=${raw.keys.toList()}');
            }
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
