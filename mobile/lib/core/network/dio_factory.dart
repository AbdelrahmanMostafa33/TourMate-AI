import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'api_config.dart';

/// Header key used to tag a request that has already been retried after
/// a 401 token refresh, preventing infinite retry loops.
const _kRetryHeader = 'x-retry-after-refresh';

class DioFactory {

  static Dio getDio() {

    final dio = Dio(
      BaseOptions(
        baseUrl: ApiConfig.httpBaseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
        headers: {
          "Accept": "application/json",
        },
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final user = FirebaseAuth.instance.currentUser;

          if (user != null) {
            // Use cached token when available; Firebase auto-refreshes ~1 hr.
            final token = await user.getIdToken();
            options.headers['Authorization'] = 'Bearer $token';
          }

          return handler.next(options);
        },

        onError: (error, handler) async {
          final statusCode = error.response?.statusCode;
          final alreadyRetried = error.requestOptions.headers.containsKey(_kRetryHeader);

          // Only handle 401 and 403 — and only on the first attempt.
          if ((statusCode == 401 || statusCode == 403) && !alreadyRetried) {
            try {
              // Force-refresh the Firebase token.
              final user = FirebaseAuth.instance.currentUser;
              if (user != null) {
                final freshToken = await user.getIdToken(true);

                // Clone the original request with the new token.
                final opts = error.requestOptions;
                opts.headers['Authorization'] = 'Bearer $freshToken';
                opts.headers[_kRetryHeader] = true;

                final response = await dio.fetch<dynamic>(opts);
                return handler.resolve(response);
              }
            } catch (_) {
              // Refresh failed — fall through and rethrow the original error.
            }
          }

          return handler.next(error);
        },
      ),
    );

    dio.interceptors.add(
      LogInterceptor(
        requestBody: true,
        responseBody: true,
      ),
    );

    return dio;
  }
}