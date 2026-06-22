import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../features/auth/data/models/full_profile_response.dart';
import '../../features/auth/data/models/register_request.dart';
import '../../features/auth/data/models/user_response.dart';
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

  /// UPDATE PROFILE
  @PUT("/v1/users/profile")
  Future<FullProfileResponse> updateProfile(
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

  /// GET TRIP DETAIL (includes itineraries, days, stops)
  @GET("/v1/trips/{trip_id}")
  Future<Map<String, dynamic>> getTripDetail(
      @Path('trip_id') String tripId,
      );

  /// EXPLORE PLACES
  @GET("/v1/places/explore")
  Future<dynamic> explorePlaces(
      @Query('city') String? city,
      @Query('country') String? country,
      @Query('category') String? category,
      @Query('limit') int? limit,
      @Query('offset') int? offset,
      );

  /// GET PLACE DETAIL
  @GET("/v1/places/{place_id}")
  Future<Map<String, dynamic>> getPlaceDetail(
      @Path('place_id') String placeId,
      );

  /// GET EXPLORE FILTERS (cities + categories)
  @GET("/v1/places/explore/filters")
  Future<Map<String, dynamic>> getExploreFilters(
      @Query('q') String? q,
      @Query('limit') int? limit,
      );

  /// SAVE A PLACE
  @POST("/v1/saved-places/")
  Future<Map<String, dynamic>> savePlace(
      @Body() Map<String, dynamic> body,
      );

  /// UN-SAVE A PLACE BY SAVED PLACE ID
  @DELETE("/v1/saved-places/{saved_place_id}")
  Future<Map<String, dynamic>> unsavePlace(
      @Path('saved_place_id') String savedPlaceId,
      );

  /// GET ALL SAVED PLACES (includes full place data)
  @GET("/v1/saved-places/")
  Future<dynamic> getSavedPlaces();

  /// GET REVIEWS FOR A PLACE
  @GET("/v1/reviews/place/{place_id}")
  Future<Map<String, dynamic>> getPlaceReviews(
      @Path('place_id') String placeId,
      );

  /// CREATE A REVIEW
  @POST("/v1/reviews/")
  Future<Map<String, dynamic>> createReview(
      @Body() Map<String, dynamic> body,
      );

  /// UPDATE A REVIEW
  @PUT("/v1/reviews/{review_id}")
  Future<Map<String, dynamic>> updateReview(
      @Path('review_id') String reviewId,
      @Body() Map<String, dynamic> body,
      );

  /// DELETE A REVIEW
  @DELETE("/v1/reviews/{review_id}")
  Future<Map<String, dynamic>> deleteReview(
      @Path('review_id') String reviewId,
      );
}