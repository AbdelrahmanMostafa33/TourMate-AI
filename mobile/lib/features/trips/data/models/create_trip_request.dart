class CreateTripRequest {
  final String destination;
  final String? tripName;
  final String? startDate;
  final String? endDate;
  final int? numberOfTravelers;
  final double? budget;
  final List<String>? preferences;

  CreateTripRequest({
    required this.destination,
    this.tripName,
    this.startDate,
    this.endDate,
    this.numberOfTravelers,
    this.budget,
    this.preferences,
  });

  Map<String, dynamic> toJson() {
    return {
      'destination': destination,
      if (tripName != null) 'trip_name': tripName,
      if (startDate != null) 'start_date': startDate,
      if (endDate != null) 'end_date': endDate,
      if (numberOfTravelers != null) 'number_of_travelers': numberOfTravelers,
      if (budget != null) 'budget': budget,
      if (preferences != null) 'preferences': preferences,
    };
  }
}