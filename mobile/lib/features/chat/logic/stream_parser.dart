import 'package:flutter/foundation.dart';
import 'chat_event.dart';

/// Parses raw WebSocket messages into typed [TypedWsEvent]s.
///
/// Supports two wire formats transparently:
///   1. **New protocol envelope** (detected by `protocol: "tourmate.chat"`)
///      — all events arrive inside a versioned envelope with strong typing.
///   2. **Legacy ad-hoc events** — individual `type` / `data` top-level keys
///      for backward compatibility during the transition period.
///
/// Design principles:
///   - **Fail-gracefully**: malformed events return `null` instead of crashing.
///   - **Deterministic**: same input always yields same output.
///   - **Pure**: no side effects, no mutable state.
///
/// Usage:
/// ```dart
/// final event = StreamParser.parse(rawJson);
/// if (event != null) { ... }
/// ```
class StreamParser {
  /// Parse a single raw WS message (already decoded from JSON).
  ///
  /// Returns `null` for unknown or malformed events so the caller can skip
  /// them without crashing the stream.
  static TypedWsEvent? parse(Map<String, dynamic> raw) {
    try {
      // ── Detect protocol ────────────────────────────────────────────
      // New protocol envelope: all events have "protocol": "tourmate.chat".
      final isNewProtocol = raw['protocol'] == 'tourmate.chat';

      if (isNewProtocol) {
        return _parseEnvelope(raw);
      }

      // ── Legacy ad-hoc events ───────────────────────────────────────
      return _parseLegacy(raw);
    } catch (e) {
      debugPrint('[StreamParser] ❌ Failed to parse event: $e');
      return null;
    }
  }

  // ── New protocol envelope parser ─────────────────────────────────────

  /// Parse a versioned protocol envelope.
  ///
  /// Format:
  /// ```json
  /// {
  ///   "protocol": "tourmate.chat",
  ///   "version": 1,
  ///   "type": "assistant.text.delta",
  ///   "sequence": 1,
  ///   "data": { ... }
  /// }
  /// ```
  static TypedWsEvent? _parseEnvelope(Map<String, dynamic> raw) {
    final eventType = raw['type'] as String?;
    final data = raw['data'] as Map<String, dynamic>? ?? {};
    final responseId = raw['response_id'] as String?;

    switch (eventType) {
      // ── Response lifecycle ───────────────────────────────────────
      case 'assistant.response.started':
        return ResponseStartedEvent(responseId: responseId);

      case 'assistant.text.delta':
        final text = data['text'] as String?;
        if (text == null || text.isEmpty) return null;
        return TextDeltaEvent(text: text);

      case 'assistant.response.completed':
        return ResponseCompletedEvent(
          status: data['status'] as String? ?? 'ok',
          message: data['message'] as String? ?? '',
        );

      // ── Structured cards ─────────────────────────────────────────
      case 'chat.card':
        final cardType = data['card_type'] as String?;
        final cardData = data['data'] as Map<String, dynamic>?;
        if (cardType == null || cardData == null) return null;
        return CardEvent(
          cardType: cardType,
          data: Map.from(cardData),
          presentation: data['presentation'] as String? ?? 'append',
        );

      // ── Pipeline progress ────────────────────────────────────────
      case 'pipeline.progress':
        return ProgressEvent(
          agent: data['agent'] as String? ?? '',
          status: data['status'] as String? ?? 'running',
          message: data['message'] as String? ?? '',
        );

      // ── Lifecycle events ─────────────────────────────────────────
      case 'trip.created':
        return TripCreatedEvent(
          tripId: data['trip_id'] as String? ?? '',
          itineraryId: data['itinerary_id'] as String?,
        );

      case 'trip.approved':
        return const TripApprovedEvent();

      case 'itinerary.updated':
        return const RefreshEvent();

      // ── Errors ───────────────────────────────────────────────────
      case 'chat.error':
        return ErrorEvent(message: data['message'] as String? ?? 'Unknown error');

      default:
        debugPrint('[StreamParser] ⚠️ Unknown envelope event type: $eventType');
        return null;
    }
  }

