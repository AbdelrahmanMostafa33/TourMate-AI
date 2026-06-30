import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/api_services.dart';
import '../data/models/trip_profile_data.dart';
import 'trip_detail_state.dart';

class TripDetailCubit extends Cubit<TripDetailState> {
  final ApiServices _api;
  Timer? _pollTimer;
  int _pollAttempts = 0;
  static const int _maxPollAttempts = 20; // 60 seconds max (20 × 3s)
  static const Duration _pollInterval = Duration(seconds: 3);

  TripDetailCubit(this._api) : super(const TripDetailState.initial());

  /// Fetch full trip detail and trip profile by ID.
  /// If the trip status is "planning", starts auto-polling until the
  /// status changes to something payment-relevant (or max attempts reached).
  Future<void> fetchTripDetail(String tripId) async {
    emit(const TripDetailState.loading());
    _cancelPoll();
    try {
      // Fetch trip detail first (required)
      final trip = await _api.getTripDetail(tripId);

      // Fetch trip profile separately (optional — failures are ignored)
      TripProfileData? profile;
      try {
        profile = await _api.getTripProfile(tripId);
      } catch (_) {
        // Profile is optional; continue without it
      }

      emit(TripDetailState.loaded(trip: trip, profile: profile));

      // Start polling if the backend is still processing the approval
      _startPollIfNeeded(tripId, trip.status);
    } catch (e) {
      emit(TripDetailState.error(e.toString()));
    }
  }

  /// Start polling every 3s if trip status is "planning" (backend is still
  /// processing the approval from Pay Now).  Stops when the status changes
  /// to something other than "planning" or after 20 attempts (~60s).
  void _startPollIfNeeded(String tripId, String currentStatus) {
    if (currentStatus.toLowerCase() != 'planning') return;

    _cancelPoll();
    _pollAttempts = 0;
    debugPrint('[TripDetailCubit] Starting poll for trip $tripId (status=planning)');

    _pollTimer = Timer.periodic(_pollInterval, (_) async {
      _pollAttempts++;
      if (_pollAttempts > _maxPollAttempts) {
        debugPrint('[TripDetailCubit] Poll limit reached for trip $tripId');
        _cancelPoll();
        return;
      }

      try {
        final trip = await _api.getTripDetail(tripId);
        if (trip.status.toLowerCase() != 'planning') {
          debugPrint('[TripDetailCubit] Status changed to ${trip.status} — stopping poll');
          _cancelPoll();

          // Fetch profile too for the new status
          TripProfileData? profile;
          try {
            profile = await _api.getTripProfile(tripId);
          } catch (_) {}

          if (!isClosed) {
            emit(TripDetailState.loaded(trip: trip, profile: profile));
          }
        } else {
          // Emit a loading-like state so the UI can show "Processing..."
          if (!isClosed) {
            emit(TripDetailState.loaded(trip: trip, profile: null));
          }
        }
      } catch (e) {
        debugPrint('[TripDetailCubit] Poll fetch failed: $e');
        // Don't cancel on transient errors — keep trying
      }
    });
  }

  void _cancelPoll() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  /// Delete a trip by ID. Lets the exception propagate so the
  /// caller (screen) can show the actual error message via snackbar.
  Future<void> deleteTrip(String tripId) async {
    await _api.deleteTrip(tripId);
  }

  @override
  Future<void> close() {
    _cancelPoll();
    return super.close();
  }
}
