import 'package:equatable/equatable.dart';

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

class FullProfileResponse extends Equatable {
  final String userId;
  final String? fullName;
  final String email;
  final String? phoneNumber;
  final String? homeCity;
  final String? registrationDate;
  final String? travelerPersona;
  final TripProfileData? tripProfile;

  const FullProfileResponse({
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

  FullProfileResponse copyWith({
    String? userId,
    String? fullName,
    String? email,
    String? phoneNumber,
    String? homeCity,
    String? registrationDate,
    String? travelerPersona,
    TripProfileData? tripProfile,
  }) {
    return FullProfileResponse(
      userId: userId ?? this.userId,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      homeCity: homeCity ?? this.homeCity,
      registrationDate: registrationDate ?? this.registrationDate,
      travelerPersona: travelerPersona ?? this.travelerPersona,
      tripProfile: tripProfile ?? this.tripProfile,
    );
  }

  @override
  List<Object?> get props => [
        userId, fullName, email, phoneNumber, homeCity,
        registrationDate, travelerPersona, tripProfile,
      ];
}