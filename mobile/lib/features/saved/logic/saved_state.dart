import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/saved_place_item.dart';

part 'saved_state.freezed.dart';

@freezed
class SavedState with _$SavedState {
  const factory SavedState.initial() = _Initial;

  const factory SavedState.loading() = _Loading;

  const factory SavedState.loaded(List<SavedPlaceItem> items) = _Loaded;

  const factory SavedState.error(String message) = _Error;
}
