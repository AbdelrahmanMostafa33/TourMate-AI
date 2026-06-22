import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../models/full_profile_response.dart';

class ProfileRepository {
  final ApiServices api;

  ProfileRepository(this.api);

  Future<ApiResult<FullProfileResponse>> getProfile() async {
    try {
      final res = await api.getProfile();
      return ApiResult.success(res);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  Future<ApiResult<FullProfileResponse>> updateProfile({
    String? fullName,
    String? phoneNumber,
    String? homeCity,
  }) async {
    try {
      final body = <String, dynamic>{};
      if (fullName != null) body['full_name'] = fullName;
      if (phoneNumber != null) body['phone_number'] = phoneNumber;
      if (homeCity != null) body['home_city'] = homeCity;

      final res = await api.updateProfile(body);
      return ApiResult.success(res);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}