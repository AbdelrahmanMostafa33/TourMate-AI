import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../features/auth/data/models/full_profile_response.dart';
import '../../features/auth/data/models/register_request.dart';
import '../../features/auth/data/models/user_response.dart';
import '../../features/quiz/data/models/persona_response.dart';
import '../../features/trips/data/models/trip_summary_model.dart';

part 'api_services.g.dart';

@RestApi()
abstract class ApiServices {

  factory ApiServices(Dio dio) = _ApiServices;

  /// LOGIN
  @POST("/v1/auth/login")
  Future<UserResponse> login();

  /// REGISTER
  @POST("/v1/auth/register")
  Future<UserResponse> register(
      @Body() RegisterRequest body,
      );

  /// GET PROFILE
  @GET("/v1/users/profile/full")
  Future<FullProfileResponse> getProfile();

  /// QUIZ SKIP
  @POST("/v1/users/quiz/skip")
  Future<PersonaResponse> skipQuiz();

  /// QUIZ SUBMIT
  @POST("/v1/users/quiz")
  Future<PersonaResponse> submitQuiz(
      @Body() Map<String, dynamic> body,
      );

  /// GET ALL TRIPS
  @GET("/v1/trips/")
  Future<List<TripSummaryModel>> getTrips();

  /// CREATE TRIP
  @POST("/v1/trips/")
  Future<void> createTrip(
      @Body() Map<String, dynamic> body,
      );
}