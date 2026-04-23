class RegisterRequest {

  final String fullName;
  final String? phone;

  RegisterRequest({
    required this.fullName,
    this.phone,
  });

  Map<String, dynamic> toJson() {
    return {
      "full_name": fullName,
      "phone": phone,
    };
  }
}