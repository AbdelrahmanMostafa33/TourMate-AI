import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';

class DioFactory {

  static Dio getDio() {

    final dio = Dio(
      BaseOptions(
        baseUrl: "http://10.0.2.2:8000/api",
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
        final token = await user.getIdToken();
        options.headers['Authorization'] = 'Bearer $token';
      }

      return handler.next(options);
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