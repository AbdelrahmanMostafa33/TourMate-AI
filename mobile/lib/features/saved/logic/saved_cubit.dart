import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/models/saved_place_item.dart';
import '../data/repository/saved_repository.dart';
import 'saved_state.dart';

class SavedCubit extends Cubit<SavedState> {
  final SavedRepository _repo;

  SavedCubit(this._repo) : super(const SavedState.initial());

  /// Load all saved places.
  Future<void> load() async {
    emit(const SavedState.loading());
    final result = await _repo.getSavedPlaces();
    result.when(
      success: (items) => emit(SavedState.loaded(items)),
      failure: (msg) => emit(SavedState.error(msg)),
    );
  }

  /// Un-save a place and remove it from the local list immediately.
  Future<void> unsave(String savedPlaceId) async {
    // Optimistic removal
    final previousItems = _currentItems();
    _emitWithFilteredItems(savedPlaceId);

    final result = await _repo.unsavePlace(savedPlaceId);
    result.when(
      success: (_) {},
      failure: (_) {
        // Revert on failure
        emit(SavedState.loaded(previousItems));
      },
    );
  }

  /// Refresh the list (pull-to-refresh).
  Future<void> refresh() async {
    await load();
  }

  // ── Helpers ───────────────────────────────────────────────

  List<SavedPlaceItem> _currentItems() {
    return state.maybeWhen(
      loaded: (items) => items,
      orElse: () => <SavedPlaceItem>[],
    );
  }

  void _emitWithFilteredItems(String savedPlaceId) {
    state.maybeWhen(
      loaded: (items) {
        emit(SavedState.loaded(
          items.where((i) => i.savedPlaceId != savedPlaceId).toList(),
        ));
      },
      orElse: () {},
    );
  }
}
