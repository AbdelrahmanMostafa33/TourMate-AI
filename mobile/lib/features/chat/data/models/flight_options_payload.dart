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
