class TripSummaryModel {
  final String tripId;
  final String destinationCity;
  final String destinationCountry;
  final String? startDate;
  final String? endDate;
  final int durationDays;
  final String status;

  TripSummaryModel({
    required this.tripId,
    required this.destinationCity,
    required this.destinationCountry,
    this.startDate,
    this.endDate,
    required this.durationDays,
    required this.status,
  });

  factory TripSummaryModel.fromJson(Map<String, dynamic> json) {
    return TripSummaryModel(
      tripId: json['trip_id'],
      destinationCity: json['destination_city'],
      destinationCountry: json['destination_country'],
      startDate: json['start_date'],
      endDate: json['end_date'],
      durationDays: json['duration_days'],
      status: json['status'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'trip_id': tripId,
      'destination_city': destinationCity,
      'destination_country': destinationCountry,
      'start_date': startDate,
      'end_date': endDate,
      'duration_days': durationDays,
      'status': status,
    };
  }
}