import 'package:flutter/foundation.dart';
import 'chat_event.dart';
import 'chat_segment.dart';

/// Assembles a stream of [TypedWsEvent]s into a stable list of [ChatSegment]s
/// for one assistant response.
///
/// Handles:
///   - Incremental text accumulation (streaming)
///   - Card deduplication (same card identity is rendered once)
///   - Mixed text + card + text ordering
///   - Stream completion
///
/// This class is stateful — create one instance per assistant response.
class MessageAssembler {
  String _buffer = '';
  final List<ChatSegment> _segments = [];
  bool _hasNonTextSegment = false;
  bool _isStreaming = false;

  /// Set of card identity hashes already rendered in this response.
  final Set<String> _renderedCards = {};

  /// The current accumulated segments (read-only view).
  List<ChatSegment> get segments => List.unmodifiable(_segments);

  /// Whether the response is still streaming.
  bool get isStreaming => _isStreaming;

  /// Process one event and return updated segments for the **current**
  /// assistant message.  Returns `null` when the event doesn't produce
  /// a visible change (e.g. a duplicate card).
  List<ChatSegment>? onEvent(TypedWsEvent event) {
    return switch (event) {
      TokenEvent(:final text) => _onToken(text),
      TypingEvent() => _onTyping(),
      DoneEvent() => _onDone(),
      ProgressEvent() => null, // handled separately by the cubit
      CardDataEvent(:final cardType, :final data) => _onCard(cardType, data),
      RefreshEvent() => null, // cubit handles bumping
      TripCreatedEvent() => null, // cubit handles
      TripApprovedEvent() => null, // cubit handles
      ErrorEvent() => null, // cubit handles
    };
  }

  /// Finalise streaming and return the final segment list.
  List<ChatSegment> finalize() {
    _isStreaming = false;
    _flushBuffer();
    return List.unmodifiable(_segments);
  }

  /// Reset for a new response.
  void reset() {
    _buffer = '';
    _segments.clear();
    _hasNonTextSegment = false;
    _isStreaming = false;
    _renderedCards.clear();
  }

  // ── Internal helpers ──────────────────────────────────────────────

  List<ChatSegment>? _onToken(String text) {
    _isStreaming = true;

    if (_hasNonTextSegment) {
      // Cards already shown — append text directly to the last (or create new)
      // text segment without buffering.
      if (_segments.isNotEmpty && _segments.last is TextSegment) {
        final last = _segments.last as TextSegment;
        _segments[_segments.length - 1] = TextSegment(
          text: last.text + text,
          isStreaming: true,
        );
      } else {
        _segments.add(TextSegment(text: text, isStreaming: true));
      }
    } else {
      // No cards yet — accumulate into buffer for eventual flush before card.
      _buffer += text;
      if (_segments.isNotEmpty && _segments.last is TextSegment) {
        final last = _segments.last as TextSegment;
        _segments[_segments.length - 1] = TextSegment(
          text: last.text + text,
          isStreaming: true,
        );
        // Text is now committed to _segments; clear buffer so
        // _flushBuffer() doesn't create a duplicate segment on done.
        _buffer = '';
      } else {
        _segments.add(TextSegment(text: _buffer, isStreaming: true));
        _buffer = '';
      }
    }
    return _segments;
  }

  List<ChatSegment>? _onTyping() {
    _isStreaming = true;
    // Typing is implicit from the streaming flag; no segment needed.
    return null;
  }

  List<ChatSegment>? _onDone() {
    _isStreaming = false;
    _flushBuffer();
    // Mark the last text segment as not streaming.
    if (_segments.isNotEmpty && _segments.last is TextSegment) {
      final last = _segments.last as TextSegment;
      _segments[_segments.length - 1] = TextSegment(
        text: last.text,
        isStreaming: false,
      );
    }
    return _segments;
  }

  List<ChatSegment>? _onCard(String cardType, Map<String, dynamic> data) {
    _hasNonTextSegment = true;

    // Flush any pending text to a segment BEFORE the card.
    _flushBuffer();

    final card = CardSegment(cardType: cardType, rawData: data);

    // Deduplicate: skip if we've already rendered this exact card.
    if (_renderedCards.contains(card.identityHash)) {
      debugPrint('[MessageAssembler] ⚠️ Duplicate card skipped: ${card.identityHash}');
      return null;
    }

    _segments.add(card);
    _renderedCards.add(card.identityHash);
    return _segments;
  }

  void _flushBuffer() {
    if (_buffer.isNotEmpty) {
      _segments.add(TextSegment(text: _buffer));
      _buffer = '';
    }
  }
}
