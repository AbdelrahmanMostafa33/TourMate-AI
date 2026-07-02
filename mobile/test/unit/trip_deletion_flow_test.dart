import 'package:flutter_test/flutter_test.dart';

import 'package:tourmate/core/errors/api_result.dart';
import 'package:tourmate/core/network/api_services.dart';
import 'package:tourmate/features/trips/data/models/create_trip_request.dart';
import 'package:tourmate/features/trips/data/models/trip_summary_model.dart';
import 'package:tourmate/features/trips/data/repository/trips_repository.dart';
import 'package:tourmate/features/trips/logic/trips_cubit.dart';
import 'package:tourmate/features/trips/logic/trips_state.dart';

// ── Helpers ──────────────────────────────────────────────────────────────

/// Extract trips from state, returning empty list for non-loaded states.
List<TripSummaryModel> _tripsFromState(TripsState state) {
  return state.maybeWhen(
    loaded: (trips) => trips,
    orElse: () => <TripSummaryModel>[],
  );
}

/// Returns true when the state is the [TripsState] loaded variant.
bool _isLoaded(TripsState state) {
  return state.maybeWhen(loaded: (_) => true, orElse: () => false);
}

/// Returns true when the state is the [TripsState] error variant.
String? _errorMessage(TripsState state) {
  return state.maybeWhen(error: (msg) => msg, orElse: () => null);
}

// ── Test Data ────────────────────────────────────────────────────────────

TripSummaryModel _trip(String id, {String destination = 'Cairo'}) {
  return TripSummaryModel(
    tripId: id,
    destination: destination,
    numberOfTravelers: 1,
    status: 'planning',
  );
}

final _cairo = _trip('trip-1', destination: 'Cairo');
final _luxor = _trip('trip-2', destination: 'Luxor');
final _aswan = _trip('trip-3', destination: 'Aswan');

// ── Fake TripsRepository ─────────────────────────────────────────────────

class FakeTripsRepository implements TripsRepository {
  /// The [api] field satisfies the interface but is never used in tests —
  /// all repository methods are overridden by this fake.
  @override
  ApiServices get api => throw UnimplementedError('ApiServices not needed in tests');

  List<TripSummaryModel>? storedTrips;
  bool shouldFailGetTrips = false;
  bool shouldFailDeleteTrip = false;
  String? lastDeletedTripId;
  int deleteTripCallCount = 0;

  FakeTripsRepository();

  @override
  Future<ApiResult<List<TripSummaryModel>>> getTrips() async {
    if (shouldFailGetTrips) {
      return ApiResult.failure('Failed to fetch trips');
    }
    return ApiResult.success(storedTrips ?? []);
  }

  @override
  Future<ApiResult<void>> createTrip(CreateTripRequest request) async {
    return const ApiResult.success(null);
  }

  @override
  Future<ApiResult<void>> deleteTrip(String tripId) async {
    deleteTripCallCount++;
    lastDeletedTripId = tripId;
    if (shouldFailDeleteTrip) {
      return ApiResult.failure('Failed to delete trip');
    }
    return const ApiResult.success(null);
  }
}

// ── Main Tests ────────────────────────────────────────────────────────────

