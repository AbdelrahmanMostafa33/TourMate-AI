class RegisterRequest {
  final String fullName;
  final String? phoneNumber;

  RegisterRequest({
    required this.fullName,
    this.phoneNumber,
  });

  Map<String, dynamic> toJson() {
    return {
      "full_name": fullName,
      "phone_number": phoneNumber,
    };
  }
}