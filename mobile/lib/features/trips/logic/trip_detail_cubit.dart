import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_services.dart';
import '../data/models/trip_detail_model.dart';
import 'trip_detail_state.dart';

class TripDetailCubit extends Cubit<TripDetailState> {
  final ApiServices _api;

  TripDetailCubit(this._api) : super(const TripDetailState.initial());

  /// Fetch full trip detail by ID.
  Future<void> fetchTripDetail(String tripId) async {
    emit(const TripDetailState.loading());
    try {
      final json = await _api.getTripDetail(tripId);
      final trip = TripDetailModel.fromJson(json);
      emit(TripDetailState.loaded(trip));
    } catch (e) {
      emit(TripDetailState.error(e.toString()));
    }
  }
}
