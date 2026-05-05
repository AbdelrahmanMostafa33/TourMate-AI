class ChatMessage {
  final String text;
  final bool isUser;
  final bool isStreaming;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isStreaming = false,
  });
}