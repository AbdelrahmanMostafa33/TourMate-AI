import 'package:equatable/equatable.dart';

class TripSummaryModel extends Equatable {
  final String tripId;
  final String? tripName;
  final String destination;
  final String? startDate;
  final String? endDate;
  final int numberOfTravelers;
  final String status;

  const TripSummaryModel({
    required this.tripId,
    this.tripName,
    required this.destination,
    this.startDate,
    this.endDate,
    required this.numberOfTravelers,
    required this.status,
  });

  /// Computed duration in days from start/end dates
  int get durationDays {
    if (startDate == null || endDate == null) return 0;
    try {
      final start = DateTime.parse(startDate!);
      final end = DateTime.parse(endDate!);
      return end.difference(start).inDays + 1;
    } catch (_) {
      return 0;
    }
  }

  factory TripSummaryModel.fromJson(Map<String, dynamic> json) {
    return TripSummaryModel(
      tripId: json['trip_id'] ?? '',
      tripName: json['trip_name'],
      destination: json['destination'] ?? '',
      startDate: json['start_date'],
      endDate: json['end_date'],
      numberOfTravelers: json['number_of_travelers'] ?? 1,
      status: json['status'] ?? '',
    );
  }

  TripSummaryModel copyWith({
    String? tripId,
    String? tripName,
    String? destination,
    String? startDate,
    String? endDate,
    int? numberOfTravelers,
    String? status,
  }) {
    return TripSummaryModel(
      tripId: tripId ?? this.tripId,
      tripName: tripName ?? this.tripName,
      destination: destination ?? this.destination,
      startDate: startDate ?? this.startDate,
      endDate: endDate ?? this.endDate,
      numberOfTravelers: numberOfTravelers ?? this.numberOfTravelers,
      status: status ?? this.status,
    );
  }

  @override
  List<Object?> get props => [
        tripId, tripName, destination, startDate,
        endDate, numberOfTravelers, status,
      ];
}