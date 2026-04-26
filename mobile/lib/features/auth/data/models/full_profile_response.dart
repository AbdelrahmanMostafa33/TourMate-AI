class FullProfileResponse {
  final String userId;
  final String fullName;
  final String email;
  final String role;
  final bool isActive;
  final bool quizCompleted;

  final String? personaName;
  final String? personaBio;

  final int? age;
  final List<String>? interests;

  FullProfileResponse({
    required this.userId,
    required this.fullName,
    required this.email,
    required this.role,
    required this.isActive,
    required this.quizCompleted,
    this.personaName,
    this.personaBio,
    this.age,
    this.interests,
  });

  factory FullProfileResponse.fromJson(Map<String, dynamic> json) {
    return FullProfileResponse(
      userId: json['user_id'],
      fullName: json['full_name'],
      email: json['email'],
      role: json['role'],
      isActive: json['is_active'],
      quizCompleted: json['quiz_completed'],
      personaName: json['persona_name'],
      personaBio: json['persona_bio'],
      age: json['age'],
      interests: (json['interests'] as List?)?.map((e) => e.toString()).toList(),
    );
  }
}