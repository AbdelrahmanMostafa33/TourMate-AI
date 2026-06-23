import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../models/create_trip_request.dart';
import '../models/trip_summary_model.dart';

class TripsRepository {
  final ApiServices api;

  TripsRepository(this.api);

  Future<ApiResult<List<TripSummaryModel>>> getTrips() async {
    try {
      final trips = await api.getTrips();
      return ApiResult.success(trips);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  Future<ApiResult<void>> createTrip(CreateTripRequest request) async {
    try {
      await api.createTrip(request.toJson());
      return const ApiResult.success(null);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  Future<ApiResult<void>> deleteTrip(String tripId) async {
    try {
      await api.deleteTrip(tripId);
      return const ApiResult.success(null);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }
}