import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../features/auth/data/models/register_request.dart';
import '../../features/auth/data/models/user_response.dart';

part 'api_services.g.dart';

@RestApi()
abstract class ApiServices {

  factory ApiServices(Dio dio) = _ApiServices;

  /// LOGIN
  @POST("/v1/auth/login")
  Future<UserResponse> login(
    @Header("Authorization") String token,
  );

  /// REGISTER
  @POST("/v1/auth/register")
  Future<UserResponse> register(
    @Header("Authorization") String token,
    @Body() RegisterRequest body,
  );
}