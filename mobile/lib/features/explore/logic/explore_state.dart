import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/place_model.dart';

part 'explore_state.freezed.dart';

@freezed
class ExploreState with _$ExploreState {
  const factory ExploreState.initial() = _Initial;

  const factory ExploreState.loading() = _Loading;

  const factory ExploreState.loaded({
    required List<PlaceModel> places,
    required int total,
    required bool isLoadingMore,
    @Default(false) bool isLoadingResults,
    String? selectedCity,
    String? selectedCategory,
    @Default(<String>{}) Set<String> savedPlaceIds,
  }) = _Loaded;

  const factory ExploreState.error(String message) = _Error;
}
