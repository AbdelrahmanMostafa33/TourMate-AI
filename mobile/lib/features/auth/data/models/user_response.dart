class UserResponse {

  final String userId;
  final String fullName;
  final String email;
  final String? phone;
  final bool isActive;
  final String role;

  UserResponse({
    required this.userId,
    required this.fullName,
    required this.email,
    this.phone,
    required this.isActive,
    required this.role,
  });

  factory UserResponse.fromJson(Map<String,dynamic> json){

    return UserResponse(
      userId: json["user_id"],
      fullName: json["full_name"],
      email: json["email"],
      phone: json["phone"],
      isActive: json["is_active"],
      role: json["role"],
    );
  }
}