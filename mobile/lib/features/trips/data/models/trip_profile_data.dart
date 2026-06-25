import 'package:equatable/equatable.dart';

/// Trip profile data associated with a specific trip.
///
/// Trip profiles (budget, style, pace, interests) belong to trips,
/// not to users directly. Users store their own basic info on the
/// `users` table (name, email, phone, etc.).
class TripProfileData extends Equatable {
  final String? profileId;
  final String? tripId;
  final String? budgetLevel;
  final String? travelStyle;
  final String? pace;
  final List<String>? interests;
  final List<String>? foodPreferences;
  final List<String>? accommodationPreferences;

  const TripProfileData({
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

  TripProfileData copyWith({
    String? profileId,
    String? tripId,
    String? budgetLevel,
    String? travelStyle,
    String? pace,
    List<String>? interests,
    List<String>? foodPreferences,
    List<String>? accommodationPreferences,
  }) {
    return TripProfileData(
      profileId: profileId ?? this.profileId,
      tripId: tripId ?? this.tripId,
      budgetLevel: budgetLevel ?? this.budgetLevel,
      travelStyle: travelStyle ?? this.travelStyle,
      pace: pace ?? this.pace,
      interests: interests ?? this.interests,
      foodPreferences: foodPreferences ?? this.foodPreferences,
      accommodationPreferences: accommodationPreferences ?? this.accommodationPreferences,
    );
  }

  @override
  List<Object?> get props => [
        profileId, tripId, budgetLevel, travelStyle,
        pace, interests, foodPreferences,
        accommodationPreferences,
      ];
}
