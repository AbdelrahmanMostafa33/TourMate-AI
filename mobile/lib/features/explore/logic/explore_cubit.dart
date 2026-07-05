import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/errors/api_result.dart';
import '../data/models/place_model.dart';
import '../data/repository/explore_repository.dart';
import 'explore_state.dart';

class ExploreCubit extends Cubit<ExploreState> {
  final ExploreRepository _repo;

  List<String> _availableCities = [];

  /// Internal mapping: place_id → saved_place_id (used for unsave)
  Map<String, String> _savedPlaceIdMap = {};

  /// Current search query
  String _currentQuery = '';

  /// Recent search history (max 10)
  List<String> _recentSearches = [];
  static const _recentSearchesKey = 'explore_recent_searches';
  static const _maxRecentSearches = 10;

  ExploreCubit(this._repo) : super(const ExploreState.initial());

  @override
  void onChange(Change<ExploreState> change) {
    super.onChange(change);
  }

  @override
  Future<void> close() {
    return super.close();
  }

  /// All available cities from the filters endpoint.
  List<String> get availableCities => _availableCities;

  /// Current search query.
  String get currentQuery => _currentQuery;

  /// Recent search history.
  List<String> get recentSearches => List.unmodifiable(_recentSearches);

  /// Load recent searches from SharedPreferences.
  Future<void> _loadRecentSearches() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _recentSearches = prefs.getStringList(_recentSearchesKey) ?? [];
    } catch (_) {
      _recentSearches = [];
    }
  }

  /// Persist recent searches to SharedPreferences.
  Future<void> _persistRecentSearches() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_recentSearchesKey, _recentSearches);
    } catch (_) {
      // Silently fail — history won't persist
    }
  }

  /// Save a search to recent history (most recent first, deduplicated).
  void _addRecentSearch(String query) {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;
    _recentSearches.remove(trimmed);
    _recentSearches.insert(0, trimmed);
    if (_recentSearches.length > _maxRecentSearches) {
      _recentSearches = _recentSearches.sublist(0, _maxRecentSearches);
    }
    _persistRecentSearches();
  }

  /// Remove a single recent search.
  void removeRecentSearch(String query) {
    _recentSearches.remove(query);
    _persistRecentSearches();
    _emitIfLoaded();
  }

  /// Clear all recent searches.
  void clearRecentSearches() {
    _recentSearches.clear();
    _persistRecentSearches();
    _emitIfLoaded();
  }

  /// Re-emit current state so UI rebuilds with updated history.
  void _emitIfLoaded() {
    state.maybeWhen(
      loaded: (places, total, isLoadingMore, isLoadingResults, selectedCity, selectedCategory, savedPlaceIds) {
        emit(ExploreState.loaded(
          places: places,
          total: total,
          isLoadingMore: isLoadingMore,
          isLoadingResults: isLoadingResults,
          selectedCity: selectedCity,
          selectedCategory: selectedCategory,
          savedPlaceIds: savedPlaceIds,
        ));
      },
      orElse: () {},
    );
  }

  /// Load filters, saved places, first page of places, and search history.
  Future<void> init() async {
    emit(const ExploreState.loading());
    try {
      final citiesResult = await _repo.getExploreFilters();
      citiesResult.when(
        success: (cities) => _availableCities = cities,
        failure: (_) => _availableCities = [],
      );

      await _loadRecentSearches();

      final savedResult = await _repo.getSavedPlaces();
      savedResult.when(
        success: (data) => _savedPlaceIdMap = data.placeIdToSavedId,
        failure: (_) => _savedPlaceIdMap = {},
      );
      final savedIds = _savedPlaceIdMap.keys.toSet();

      final placesResult = await _repo.explorePlaces(city: null, category: null);
      placesResult.when(
        success: (result) => emit(ExploreState.loaded(
          places: result.places,
          total: result.total,
          isLoadingMore: false,
          selectedCity: null,
          selectedCategory: null,
          savedPlaceIds: savedIds,
        )),
        failure: (msg) => emit(ExploreState.error(msg)),
      );
    } catch (e) {
      emit(ExploreState.error(e.toString()));
    }
  }

  /// Change the city filter and reload.
  Future<void> setCity(String? city) async {
    String? cat;
    Set<String> saved = {};
    List<PlaceModel> currentPlaces = [];
    int currentTotal = 0;
    state.maybeWhen(
      loaded: (p, t, _, _, _, ct, s) {
        currentPlaces = p;
        currentTotal = t;
        cat = ct;
        saved = s;
      },
      orElse: () {},
    );
    // Show shimmer on existing results instead of full spinner
    emit(ExploreState.loaded(
      places: currentPlaces,
      total: currentTotal,
      isLoadingMore: false,
      isLoadingResults: true,
      selectedCity: city,
      selectedCategory: cat,
      savedPlaceIds: saved,
    ));
    try {
      final result = await _repo.explorePlaces(city: city, category: cat);
      result.when(
        success: (data) => emit(ExploreState.loaded(
          places: data.places,
          total: data.total,
          isLoadingMore: false,
          selectedCity: city,
          selectedCategory: cat,
          savedPlaceIds: saved,
        )),
        failure: (_) {
          // Revert to previous results on error
          emit(ExploreState.loaded(
            places: currentPlaces,
            total: currentTotal,
            isLoadingMore: false,
            selectedCity: city,
            selectedCategory: cat,
            savedPlaceIds: saved,
          ));
        },
      );
    } catch (e) {
      // Revert to previous results on error
      emit(ExploreState.loaded(
        places: currentPlaces,
        total: currentTotal,
        isLoadingMore: false,
        selectedCity: city,
        selectedCategory: cat,
        savedPlaceIds: saved,
      ));
    }
  }

  /// Change the category filter and reload.
  Future<void> setCategory(String? category) async {
    String? city;
    Set<String> saved = {};
    List<PlaceModel> currentPlaces = [];
    int currentTotal = 0;
    state.maybeWhen(
      loaded: (p, t, _, _, c, _, s) {
        currentPlaces = p;
        currentTotal = t;
        city = c;
        saved = s;
      },
      orElse: () {},
    );
    // Show shimmer on existing results instead of full spinner
    emit(ExploreState.loaded(
      places: currentPlaces,
      total: currentTotal,
      isLoadingMore: false,
      isLoadingResults: true,
      selectedCity: city,
      selectedCategory: category,
      savedPlaceIds: saved,
    ));
    try {
      final result = await _repo.explorePlaces(city: city, category: category);
      result.when(
        success: (data) => emit(ExploreState.loaded(
          places: data.places,
          total: data.total,
          isLoadingMore: false,
          selectedCity: city,
          selectedCategory: category,
          savedPlaceIds: saved,
        )),
        failure: (_) {
          // Revert to previous results on error
          emit(ExploreState.loaded(
            places: currentPlaces,
            total: currentTotal,
            isLoadingMore: false,
            selectedCity: city,
            selectedCategory: category,
            savedPlaceIds: saved,
          ));
        },
      );
    } catch (e) {
      // Revert to previous results on error
      emit(ExploreState.loaded(
        places: currentPlaces,
        total: currentTotal,
        isLoadingMore: false,
        selectedCity: city,
        selectedCategory: category,
        savedPlaceIds: saved,
      ));
    }
  }

  /// Search places using semantic search (embeddings).
  /// Only called when the user explicitly submits (button tap or keyboard action).
  Future<void> searchPlaces(String query) async {
    _currentQuery = query.trim();

    if (_currentQuery.isEmpty) {
      clearSearch();
      return;
    }

    // Save to recent history
    _addRecentSearch(_currentQuery);

String? city;
String? cat;
Set<String> saved = {};
List<PlaceModel> currentPlaces = [];
int currentTotal = 0;
state.maybeWhen(
  loaded: (p, t, _, _, c, ct, s) {
    currentPlaces = p;
    currentTotal = t;
    city = c;
    cat = ct;
    saved = s;
  },
  orElse: () {},
);
// Show shimmer overlay on existing results instead of full spinner
emit(ExploreState.loaded(
  places: currentPlaces,
  total: currentTotal,
  isLoadingMore: false,
  isLoadingResults: true,
  selectedCity: city,
  selectedCategory: cat,
  savedPlaceIds: saved,
));
try {
  final result = await _repo.semanticSearch(
    query: _currentQuery,
    city: city,
    category: cat,
  );
  result.when(
    success: (data) => emit(ExploreState.loaded(
      places: data.places,
      total: data.total,
      isLoadingMore: false,
      isLoadingResults: false,
      selectedCity: city,
      selectedCategory: cat,
      savedPlaceIds: saved,
    )),
    failure: (_) {
      emit(ExploreState.loaded(
        places: currentPlaces,
        total: currentTotal,
        isLoadingMore: false,
        isLoadingResults: false,
        selectedCity: city,
        selectedCategory: cat,
        savedPlaceIds: saved,
      ));
    },
  );
} catch (e) {
  emit(ExploreState.loaded(
    places: currentPlaces,
    total: currentTotal,
    isLoadingMore: false,
    isLoadingResults: false,
    selectedCity: city,
    selectedCategory: cat,
    savedPlaceIds: saved,
  ));
}
  }

  /// Clear search and reload normal results.
  void clearSearch() {
    _currentQuery = '';
    // Re-fetch current filters
    String? city;
    String? cat;
    Set<String> saved = {};
    List<PlaceModel> currentPlaces = [];
    int currentTotal = 0;
    state.maybeWhen(
      loaded: (p, t, _, _, c, ct, s) {
        currentPlaces = p;
        currentTotal = t;
        city = c;
        cat = ct;
        saved = s;
      },
      orElse: () {},
    );
    // Show shimmer on existing results instead of full spinner
    emit(ExploreState.loaded(
      places: currentPlaces,
      total: currentTotal,
      isLoadingMore: false,
      isLoadingResults: true,
      selectedCity: city,
      selectedCategory: cat,
      savedPlaceIds: saved,
    ));
    _repo.explorePlaces(city: city, category: cat).then((result) {
      result.when(
        success: (data) => emit(ExploreState.loaded(
          places: data.places,
          total: data.total,
          isLoadingMore: false,
          selectedCity: city,
          selectedCategory: cat,
          savedPlaceIds: saved,
        )),
        failure: (_) {
          // Revert to previous results on error
          emit(ExploreState.loaded(
            places: currentPlaces,
            total: currentTotal,
            isLoadingMore: false,
            selectedCity: city,
            selectedCategory: cat,
            savedPlaceIds: saved,
          ));
        },
      );
    });
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
      loaded: (p, t, lm, _, c, ct, s) { places = p; total = t; loadMore = lm; city = c; cat = ct; saved = s; },
      orElse: () {},
    );
    final isSaved = saved.contains(placeId);
    try {        if (isSaved) {
        final savedId = _savedPlaceIdMap[placeId];
        if (savedId != null) {
          final unsaveResult = await _repo.unsavePlace(savedId);
          unsaveResult.when(
            success: (_) => _savedPlaceIdMap.remove(placeId),
            failure: (_) {},
          );
        }
      } else {
        final saveResult = await _repo.savePlace(placeId);
        saveResult.when(
          success: (_) async {
            // Re-fetch saved places to get the new saved_place_id mapping
            final freshResult = await _repo.getSavedPlaces();
            freshResult.when(
              success: (data) => _savedPlaceIdMap = data.placeIdToSavedId,
              failure: (_) {},
            );
          },
          failure: (_) {},
        );
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
