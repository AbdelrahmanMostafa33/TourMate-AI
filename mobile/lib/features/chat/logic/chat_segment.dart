import '../data/models/booking_data.dart';
import '../data/models/flight_options_payload.dart';
import '../data/models/hotel_option.dart';
import '../data/models/itinerary_data.dart';
import '../data/models/photo_analysis_data.dart';

/// A fragment of rendered assistant content.
///
/// A single [ChatMessage] holds a **list** of segments so that text and
/// structured cards can coexist naturally — text-before-card, card-before-text,
/// multiple cards, plain text, etc. — without one overwriting the other.
sealed class ChatSegment {
  const ChatSegment();
}

/// Plain text (streamed incrementally or complete).
class TextSegment extends ChatSegment {
  final String text;
  final bool isStreaming;

  const TextSegment({required this.text, this.isStreaming = false});
}

/// A structured card, rendered by the registered [CardRenderer].
class CardSegment extends ChatSegment {
  final String cardType;
  final Map<String, dynamic> rawData;

  /// Lazily-parsed typed data (populated on first access).
  ItineraryData? _itinerary;
  BookingData? _booking;
  FlightOptionsPayload? _flightOptions;
  HotelOptionsPayload? _hotelOptions;
  PhotoAnalysisData? _photoAnalysis;

  ItineraryData? get itinerary {
    if (cardType != 'itinerary') return null;
    _itinerary ??= _tryParse(() => ItineraryData.fromJson(rawData));
    return _itinerary;
  }

  BookingData? get booking {
    if (cardType != 'booking') return null;
    _booking ??= _tryParse(() => BookingData.fromJson(rawData));
    return _booking;
  }

  FlightOptionsPayload? get flightOptions {
    if (cardType != 'flight_options') return null;
    _flightOptions ??= _tryParse(() => FlightOptionsPayload.fromJson(rawData));
    return _flightOptions;
  }

  HotelOptionsPayload? get hotelOptions {
    if (cardType != 'hotel_options') return null;
    _hotelOptions ??= _tryParse(() => HotelOptionsPayload.fromJson(rawData));
    return _hotelOptions;
  }

  PhotoAnalysisData? get photoAnalysis {
    if (cardType != 'image_features') return null;
    _photoAnalysis ??= _tryParse(() => PhotoAnalysisData.fromJson(rawData));
    return _photoAnalysis;
  }

  CardSegment({required this.cardType, required this.rawData});

  /// A stable identity hash used by [MessageAssembler] for deduplication.
  String get identityHash => '${cardType}_${rawData.hashCode}';
}

/// Pipeline progress updates (visible during AI processing).
class ProgressSegment extends ChatSegment {
  final List<ProgressStep> steps;

  const ProgressSegment({required this.steps});
}

/// One step inside a [ProgressSegment].
class ProgressStep {
  final String agent;
  final String status;
  final String message;

  const ProgressStep({
    required this.agent,
    required this.status,
    this.message = '',
  });
}

// ── Internal helpers ───────────────────────────────────────────────────────

T? _tryParse<T>(T Function() fn) {
  try {
    return fn();
  } catch (e) {
    // ignore: avoid_print
    print('[ChatSegment] ⚠️ Failed to parse $T: $e');
    return null;
  }
}
