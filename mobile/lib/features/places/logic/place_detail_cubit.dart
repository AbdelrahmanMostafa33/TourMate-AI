import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/repository/places_repository.dart';
import 'place_detail_state.dart';

class PlaceDetailCubit extends Cubit<PlaceDetailState> {
  final PlacesRepository _repo;
  final String placeId;

  PlaceDetailCubit(this._repo, this.placeId) : super(const PlaceDetailState.initial()) {
    load();
  }

  Future<void> load() async {
    emit(const PlaceDetailState.loading());
    final result = await _repo.getPlaceDetail(placeId);
    result.when(
      success: (place) => emit(PlaceDetailState.loaded(place)),
      failure: (msg) => emit(PlaceDetailState.error(msg)),
    );
  }
}
