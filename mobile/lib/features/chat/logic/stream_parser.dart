import 'package:flutter/foundation.dart';
import 'chat_event.dart';

/// Parses raw WebSocket messages into typed [TypedWsEvent]s.
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

        // ── Structured card data ────────────────────────────────────
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
          // The backend forwards `result` events *only* for image_features
          // (see process_message_stream in routes/chat.py).
          // Extract image_features as a card if present.
          final data = raw['data'] as Map<String, dynamic>?;
          if (data == null) return null;
          final imageFeatures = data['image_features'] as Map<String, dynamic>?;
          if (imageFeatures != null && imageFeatures.isNotEmpty) {
            return CardDataEvent(
              cardType: 'image_features',
              data: Map.from(imageFeatures),
            );
          }
          return null; // no actionable data in this result

        // ── Lifecycle ───────────────────────────────────────────────
        case 'trip_created':
          return TripCreatedEvent(
            tripId: raw['trip_id'] as String? ?? '',
            itineraryId: raw['itinerary_id'] as String?,
          );

        case 'trip_approved':
          return const TripApprovedEvent();

        case 'itinerary_updated':
          return const RefreshEvent();

        // ── Backend-internal signaling ─────────────────────────────
        case 'phase':
          // Phase transitions (e.g. "flight_selection", "completed") are
          // backend-internal; forwarded to client but not consumed by UI.
          return null;

        case 'actions':
          // Server-side action execution results forwarded but not
          // consumed by Flutter UI (they trigger itinerary_updated).
          return null;

        case 'pong':
          // Heartbeat response from the server — silently ignore.
          return null;

        // ── Errors ──────────────────────────────────────────────────
        case 'error':
          final msg = raw['data'] as String? ?? 'Unknown error';
          return ErrorEvent(message: msg);

        default:
          // Unknown event type — log and skip
          debugPrint('[StreamParser] ⚠️ Unknown event type: $type');
          return null;
      }
    } catch (e) {
      debugPrint('[StreamParser] ❌ Failed to parse event: $e');
      return null;
    }
  }
}
