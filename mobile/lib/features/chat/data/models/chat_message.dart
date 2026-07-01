import 'dart:typed_data';
import 'itinerary_data.dart';
import 'hotel_option.dart';
import 'booking_data.dart';
import 'flight_options_payload.dart';

class ChatMessage {
  final String text;
  final bool isUser;
  final bool isStreaming;
  final ItineraryData? itinerary;
  final Uint8List? imageBytes;
  final HotelOptionsPayload? hotelOptions;
  final BookingData? bookingData;
  final FlightOptionsPayload? flightOptions;

  ChatMessage({
    required this.text,
    required this.isUser,
    this.isStreaming = false,
    this.itinerary,
    this.imageBytes,
    this.hotelOptions,
    this.bookingData,
    this.flightOptions,
  });

  ChatMessage copyWith({
    String? text,
    bool? isUser,
    bool? isStreaming,
    ItineraryData? itinerary,
    Uint8List? imageBytes,
    HotelOptionsPayload? hotelOptions,
    BookingData? bookingData,
    FlightOptionsPayload? flightOptions,
  }) {
    return ChatMessage(
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      isStreaming: isStreaming ?? this.isStreaming,
      itinerary: itinerary ?? this.itinerary,
      imageBytes: imageBytes ?? this.imageBytes,
      hotelOptions: hotelOptions ?? this.hotelOptions,
      bookingData: bookingData ?? this.bookingData,
      flightOptions: flightOptions ?? this.flightOptions,
    );
  }
}