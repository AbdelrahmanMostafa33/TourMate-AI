import 'dart:developer' as dev;
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_services.dart';
import '../../bookings/data/models/booking_models.dart';
import '../data/models/trip_profile_data.dart';
import 'trip_detail_state.dart';

class TripDetailCubit extends Cubit<TripDetailState> {
  final ApiServices _api;

  TripDetailCubit(this._api) : super(const TripDetailState.initial());

  /// Fetch full trip detail, trip profile, and bookings by ID.
  Future<void> fetchTripDetail(String tripId) async {
    emit(const TripDetailState.loading());
    try {
      final trip = await _api.getTripDetail(tripId);

      // Trip profile is optional — failures are silently ignored.
      TripProfileData? profile;
      try {
        profile = await _api.getTripProfile(tripId);
      } catch (_) {}

      // Bookings are optional — failures are silently ignored,
      // but we log the error for debugging.
      List<BookingResponse> bookings = [];
      try {
        bookings = await _api.listTripBookings(tripId, null);
      } catch (e) {
        dev.log('[TripDetailCubit] Failed to fetch bookings: $e');
      }

      emit(TripDetailState.loaded(
        trip: trip,
        profile: profile,
        bookings: bookings,
      ));
    } catch (e) {
      emit(TripDetailState.error(e.toString()));
    }
  }

  /// Delete a trip by ID. Lets the exception propagate so the
  /// caller (screen) can show the actual error message via snackbar.
  Future<void> deleteTrip(String tripId) async {
    await _api.deleteTrip(tripId);
  }

  /// Cancel an entire trip — cancels all bookings, refunds payments,
  /// and marks the trip as cancelled. Returns the response map with
  /// {cancelled_bookings, refunded_payments} for displaying feedback.
  ///
  /// Does NOT update the local state — the screen handles navigation
  /// and snackbar feedback after a successful cancellation.
  Future<Map<String, dynamic>> cancelTrip(String tripId) async {
    final response = await _api.cancelTrip(tripId);
    return response.data;
  }
}
