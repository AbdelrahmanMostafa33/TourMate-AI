import '../../../../core/errors/api_result.dart';
import '../../data/models/persona_response.dart';

class QuizRepository {
  QuizRepository();

  /// Skip quiz → default persona (no backend endpoint — returns default)
  Future<ApiResult<PersonaResponse>> skipQuiz() async {
    return ApiResult.success(const PersonaResponse(
      personaName: 'The Open Explorer',
      personaBio: 'A curious traveler ready to explore the world.',
      interests: [],
      suggestedQuestions: [],
      quizCompleted: false,
    ));
  }

  /// Submit quiz (no backend endpoint — returns default)
  Future<ApiResult<PersonaResponse>> submitQuiz(
      Map<String, dynamic> body) async {
    return ApiResult.success(const PersonaResponse(
      personaName: 'The Open Explorer',
      personaBio: 'A curious traveler ready to explore the world.',
      interests: [],
      suggestedQuestions: [],
      quizCompleted: false,
    ));
  }
}