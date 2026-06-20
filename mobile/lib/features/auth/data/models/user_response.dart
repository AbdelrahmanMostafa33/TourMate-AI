class UserResponse {
  final String userId;
  final String? fullName;
  final String email;
  final String? phoneNumber;
  final String? registrationDate;
  final String? homeCity;
  final String? travelerPersona;
  final String? updatedAt;

  UserResponse({
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
}