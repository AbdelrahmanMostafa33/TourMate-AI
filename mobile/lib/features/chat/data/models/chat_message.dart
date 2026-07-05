import 'dart:typed_data';
import '../../logic/chat_segment.dart';

/// A single message in the chat, holding a list of [ChatSegment]s.
///
/// A message can have any combination of text and card segments, in any
/// order.  This replaces the previous union-type approach where each card
/// type was a separate nullable field — adding a new card type now only
/// requires adding a [CardSegment] without changing this model.
class ChatMessage {
  final bool isUser;
  final List<ChatSegment> segments;
  final bool isStreaming;
  final Uint8List? imageBytes;

  const ChatMessage({
    required this.isUser,
    this.segments = const [],
    this.isStreaming = false,
    this.imageBytes,
  });

  /// Convenience: plain text message (no cards).
  factory ChatMessage.text(String text, {
    bool isUser = false,
    bool isStreaming = false,
    Uint8List? imageBytes,
  }) {
    return ChatMessage(
      isUser: isUser,
      segments: [TextSegment(text: text, isStreaming: isStreaming)],
      isStreaming: isStreaming,
      imageBytes: imageBytes,
    );
  }

  /// Convenience: card-only message (no text).
  factory ChatMessage.card(String cardType, Map<String, dynamic> data, {bool isUser = false}) {
    return ChatMessage(
      isUser: isUser,
      segments: [CardSegment(cardType: cardType, rawData: data)],
    );
  }

  ChatMessage copyWith({
    List<ChatSegment>? segments,
    bool? isUser,
    bool? isStreaming,
    Uint8List? imageBytes,
  }) {
    return ChatMessage(
      isUser: isUser ?? this.isUser,
      segments: segments ?? List.from(this.segments),
      isStreaming: isStreaming ?? this.isStreaming,
      imageBytes: imageBytes ?? this.imageBytes,
    );
  }

  /// The combined text of all [TextSegment]s (for display/search).
  String get combinedText => segments
      .whereType<TextSegment>()
      .map((s) => s.text)
      .join();

  /// Whether any segment is a [CardSegment].
  bool get hasCard => segments.any((s) => s is CardSegment);
}
