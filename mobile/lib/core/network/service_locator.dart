import 'package:get_it/get_it.dart';
import 'package:dio/dio.dart';

import '../../features/auth/data/repository/profile_repository.dart';
import '../../features/quiz/data/repository/quiz_repository.dart';
import '../network/dio_factory.dart';
import '../network/api_services.dart';

import '../../core/auth/firebase_auth_service.dart';
import '../../features/auth/data/repository/auth_repository.dart';

// import '../../features/auth/data/repository/auth_repository.dart';

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

  locator.registerLazySingleton<QuizRepository>(
        () => QuizRepository(locator<ApiServices>()),
  );
}