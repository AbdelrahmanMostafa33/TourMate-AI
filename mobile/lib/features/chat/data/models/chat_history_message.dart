import 'package:equatable/equatable.dart';

/// A single message from the chat history endpoint.
class ChatHistoryMessage extends Equatable {
  final String messageId;
  final String conversationId;
  final String sender;
  final String content;
  final String? timestamp;

  const ChatHistoryMessage({
    required this.messageId,
    required this.conversationId,
    required this.sender,
    required this.content,
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
      timestamp: json['timestamp'] as String?,
    );
  }

  ChatHistoryMessage copyWith({
    String? messageId,
    String? conversationId,
    String? sender,
    String? content,
    String? timestamp,
  }) {
    return ChatHistoryMessage(
      messageId: messageId ?? this.messageId,
      conversationId: conversationId ?? this.conversationId,
      sender: sender ?? this.sender,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
    );
  }

  @override
  List<Object?> get props => [messageId, conversationId, sender, content, timestamp];
}
