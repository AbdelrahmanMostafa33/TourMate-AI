import 'package:freezed_annotation/freezed_annotation.dart';
import '../../explore/data/models/place_model.dart';

part 'place_detail_state.freezed.dart';

@freezed
class PlaceDetailState with _$PlaceDetailState {
  const factory PlaceDetailState.initial() = _Initial;

  const factory PlaceDetailState.loading() = _Loading;

  const factory PlaceDetailState.loaded(PlaceModel place) = _Loaded;

  const factory PlaceDetailState.error(String message) = _Error;
}
