import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/trip_summary_model.dart';

part 'trips_state.freezed.dart';

@freezed
class TripsState with _$TripsState {
  const factory TripsState.initial() = _Initial;

  const factory TripsState.loading() = _Loading;

  const factory TripsState.loaded(List<TripSummaryModel> trips) = _Loaded;

  const factory TripsState.creating() = _Creating;

  const factory TripsState.created() = _Created;

  const factory TripsState.error(String message) = _Error;
}