import '../../../../core/network/api_services.dart';
import '../models/create_trip_request.dart';
import '../models/trip_summary_model.dart';

class TripsRepository {
  final ApiServices api;

  TripsRepository(this.api);

  Future<List<TripSummaryModel>> getTrips() async {
    try {
      return await api.getTrips();
    } catch (e) {
      throw Exception("Failed to load trips: $e");
    }
  }

  Future<void> createTrip(CreateTripRequest request) async {
    try {
      await api.createTrip(request.toJson());
    } catch (e) {
      throw Exception("Failed to create trip: $e");
    }
  }
}