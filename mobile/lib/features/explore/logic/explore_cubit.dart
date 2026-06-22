import 'package:flutter_bloc/flutter_bloc.dart';

import '../data/models/place_model.dart';
import '../data/repository/explore_repository.dart';
import 'explore_state.dart';

class ExploreCubit extends Cubit<ExploreState> {
  final ExploreRepository _repo;

  List<String> _availableCities = [];

  /// Internal mapping: place_id → saved_place_id (used for unsave)
  Map<String, String> _savedPlaceIdMap = {};

  ExploreCubit(this._repo) : super(const ExploreState.initial());

  /// All available cities from the filters endpoint.
  List<String> get availableCities => _availableCities;

  /// Load filters, saved places, and first page of places.
  Future<void> init() async {
    emit(const ExploreState.loading());
    try {
      _availableCities = await _repo.getExploreFilters();

      final savedResult = await _repo.getSavedPlaces();
      _savedPlaceIdMap = savedResult.placeIdToSavedId;
      final savedIds = _savedPlaceIdMap.keys.toSet();

      final result = await _repo.explorePlaces(city: null, category: null);
      emit(ExploreState.loaded(
        places: result.places,
        total: result.total,
        isLoadingMore: false,
        selectedCity: null,
        selectedCategory: null,
        savedPlaceIds: savedIds,
      ));
    } catch (e) {
      emit(ExploreState.error(e.toString()));
    }
  }

  /// Change the city filter and reload.
  Future<void> setCity(String? city) async {
    String? cat;
    Set<String> saved = {};
    state.maybeWhen(
      loaded: (_, _, _, _, c, s) { cat = c; saved = s; },
      orElse: () {},
    );
    emit(const ExploreState.loading());
    try {
      final result = await _repo.explorePlaces(city: city, category: cat);
      emit(ExploreState.loaded(
        places: result.places,
        total: result.total,
        isLoadingMore: false,
        selectedCity: city,
        selectedCategory: cat,
        savedPlaceIds: saved,
      ));
    } catch (e) {
      emit(ExploreState.error(e.toString()));
    }
  }

  /// Change the category filter and reload.
  Future<void> setCategory(String? category) async {
    String? city;
    Set<String> saved = {};
    state.maybeWhen(
      loaded: (_, _, _, c, _, s) { city = c; saved = s; },
      orElse: () {},
    );
    emit(const ExploreState.loading());
    try {
      final result = await _repo.explorePlaces(city: city, category: category);
      emit(ExploreState.loaded(
        places: result.places,
        total: result.total,
        isLoadingMore: false,
        selectedCity: city,
        selectedCategory: category,
        savedPlaceIds: saved,
      ));
    } catch (e) {
      emit(ExploreState.error(e.toString()));
    }
  }

  /// Toggle save / un-save a place by its ID.
  Future<void> toggleSave(String placeId) async {
    List<PlaceModel> places = [];
    int total = 0;
    bool loadMore = false;
    String? city;
    String? cat;
    Set<String> saved = {};
    state.maybeWhen(
      loaded: (p, t, lm, c, ct, s) { places = p; total = t; loadMore = lm; city = c; cat = ct; saved = s; },
      orElse: () {},
    );
    final isSaved = saved.contains(placeId);
    try {
      if (isSaved) {
        final savedId = _savedPlaceIdMap[placeId];
        if (savedId != null) {
          await _repo.unsavePlace(savedId);
          _savedPlaceIdMap.remove(placeId);
        }
      } else {
        await _repo.savePlace(placeId);
        // Re-fetch saved places to get the new saved_place_id mapping
        final fresh = await _repo.getSavedPlaces();
        _savedPlaceIdMap = fresh.placeIdToSavedId;
      }
      // Rebuild the saved set from the mapping
      final updated = Set<String>.from(_savedPlaceIdMap.keys);
      emit(ExploreState.loaded(
        places: places,
        total: total,
        isLoadingMore: loadMore,
        selectedCity: city,
        selectedCategory: cat,
        savedPlaceIds: updated,
      ));
    } catch (_) {
      // Silently fail — the heart won't toggle
    }
  }
}
