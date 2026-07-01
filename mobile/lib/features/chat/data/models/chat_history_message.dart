import 'package:equatable/equatable.dart';

/// A single message from the chat history endpoint.
///
/// The [cardData] field contains structured card data that was persisted
/// alongside the text message during the live chat. It can hold:
///   - itinerary_data: full itinerary JSON for the itinerary card
///   - hotel_options: hotel options payload for the hotel options card
///   - flight_options: flight options payload for the flight options card
///   - booking_data: booking data for the booking card
///
/// The Flutter client uses this card data to reconstruct cards exactly as
/// they appeared during the live chat, without needing to guess or
/// reconstruct from secondary data sources.
class ChatHistoryMessage extends Equatable {
  final String messageId;
  final String conversationId;
  final String sender;
  final String content;
  final String? imageData;
  final Map<String, dynamic>? cardData;
  final String? timestamp;

  const ChatHistoryMessage({
    required this.messageId,
    required this.conversationId,
    required this.sender,
    required this.content,
    this.imageData,
    this.cardData,
    this.timestamp,
  });

  /// Whether this message was sent by the user.
  bool get isUser => sender == 'user';

  factory ChatHistoryMessage.fromJson(Map<String, dynamic> json) {
    return ChatHistoryMessage(
      messageId: json['message_id'] as String? ?? '',
      conversationId: json['conversation_id'] as String? ?? '',
      sender: json['sender'] as String? ?? 'agent',
      content: json['content'] as String? ?? '',
      imageData: json['image_data'] as String?,
      cardData: json['card_data'] as Map<String, dynamic>?,
      timestamp: json['timestamp'] as String?,
    );
  }

  ChatHistoryMessage copyWith({
    String? messageId,
    String? conversationId,
    String? sender,
    String? content,
    String? imageData,
    Map<String, dynamic>? cardData,
    String? timestamp,
  }) {
    return ChatHistoryMessage(
      messageId: messageId ?? this.messageId,
      conversationId: conversationId ?? this.conversationId,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      imageData: imageData ?? this.imageData,
      cardData: cardData ?? this.cardData,
      timestamp: timestamp ?? this.timestamp,
    );
  }

  @override
  List<Object?> get props => [messageId, conversationId, sender, content, imageData, cardData, timestamp];
}
