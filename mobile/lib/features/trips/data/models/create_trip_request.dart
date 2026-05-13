class CreateTripRequest {
  final String destinationCity;
  final String destinationCountry;
  final String? startDate;
  final String? endDate;
  final double? budgetTotal;
  final int? travelerCount;
  final String? preferences;
  final String inputMode;

  CreateTripRequest({
    required this.destinationCity,
    required this.destinationCountry,
    this.startDate,
    this.endDate,
    this.budgetTotal,
    this.travelerCount,
    this.preferences,
    this.inputMode = "manual", // default value
  });

  factory CreateTripRequest.fromJson(Map<String, dynamic> json) {
    return CreateTripRequest(
      destinationCity: json['destination_city'],
      destinationCountry: json['destination_country'],
      startDate: json['start_date'],
      endDate: json['end_date'],
      budgetTotal: json['budget_total']?.toDouble(),
      travelerCount: json['traveler_count'],
      preferences: json['preferences'],
      inputMode: json['input_mode'] ?? "manual",
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'destination_city': destinationCity,
      'destination_country': destinationCountry,
      'start_date': startDate,
      'end_date': endDate,
      'budget_total': budgetTotal,
      'traveler_count': travelerCount,
      'preferences': preferences,
      'input_mode': inputMode,
    };
  }
}