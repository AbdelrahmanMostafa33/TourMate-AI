import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../../../quiz/data/models/persona_response.dart';

class ProfileRepository {
  final ApiServices api;

  ProfileRepository(this.api);

  Future<ApiResult<PersonaResponse>> getProfile() async {
    try {
      final res = await api.getProfile();
      return ApiResult.success(res);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}