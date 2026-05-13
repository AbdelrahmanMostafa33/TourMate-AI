import 'package:flutter_bloc/flutter_bloc.dart';
import '../data/models/create_trip_request.dart';
import '../data/repository/trips_repository.dart';
import 'trips_state.dart';

class TripsCubit extends Cubit<TripsState> {
  final TripsRepository repo;

  TripsCubit(this.repo) : super(const TripsState.initial());

  // ✅ Get all trips
  Future<void> getTrips() async {
    emit(const TripsState.loading());
    try {
      final trips = await repo.getTrips();
      emit(TripsState.loaded(trips));
    } catch (e) {
      emit(TripsState.error(e.toString()));
    }
  }

  // ✅ Create trip (THIS replaces CreateTripCubit)
  Future<void> createTrip(CreateTripRequest request) async {
    emit(const TripsState.creating());
    try {
      await repo.createTrip(request);

      // Option 1: just emit success
      emit(const TripsState.created());

      // Option 2 (better UX): refresh trips automatically
      await getTrips();

    } catch (e) {
      emit(TripsState.error(e.toString()));
    }
  }
}