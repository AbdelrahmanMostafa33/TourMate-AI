import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../../../explore/data/models/place_model.dart';

class PlacesRepository {
  final ApiServices _api;

  PlacesRepository(this._api);

  /// Fetch full place details by ID.
  Future<ApiResult<PlaceModel>> getPlaceDetail(String placeId) async {
    try {
      final place = await _api.getPlaceDetail(placeId);
      return ApiResult.success(place);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}
