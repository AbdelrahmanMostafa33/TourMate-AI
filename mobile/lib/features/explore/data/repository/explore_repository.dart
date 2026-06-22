import '../../../../core/network/api_services.dart';
import '../models/place_model.dart';

class ExploreRepository {
  final ApiServices api;

  ExploreRepository(this.api);

  /// Fetch explore places with optional filters.
  /// Returns a tuple of (places, total).
  Future<({List<PlaceModel> places, int total})> explorePlaces({
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

      final placesList = (response['places'] as List<dynamic>)
          .map((e) => PlaceModel.fromJson(e as Map<String, dynamic>))
          .toList();

      final total = (response['total'] as num?)?.toInt() ?? placesList.length;

      return (places: placesList, total: total);
    } catch (e) {
      throw Exception('Failed to load places: $e');
    }
  }

  /// Fetch available cities from the explore/filters endpoint.
  Future<List<String>> getExploreFilters() async {
    try {
      final response = await api.getExploreFilters(null, 200);
      final locations = response['locations'] as List<dynamic>? ?? [];
      final cities = <String>{};
      for (final loc in locations) {
        final city = loc['city'] as String?;
        if (city != null && city.isNotEmpty) {
          cities.add(city);
        }
      }
      final sorted = cities.toList()..sort();
      return sorted;
    } catch (e) {
      return [];
    }
  }

  /// Get all saved places for the current user.
  /// Returns a mapping of place_id → saved_place_id, plus the raw list.
  Future<({
    Map<String, String> placeIdToSavedId,
    List<Map<String, dynamic>> raw,
  })> getSavedPlaces() async {
    try {
      final response = await api.getSavedPlaces();
      final list = (response as List<dynamic>).cast<Map<String, dynamic>>();
      final mapping = <String, String>{};
      for (final item in list) {
        final placeId = item['place_id'] as String?;
        final savedId = item['saved_place_id'] as String?;
        if (placeId != null && savedId != null) {
          mapping[placeId] = savedId;
        }
      }
      return (placeIdToSavedId: mapping, raw: list);
    } catch (e) {
      return (placeIdToSavedId: <String, String>{}, raw: <Map<String, dynamic>>[]);
    }
  }

  /// Save a place for the current user.
  Future<void> savePlace(String placeId) async {
    await api.savePlace({'place_id': placeId});
  }

  /// Un-save a place by its saved_place_id.
  Future<void> unsavePlace(String savedPlaceId) async {
    await api.unsavePlace(savedPlaceId);
  }
}
