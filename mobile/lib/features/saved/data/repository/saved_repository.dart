import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../models/saved_place_item.dart';

class SavedRepository {
  final ApiServices _api;

  SavedRepository(this._api);

  /// Fetch all saved places for the current user.
  Future<ApiResult<List<SavedPlaceItem>>> getSavedPlaces() async {
    try {
      final list = await _api.getSavedPlaces();
      return ApiResult.success(list);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Un-save a place by its saved_place_id.
  Future<ApiResult<void>> unsavePlace(String savedPlaceId) async {
    try {
      await _api.unsavePlace(savedPlaceId);
      return const ApiResult.success(null);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}
