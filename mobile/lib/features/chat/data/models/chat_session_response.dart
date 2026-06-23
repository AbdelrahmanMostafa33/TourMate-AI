import 'package:equatable/equatable.dart';

/// A single chat session (conversation) with optional trip info.
class ChatSessionResponse extends Equatable {
  final String conversationId;
  final String? tripId;
  final TripInfo? trip;
  final String? createdAt;
  final String? lastMessage;
  final String? lastMessageAt;

  const ChatSessionResponse({
    required this.conversationId,
    this.tripId,
    this.trip,
    this.createdAt,
    this.lastMessage,
    this.lastMessageAt,
  });

  factory ChatSessionResponse.fromJson(Map<String, dynamic> json) {
    return ChatSessionResponse(
      conversationId: json['conversation_id'] as String? ?? '',
      tripId: json['trip_id'] as String?,
      trip: json['trip'] != null
          ? TripInfo.fromJson(json['trip'] as Map<String, dynamic>)
          : null,
      createdAt: json['created_at'] as String?,
      lastMessage: json['last_message'] as String?,        lastMessageAt: json['last_message_at'] as String?,
    );
  }

  ChatSessionResponse copyWith({
    String? conversationId,
    String? tripId,
    TripInfo? trip,
    String? createdAt,
    String? lastMessage,
    String? lastMessageAt,
  }) {
    return ChatSessionResponse(
      conversationId: conversationId ?? this.conversationId,
      tripId: tripId ?? this.tripId,
      trip: trip ?? this.trip,
      createdAt: createdAt ?? this.createdAt,
      lastMessage: lastMessage ?? this.lastMessage,
      lastMessageAt: lastMessageAt ?? this.lastMessageAt,
    );
  }

  @override
  List<Object?> get props => [
        conversationId, tripId, trip, createdAt,
        lastMessage, lastMessageAt,
      ];
}

class TripInfo extends Equatable {
  final String? tripId;
  final String? tripName;
  final String? destination;
  final String? status;

  const TripInfo({this.tripId, this.tripName, this.destination, this.status});

  factory TripInfo.fromJson(Map<String, dynamic> json) {
    return TripInfo(
      tripId: json['trip_id'] as String?,
      tripName: json['trip_name'] as String?,
      destination: json['destination'] as String?,
      status: json['status'] as String?,
    );
  }

  TripInfo copyWith({
    String? tripId,
    String? tripName,
    String? destination,
    String? status,
  }) {
    return TripInfo(
      tripId: tripId ?? this.tripId,
      tripName: tripName ?? this.tripName,
      destination: destination ?? this.destination,
      status: status ?? this.status,
    );
  }

  @override
  List<Object?> get props => [tripId, tripName, destination, status];
}