void main() {
  late FakeTripsRepository repository;
  late TripsCubit cubit;

  setUp(() {
    repository = FakeTripsRepository();
    cubit = TripsCubit(repository);
  });

  tearDown(() async {
    await cubit.close();
  });

  // ── Constructor ─────────────────────────────────────────────────────

  group('constructor', () {
    test('initial state is TripsState.initial()', () {
      expect(cubit.state, const TripsState.initial());
    });
  });

  // ── getTrips ────────────────────────────────────────────────────────

  group('getTrips', () {
    test('loads trips into loaded state', () async {
      repository.storedTrips = [_cairo, _luxor];

      await cubit.getTrips();

      expect(_isLoaded(cubit.state), true);
      expect(_tripsFromState(cubit.state), hasLength(2));
      expect(
        _tripsFromState(cubit.state).map((t) => t.tripId).toList(),
        ['trip-1', 'trip-2'],
      );
    });

    test('loads empty list when no trips exist', () async {
      repository.storedTrips = [];

      await cubit.getTrips();

      expect(_isLoaded(cubit.state), true);
      expect(_tripsFromState(cubit.state), isEmpty);
    });

    test('transitions to error on API failure', () async {
      repository.shouldFailGetTrips = true;

      await cubit.getTrips();

      expect(_errorMessage(cubit.state), contains('Failed to fetch trips'));
    });
  });

  // ── removeTripFromState ─────────────────────────────────────────────

  group('removeTripFromState', () {
    test('removes matching trip from loaded state', () async {
      repository.storedTrips = [_cairo, _luxor, _aswan];
      await cubit.getTrips();

      cubit.removeTripFromState('trip-2'); // Remove Luxor

      expect(_tripsFromState(cubit.state), hasLength(2));
      expect(
        _tripsFromState(cubit.state).map((t) => t.tripId).toList(),
        ['trip-1', 'trip-3'],
      );
    });

    test('removes first trip from loaded state', () async {
      repository.storedTrips = [_cairo, _luxor];
      await cubit.getTrips();

      cubit.removeTripFromState('trip-1');

      expect(_tripsFromState(cubit.state), hasLength(1));
      expect(_tripsFromState(cubit.state).first.tripId, 'trip-2');
    });

    test('removes last trip leaving empty list', () async {
      repository.storedTrips = [_cairo];
      await cubit.getTrips();

      cubit.removeTripFromState('trip-1');

      expect(_tripsFromState(cubit.state), isEmpty);
    });

    test('does nothing when tripId does not match any trip', () async {
      repository.storedTrips = [_cairo, _luxor];
      await cubit.getTrips();

      cubit.removeTripFromState('non-existent-id');

      expect(_tripsFromState(cubit.state), hasLength(2));
      expect(
        _tripsFromState(cubit.state).map((t) => t.tripId).toList(),
        ['trip-1', 'trip-2'],
      );
    });

    test('does nothing when state is initial', () {
      cubit.removeTripFromState('trip-1');

      expect(cubit.state, const TripsState.initial());
    });

    test('does nothing when state is loading', () {
      cubit.emit(const TripsState.loading()); // ignore: invalid_use_of_visible_for_testing_member

      cubit.removeTripFromState('trip-1');

      expect(cubit.state, const TripsState.loading());
    });

    test('does nothing when state is error', () {
      cubit.emit(const TripsState.error('Something went wrong')); // ignore: invalid_use_of_visible_for_testing_member

      cubit.removeTripFromState('trip-1');

      expect(_errorMessage(cubit.state), contains('Something went wrong'));
    });

    test('emits updated state through stream', () async {
      repository.storedTrips = [_cairo, _luxor, _aswan];
      await cubit.getTrips();

      // Stream listener captures the state from removeTripFromState only
      final states = <TripsState>[];
      final sub = cubit.stream.listen(states.add);

      cubit.removeTripFromState('trip-2');
      await Future<void>.delayed(Duration.zero);

      expect(states, hasLength(1));
      final state = states.first;
      expect(
        state.maybeWhen(
          loaded: (trips) => trips.map((t) => t.tripId).toList(),
          orElse: () => <String>[],
        ),
        ['trip-1', 'trip-3'],
      );

      await sub.cancel();
    });

    test('is no-op when cubit is closed', () async {
      repository.storedTrips = [_cairo, _luxor];
      await cubit.getTrips();
      await cubit.close();

      // Should not throw despite cubit being closed
      cubit.removeTripFromState('trip-2');

      // State should remain unchanged
      expect(_isLoaded(cubit.state), true);
      expect(_tripsFromState(cubit.state), hasLength(2));
    });
  });

  // ── removeTripFromState with getTrips refresh ──────────────────────

  group('optimistic removal + server refresh', () {
    test('server refresh confirms the optimistic state', () async {
      repository.storedTrips = [_cairo, _luxor, _aswan];
      await cubit.getTrips();

      // Step 1: Optimistic removal
      cubit.removeTripFromState('trip-2');
      expect(_tripsFromState(cubit.state), hasLength(2));

      // Step 2: Server confirms with full refresh
      repository.storedTrips = [_cairo, _aswan];
      await cubit.getTrips();

      expect(_tripsFromState(cubit.state), hasLength(2));
      expect(
        _tripsFromState(cubit.state).map((t) => t.tripId).toList(),
        ['trip-1', 'trip-3'],
      );
    });
  });

  // ── deleteTrip via repository ──────────────────────────────────────

  group('repository deleteTrip', () {
    test('calls API with correct tripId', () async {
      await repository.deleteTrip('trip-42');

      expect(repository.lastDeletedTripId, 'trip-42');
      expect(repository.deleteTripCallCount, 1);
    });

    test('returns failure on API error', () async {
      repository.shouldFailDeleteTrip = true;

      final result = await repository.deleteTrip('trip-42');

      result.when(
        success: (_) => fail('Expected failure'),
        failure: (msg) => expect(msg, contains('Failed to delete trip')),
      );
    });

    test('can delete multiple trips sequentially', () async {
      await repository.deleteTrip('trip-1');
      await repository.deleteTrip('trip-2');

      expect(repository.deleteTripCallCount, 2);
      expect(repository.lastDeletedTripId, 'trip-2');
    });
  });

  // ── Full deletion flow ────────────────────────────────────────────

  group('full deletion flow', () {
    test('optimistic removal followed by server delete succeeds', () async {
      repository.storedTrips = [_cairo];
      await cubit.getTrips();

      // 1. Optimistic removal
      cubit.removeTripFromState('trip-1');
      expect(_tripsFromState(cubit.state), isEmpty);

      // 2. Server-side delete
      final result = await repository.deleteTrip('trip-1');
      expect(result, isA<ApiResult<void>>());
      expect(repository.lastDeletedTripId, 'trip-1');
    });

    test('server delete failure recovers on next refresh', () async {
      repository.storedTrips = [_cairo];
      await cubit.getTrips();

      // 1. Optimistic removal (UI updates instantly)
      cubit.removeTripFromState('trip-1');
      expect(_tripsFromState(cubit.state), isEmpty);

      // 2. Server delete fails
      repository.shouldFailDeleteTrip = true;
      final result = await repository.deleteTrip('trip-1');
      result.when(
        success: (_) => fail('Expected failure'),
        failure: (_) => {/* Expected */},
      );

      // 3. Refresh from server — trip should still exist because
      //    the server-side delete did not actually go through
      repository.shouldFailDeleteTrip = false;
      repository.storedTrips = [_cairo];
      await cubit.getTrips();

      expect(_tripsFromState(cubit.state), hasLength(1));
      expect(_tripsFromState(cubit.state).first.tripId, 'trip-1');
    });
  });
}
