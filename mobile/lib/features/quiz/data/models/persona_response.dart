class PersonaResponse {
  final String personaName;
  final String personaBio;
  final List<String> interests;
  final List<String> suggestedQuestions;
  final bool quizCompleted;

  const PersonaResponse({
    required this.personaName,
    required this.personaBio,
    required this.interests,
    required this.suggestedQuestions,
    required this.quizCompleted,
  });

  factory PersonaResponse.fromJson(Map<String, dynamic> json) {
    return PersonaResponse(
      personaName: json['persona_name'] as String? ?? 'The Open Explorer',
      personaBio: json['persona_bio'] as String? ?? '',
      interests: List<String>.from(json['interests'] ?? []),
      suggestedQuestions:
      List<String>.from(json['suggested_questions'] ?? []),
      quizCompleted: json['quiz_completed'] as bool? ?? false,
    );
  }
}