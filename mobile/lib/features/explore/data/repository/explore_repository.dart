import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../models/place_model.dart';

class ExploreRepository {
  final ApiServices api;

  ExploreRepository(this.api);

  /// Fetch explore places with optional filters.
  Future<ApiResult<({List<PlaceModel> places, int total})>> explorePlaces({
    String? city,
    String? country,
    String? category,
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final response = await api.explorePlaces(
        city,
        country,
        category,
        limit,
        offset,
      );
      return ApiResult.success(
        (places: response.places, total: response.total),
      );
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Fetch available cities from the explore/filters endpoint.
  Future<ApiResult<List<String>>> getExploreFilters() async {
    try {
      final response = await api.getExploreFilters(null, 50);
      final cities = <String>{};
      for (final loc in response.locations) {
        final city = loc.city;
        if (city != null && city.isNotEmpty) {
          cities.add(city);
        }
      }
      final sorted = cities.toList()..sort();
      return ApiResult.success(sorted);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Get all saved places for the current user.
  /// Returns a mapping of place_id → saved_place_id, plus the raw list.
  Future<ApiResult<({
    Map<String, String> placeIdToSavedId,
    List<Map<String, dynamic>> raw,
  })>> getSavedPlaces() async {
    try {
      final list = await api.getSavedPlaces();
      // API returns List<SavedPlaceItem>, but we need the raw JSON for the mapping.
      // Re-fetch via the raw API call isn't ideal, so build the mapping from the typed objects.
      final mapping = <String, String>{};
      final rawList = <Map<String, dynamic>>[];
      for (final item in list) {
        mapping[item.placeId] = item.savedPlaceId;
        rawList.add({
          'place_id': item.placeId,
          'saved_place_id': item.savedPlaceId,
        });
      }
      return ApiResult.success((placeIdToSavedId: mapping, raw: rawList));
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Save a place for the current user.
  Future<ApiResult<void>> savePlace(String placeId) async {
    try {
      await api.savePlace({'place_id': placeId});
      return const ApiResult.success(null);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Un-save a place by its saved_place_id.
  Future<ApiResult<void>> unsavePlace(String savedPlaceId) async {
    try {
      await api.unsavePlace(savedPlaceId);
      return const ApiResult.success(null);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Semantic search using embeddings.
  /// Returns places ranked by semantic similarity to the query.
  Future<ApiResult<({List<PlaceModel> places, int total, String query})>> semanticSearch({
    required String query,
    String? city,
    String? category,
    int limit = 20,
  }) async {
    try {
      final response = await api.semanticSearchPlaces({
        'query': query,
        // ignore: use_null_aware_elements – `?` applies to the key, not the value
        if (city != null) 'city': city,
        // ignore: use_null_aware_elements – `?` applies to the key, not the value
        if (category != null) 'category': category,
        'limit': limit,
      });
      return ApiResult.success(
        (places: response.places, total: response.total, query: query),
      );
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}
