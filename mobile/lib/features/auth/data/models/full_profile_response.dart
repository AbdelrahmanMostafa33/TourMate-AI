class TripProfileData {
  final String? profileId;
  final String? tripId;
  final String? budgetLevel;
  final String? travelStyle;
  final String? pace;
  final List<String>? interests;
  final List<String>? foodPreferences;
  final List<String>? accommodationPreferences;

  TripProfileData({
    this.profileId,
    this.tripId,
    this.budgetLevel,
    this.travelStyle,
    this.pace,
    this.interests,
    this.foodPreferences,
    this.accommodationPreferences,
  });

  factory TripProfileData.fromJson(Map<String, dynamic> json) {
    return TripProfileData(
      profileId: json['profile_id'],
      tripId: json['trip_id'],
      budgetLevel: json['budget_level'],
      travelStyle: json['travel_style'],
      pace: json['pace'],
      interests: (json['interests'] as List?)?.map((e) => e.toString()).toList(),
      foodPreferences: (json['food_preferences'] as List?)?.map((e) => e.toString()).toList(),
      accommodationPreferences: (json['accommodation_preferences'] as List?)?.map((e) => e.toString()).toList(),
    );
  }
}

class FullProfileResponse {
  final String userId;
  final String? fullName;
  final String email;
  final String? phoneNumber;
  final String? homeCity;
  final String? registrationDate;
  final String? travelerPersona;
  final TripProfileData? tripProfile;

  FullProfileResponse({
    required this.userId,
    this.fullName,
    required this.email,
    this.phoneNumber,
    this.homeCity,
    this.registrationDate,
    this.travelerPersona,
    this.tripProfile,
  });

  factory FullProfileResponse.fromJson(Map<String, dynamic> json) {
    return FullProfileResponse(
      userId: json['user_id'] ?? '',
      fullName: json['full_name'],
      email: json['email'] ?? '',
      phoneNumber: json['phone_number'],
      homeCity: json['home_city'],
      registrationDate: json['registration_date'],
      travelerPersona: json['traveler_persona'],
      tripProfile: json['trip_profile'] != null
          ? TripProfileData.fromJson(json['trip_profile'])
          : null,
    );
  }
}