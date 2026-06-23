import 'package:equatable/equatable.dart';

class UserResponse extends Equatable {
  final String userId;
  final String? fullName;
  final String email;
  final String? phoneNumber;
  final String? registrationDate;
  final String? homeCity;
  final String? travelerPersona;
  final String? updatedAt;

  const UserResponse({
    required this.userId,
    this.fullName,
    required this.email,
    this.phoneNumber,
    this.registrationDate,
    this.homeCity,
    this.travelerPersona,
    this.updatedAt,
  });

  factory UserResponse.fromJson(Map<String, dynamic> json) {
    return UserResponse(
      userId: json['user_id'] ?? '',
      fullName: json['full_name'],
      email: json['email'] ?? '',
      phoneNumber: json['phone_number'],
      registrationDate: json['registration_date'],
      homeCity: json['home_city'],
      travelerPersona: json['traveler_persona'],
      updatedAt: json['updated_at'],
    );
  }

  UserResponse copyWith({
    String? userId,
    String? fullName,
    String? email,
    String? phoneNumber,
    String? registrationDate,
    String? homeCity,
    String? travelerPersona,
    String? updatedAt,
  }) {
    return UserResponse(
      userId: userId ?? this.userId,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      registrationDate: registrationDate ?? this.registrationDate,
      homeCity: homeCity ?? this.homeCity,
      travelerPersona: travelerPersona ?? this.travelerPersona,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
        userId, fullName, email, phoneNumber,
        registrationDate, homeCity, travelerPersona, updatedAt,
      ];
}