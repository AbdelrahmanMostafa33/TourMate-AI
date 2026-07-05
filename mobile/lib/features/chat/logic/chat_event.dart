/// Typed events produced by [StreamParser] from raw WebSocket messages.
///
/// Each event corresponds to a backend WsMessage type but is guaranteed to
/// be well-typed and validated.  Unknown/malformed events are silently
/// dropped by the parser (fail-gracefully).
sealed class TypedWsEvent {
  const TypedWsEvent();
}

// ── Legacy stream-to-response events ────────────────────────────────────

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

// ── New protocol events (versioned envelope) ────────────────────────────

/// A new assistant response has started streaming.
///
/// Maps to backend's `assistant.response.started`.
class ResponseStartedEvent extends TypedWsEvent {
  final String? responseId;

  const ResponseStartedEvent({this.responseId});
}

/// Incremental text delta from the AI response.
///
/// Maps to backend's `assistant.text.delta`.
class TextDeltaEvent extends TypedWsEvent {
  final String text;
  const TextDeltaEvent({required this.text});
}

/// A structured card rendered by the UI.
///
/// Maps to backend's `chat.card` envelope. The [presentation] field
/// controls whether the card is appended to the current message or
/// replaces a previous card of the same type.
class CardEvent extends TypedWsEvent {
  final String cardType;
  final Map<String, dynamic> data;
  final String presentation; // "append" | "replace"

  const CardEvent({
    required this.cardType,
    required this.data,
    this.presentation = 'append',
  });
}

/// The assistant response has been fully processed and persisted.
///
/// Maps to backend's `assistant.response.completed`.
class ResponseCompletedEvent extends TypedWsEvent {
  final String status; // "ok" | "error"
  final String message;

  const ResponseCompletedEvent({
    this.status = 'ok',
    this.message = '',
  });
}

// ── Shared events (used by both legacy and new protocol) ─────────────────

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

/// Structured card data (itinerary, booking, flight options, etc.) — legacy.
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
