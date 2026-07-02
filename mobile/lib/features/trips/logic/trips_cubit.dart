import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/models/create_trip_request.dart';
import '../data/repository/trips_repository.dart';
import 'trips_state.dart';

class TripsCubit extends Cubit<TripsState> {
  final TripsRepository repo;

  TripsCubit(this.repo) : super(const TripsState.initial());

  Future<void> getTrips() async {
    emit(const TripsState.loading());
    final result = await repo.getTrips();
    result.when(
      success: (trips) => emit(TripsState.loaded(trips)),
      failure: (msg) => emit(TripsState.error(msg)),
    );
  }

  Future<void> createTrip(CreateTripRequest request) async {
    emit(const TripsState.creating());
    final result = await repo.createTrip(request);
    result.when(
      success: (_) => emit(const TripsState.created()),
      failure: (msg) => emit(TripsState.error(msg)),
    );
  }

  /// Optimistically remove a trip from the local loaded state after deletion.
  /// This provides instant UI feedback without waiting for a full re-fetch.
  void removeTripFromState(String tripId) {
    if (isClosed) return;
    final current = state;
    current.maybeWhen(
      loaded: (trips) {
        final updated = trips.where((t) => t.tripId != tripId).toList();
        emit(TripsState.loaded(updated));
      },
      orElse: () {},
    );
  }
}