  // ── Legacy parser ────────────────────────────────────────────────────

  /// Parse legacy ad-hoc events (no protocol envelope).
  static TypedWsEvent? _parseLegacy(Map<String, dynamic> raw) {
    final type = raw['type'] as String?;
    if (type == null) return null;

    switch (type) {
      // ── Streaming ───────────────────────────────────────────────
      case 'token':
        final text = raw['data'] as String? ?? '';
        if (text.isEmpty) return null;
        return TokenEvent(text: text);

      case 'typing':
        return const TypingEvent();

      case 'done':
        return const DoneEvent();

      // ── Pipeline progress ───────────────────────────────────────
      case 'progress':
        final data = raw['data'] as Map<String, dynamic>?;
        if (data == null) return null;
        return ProgressEvent(
          agent: data['agent'] as String? ?? '',
          status: data['status'] as String? ?? 'running',
          message: data['message'] as String? ?? '',
        );

      // ── Structured cards (legacy) ───────────────────────────────
      case 'itinerary_data':
        final data = raw['data'];
        if (data is! Map) return null;
        return CardDataEvent(cardType: 'itinerary', data: Map.from(data));

      case 'booking_data':
        final data = raw['data'];
        if (data is! Map) return null;
        return CardDataEvent(cardType: 'booking', data: Map.from(data));

      case 'flight_options':
        final data = raw['data'];
        if (data is! Map) return null;
        return CardDataEvent(cardType: 'flight_options', data: Map.from(data));

      case 'hotel_options':
        final data = raw['data'];
        if (data is! Map) return null;
        return CardDataEvent(cardType: 'hotel_options', data: Map.from(data));

      case 'result':
        // Legacy `result` events may carry image_features or hotel_options.
        final data = raw['data'] as Map<String, dynamic>?;
        if (data == null) return null;
        final imageFeatures = data['image_features'] as Map<String, dynamic>?;
        if (imageFeatures != null && imageFeatures.isNotEmpty) {
          debugPrint(
            '[DEBUG_HOTEL_CARD] stream_parser: extracted image_features from result event');
          return CardDataEvent(
            cardType: 'image_features',
            data: Map.from(imageFeatures),
          );
        }
        final hotelOptions = data['hotel_options'] as Map<String, dynamic>?;
        debugPrint(
          '[DEBUG_HOTEL_CARD] stream_parser: result event keys=${data.keys.toList()} '
          'has_hotel_options=${hotelOptions != null} '
          'hotel_options_isEmpty=${hotelOptions == null || hotelOptions.isEmpty} '
          'options_count=${hotelOptions?['options'] is List ? (hotelOptions!['options'] as List).length : "N/A"}');
        if (hotelOptions != null && hotelOptions.isNotEmpty) {
          debugPrint(
            '[DEBUG_HOTEL_CARD] stream_parser: extracted hotel_options card with '
            'options_count=${hotelOptions['options'] is List ? (hotelOptions['options'] as List).length : "?"} '
            'accom_prefs=${hotelOptions['accommodation_preferences']}');
          return CardDataEvent(
            cardType: 'hotel_options',
            data: Map.from(hotelOptions),
          );
        }
        return null;

      // ── Lifecycle (legacy) ──────────────────────────────────────
      case 'trip_created':
        return TripCreatedEvent(
          tripId: raw['trip_id'] as String? ?? '',
          itineraryId: raw['itinerary_id'] as String?,
        );

      case 'trip_approved':
        return const TripApprovedEvent();

      case 'itinerary_updated':
        return const RefreshEvent();

      // ── Backend-internal signaling ──────────────────────────────
      case 'phase':
      case 'actions':
      case 'pong':
        return null;

      // ── Errors ──────────────────────────────────────────────────
      case 'error':
        final msg = raw['data'] as String? ?? 'Unknown error';
        return ErrorEvent(message: msg);

      default:
        debugPrint('[StreamParser] ⚠️ Unknown legacy event type: $type');
        return null;
    }
  }
}
