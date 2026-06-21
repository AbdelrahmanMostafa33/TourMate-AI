class RegisterRequest {
  final String fullName;
  final String? phoneNumber;
  final String? homeCity;

  RegisterRequest({
    required this.fullName,
    this.phoneNumber,
    this.homeCity,
  });

  Map<String, dynamic> toJson() {
    return {
      "full_name": fullName,
      "phone_number": phoneNumber,
      "home_city": homeCity,
    };
  }
}