import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';

import '../../features/auth/data/repository/profile_repository.dart';
import '../../features/auth/data/datasource/firebase_auth_service.dart';
import '../../features/auth/data/repository/auth_repository.dart';
import '../../features/chat/data/datasource/chat_ws_service.dart';
import '../../features/chat/data/repository/chat_repository.dart';
import '../../features/payments/data/datasource/payment_service.dart';
import '../../features/places/data/repository/places_repository.dart';
import '../../features/trips/data/repository/trips_repository.dart';
import '../../features/explore/data/repository/explore_repository.dart';
import '../../features/saved/data/repository/saved_repository.dart';
import '../../features/bookings/data/repository/booking_repository.dart';
import '../../features/flights/data/repository/flight_repository.dart';

import '../network/dio_factory.dart';
import '../network/api_services.dart';




final locator = GetIt.instance;

Future<void> setupLocator() async {

  /// Dio
  locator.registerLazySingleton<Dio>(() => DioFactory.getDio());

  /// API Service
  locator.registerLazySingleton<ApiServices>(
        () => ApiServices(locator<Dio>()),
  );

  /// Firebase Auth Service
  locator.registerLazySingleton<FirebaseAuthService>(
        () => FirebaseAuthService(),
  );

  /// Chat WebSocket Service
  locator.registerLazySingleton(
        () => ChatWebSocketService(locator<FirebaseAuthService>()),
  );

  /// ── Payment Service (Stripe Payment Sheet) ─────────────────────────────
  locator.registerLazySingleton<PaymentService>(
        () => PaymentService(),
  );

  /// Repositories
  locator.registerLazySingleton<AuthRepository>(
        () => AuthRepository(
      locator<ApiServices>(),
      locator<FirebaseAuthService>(),
    ),
  );

  locator.registerLazySingleton<ProfileRepository>(
        () => ProfileRepository(locator<ApiServices>()),
  );

  locator.registerLazySingleton(
        () => ChatRepository(
          locator<ChatWebSocketService>(),
          locator<ApiServices>(),
        ),
  );

  locator.registerLazySingleton(
        () => TripsRepository(locator<ApiServices>()),
  );

  locator.registerLazySingleton(
        () => ExploreRepository(locator<ApiServices>()),
  );

  locator.registerLazySingleton<SavedRepository>(
        () => SavedRepository(locator<ApiServices>()),
  );

  locator.registerLazySingleton<PlacesRepository>(
        () => PlacesRepository(locator<ApiServices>()),
  );

  /// ── Payment / Booking Repositories ─────────────────────────────────────
  locator.registerLazySingleton<BookingRepository>(
        () => BookingRepository(locator<ApiServices>()),
  );

  locator.registerLazySingleton<FlightRepository>(
        () => FlightRepository(locator<ApiServices>()),
  );
}