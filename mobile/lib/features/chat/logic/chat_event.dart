/// Typed events produced by [StreamParser] from raw WebSocket messages.
///
/// Each event corresponds to a backend WsMessage type but is guaranteed to
/// be well-typed and validated.  Unknown/malformed events are silently
/// dropped by the parser (fail-gracefully).
sealed class TypedWsEvent {
  const TypedWsEvent();
}

/// Streamed token — incremental text from the AI response.
class TokenEvent extends TypedWsEvent {
  final String text;
  const TokenEvent({required this.text});
}

/// AI has started generating a response (no text yet).
class TypingEvent extends TypedWsEvent {
  const TypingEvent();
}

/// AI has finished the full response.
class DoneEvent extends TypedWsEvent {
  const DoneEvent();
}

/// Pipeline progress update (agent status).
class ProgressEvent extends TypedWsEvent {
  final String agent;
  final String status; // "running" | "done" | "error"
  final String message;

  const ProgressEvent({
    required this.agent,
    required this.status,
    this.message = '',
  });
}

/// Structured card data (itinerary, booking, flight options, etc.).
class CardDataEvent extends TypedWsEvent {
  final String cardType;
  final Map<String, dynamic> data;

  const CardDataEvent({required this.cardType, required this.data});
}

/// Refresh the UI (bump token) without adding new data.
class RefreshEvent extends TypedWsEvent {
  const RefreshEvent();
}

/// A new trip was created by the backend.
class TripCreatedEvent extends TypedWsEvent {
  final String tripId;
  final String? itineraryId;

  const TripCreatedEvent({required this.tripId, this.itineraryId});
}

/// The current trip was approved.
class TripApprovedEvent extends TypedWsEvent {
  const TripApprovedEvent();
}

/// An error message from the backend.
class ErrorEvent extends TypedWsEvent {
  final String message;
  const ErrorEvent({required this.message});
}
