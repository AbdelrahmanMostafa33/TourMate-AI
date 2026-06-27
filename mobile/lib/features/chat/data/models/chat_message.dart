import 'dart:typed_data';
import 'itinerary_data.dart';
import 'hotel_option.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final bool isStreaming;
  final ItineraryData? itinerary;
  final Uint8List? imageBytes;
  final HotelOptionsPayload? hotelOptions;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isStreaming = false,
    this.itinerary,
    this.imageBytes,
    this.hotelOptions,
  });

  ChatMessage copyWith({
    String? text,
    bool? isUser,
    bool? isStreaming,
    ItineraryData? itinerary,
    Uint8List? imageBytes,
    HotelOptionsPayload? hotelOptions,
  }) {
    return ChatMessage(
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      isStreaming: isStreaming ?? this.isStreaming,
      itinerary: itinerary ?? this.itinerary,
      imageBytes: imageBytes ?? this.imageBytes,
      hotelOptions: hotelOptions ?? this.hotelOptions,
    );
  }
}