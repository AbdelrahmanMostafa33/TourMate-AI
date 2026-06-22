import 'itinerary_data.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final bool isStreaming;
  final ItineraryData? itinerary;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isStreaming = false,
    this.itinerary,
  });

  ChatMessage copyWith({
    String? text,
    bool? isUser,
    bool? isStreaming,
    ItineraryData? itinerary,
  }) {
    return ChatMessage(
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      isStreaming: isStreaming ?? this.isStreaming,
      itinerary: itinerary ?? this.itinerary,
    );
  }
}