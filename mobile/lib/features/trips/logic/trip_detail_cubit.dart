import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_services.dart';
import 'trip_detail_state.dart';

class TripDetailCubit extends Cubit<TripDetailState> {
  final ApiServices _api;

  TripDetailCubit(this._api) : super(const TripDetailState.initial());

  /// Fetch full trip detail by ID.
  Future<void> fetchTripDetail(String tripId) async {
    emit(const TripDetailState.loading());
    try {
      final trip = await _api.getTripDetail(tripId);
      emit(TripDetailState.loaded(trip));
    } catch (e) {
      emit(TripDetailState.error(e.toString()));
    }
  }

  /// Delete a trip by ID. Lets the exception propagate so the
  /// caller (screen) can show the actual error message via snackbar.
  Future<void> deleteTrip(String tripId) async {
    await _api.deleteTrip(tripId);
  }
}
