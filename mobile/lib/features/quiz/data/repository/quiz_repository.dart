import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../../data/models/persona_response.dart';

class QuizRepository {
  final ApiServices api;

  QuizRepository(this.api);

  /// Skip quiz → default persona
  Future<ApiResult<PersonaResponse>> skipQuiz() async {
    try {
      final res = await api.skipQuiz();
      return ApiResult.success(res);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Submit quiz
  Future<ApiResult<PersonaResponse>> submitQuiz(
      Map<String, dynamic> body) async {
    try {
      final res = await api.submitQuiz(body);
      return ApiResult.success(res);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}