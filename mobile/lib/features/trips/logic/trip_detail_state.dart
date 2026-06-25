import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/trip_detail_model.dart';
import '../data/models/trip_profile_data.dart';

part 'trip_detail_state.freezed.dart';

@freezed
class TripDetailState with _$TripDetailState {
  const factory TripDetailState.initial() = _Initial;

  const factory TripDetailState.loading() = _Loading;

  const factory TripDetailState.loaded({
    required TripDetailModel trip,
    TripProfileData? profile,
  }) = _Loaded;

  const factory TripDetailState.error(String message) = _Error;
}
