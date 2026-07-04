import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../../features/auth/data/models/user_response.dart';
import '../../features/auth/data/models/register_request.dart';
import '../../features/chat/data/models/chat_history_message.dart';
import '../../features/chat/data/models/chat_session_response.dart';
import '../../features/explore/data/models/explore_filters_response.dart';
import '../../features/explore/data/models/explore_places_response.dart';
import '../../features/explore/data/models/place_model.dart';
import '../../features/places/data/models/review_model.dart';
import '../../features/saved/data/models/saved_place_item.dart';
import '../../features/trips/data/models/trip_detail_model.dart';
import '../../features/trips/data/models/trip_profile_data.dart';
import '../../features/trips/data/models/trip_summary_model.dart';

// ─── Payment / Booking Models ────────────────────────────────────────────────
import '../../features/bookings/data/models/booking_models.dart';
import '../../features/flights/data/models/city_search_result.dart';
import '../../features/flights/data/models/flight_booking_response.dart';

part 'api_services.g.dart';

@RestApi()
abstract class ApiServices {

  factory ApiServices(Dio dio) = _ApiServices;

  /// LOGIN
  @POST("/api/v1/auth/login")
  Future<UserResponse> login();

  /// REGISTER
  @POST("/api/v1/auth/register")
  Future<UserResponse> register(
      @Body() RegisterRequest body,
      );

  /// GET PROFILE
  @GET("/api/v1/users/profile/full")
  Future<UserResponse> getProfile();

  /// UPDATE PROFILE
  @PUT("/api/v1/users/profile")
  Future<UserResponse> updateProfile(
      @Body() Map<String, dynamic> body,
      );

  /// GET ALL TRIPS
  @GET("/api/v1/trips/")
  Future<List<TripSummaryModel>> getTrips();

  /// CREATE TRIP
  @POST("/api/v1/trips/")
  Future<void> createTrip(
      @Body() Map<String, dynamic> body,
      );

  /// GET TRIP DETAIL (includes itineraries, days, stops)
  @GET("/api/v1/trips/{trip_id}")
  Future<TripDetailModel> getTripDetail(
      @Path('trip_id') String tripId,
      );

  /// GET TRIP PROFILE (budget, style, pace, interests)
  @GET("/api/v1/trips/{trip_id}/profile")
  Future<TripProfileData> getTripProfile(
      @Path('trip_id') String tripId,
      );

  /// EXPLORE PLACES
  @GET("/api/v1/places/explore")
  Future<ExplorePlacesResponse> explorePlaces(
      @Query('city') String? city,
      @Query('country') String? country,
      @Query('category') String? category,
      @Query('limit') int? limit,
      @Query('offset') int? offset,
      );

  /// GET PLACE DETAIL
  @GET("/api/v1/places/{place_id}")
  Future<PlaceModel> getPlaceDetail(
      @Path('place_id') String placeId,
      );

  /// GET EXPLORE FILTERS (cities + categories)
  @GET("/api/v1/places/explore/filters")
  Future<ExploreFiltersResponse> getExploreFilters(
      @Query('q') String? q,
      @Query('limit') int? limit,
      );

  /// SEMANTIC SEARCH PLACES (using embeddings)
  @POST("/api/v1/places/search/semantic")
  Future<ExplorePlacesResponse> semanticSearchPlaces(
      @Body() Map<String, dynamic> body,
      );

  /// SAVE A PLACE
  @POST("/api/v1/saved-places/")
  Future<void> savePlace(
      @Body() Map<String, dynamic> body,
      );

  /// UN-SAVE A PLACE BY SAVED PLACE ID
  @DELETE("/api/v1/saved-places/{saved_place_id}")
  Future<void> unsavePlace(
      @Path('saved_place_id') String savedPlaceId,
      );

  /// GET ALL SAVED PLACES (includes full place data)
  @GET("/api/v1/saved-places/")
  Future<List<SavedPlaceItem>> getSavedPlaces();

  /// GET REVIEWS FOR A PLACE
  @GET("/api/v1/reviews/place/{place_id}")
  Future<PlaceReviewsResponse> getPlaceReviews(
      @Path('place_id') String placeId,
      );

  /// CREATE A REVIEW
  @POST("/api/v1/reviews/")
  Future<void> createReview(
      @Body() Map<String, dynamic> body,
      );

  /// UPDATE A REVIEW
  @PUT("/api/v1/reviews/{review_id}")
  Future<void> updateReview(
      @Path('review_id') String reviewId,
      @Body() Map<String, dynamic> body,
      );

  /// DELETE A REVIEW
  @DELETE("/api/v1/reviews/{review_id}")
  Future<void> deleteReview(
      @Path('review_id') String reviewId,
      );

  /// LIKE / UNLIKE A REVIEW (toggle)
  @POST("/api/v1/reviews/{review_id}/like")
  Future<void> likeReview(
      @Path('review_id') String reviewId,
      );  /// DELETE A TRIP
  @DELETE("/api/v1/trips/{trip_id}")
  Future<void> deleteTrip(
    @Path('trip_id') String tripId,
  );

  /// UPDATE TRIP STATUS (bypasses LLM interpreter)
  @PATCH("/api/v1/trips/{trip_id}/status")
  Future<void> updateTripStatus(
    @Path('trip_id') String tripId,
    @Body() Map<String, dynamic> body,
  );

  /// LIST ALL CHAT SESSIONS (conversation history)
  @GET("/api/v1/chats/")
  Future<List<ChatSessionResponse>> getChatSessions();

  /// GET CHAT HISTORY for a specific trip
  @GET("/api/v1/chat/{trip_id}/history")
  Future<List<ChatHistoryMessage>> getChatHistory(
    @Path('trip_id') String tripId,
  );

  // ═════════════════════════════════════════════════════════════════════════
  // BOOKING & PAYMENT ENDPOINTS (existing backend)
  // ═════════════════════════════════════════════════════════════════════════

  /// List bookings for a trip
  @GET("/api/v1/bookings/trip/{trip_id}")
  Future<List<BookingResponse>> listTripBookings(
    @Path('trip_id') String tripId,
    @Query('status') String? status,
  );
  /// Initiate an async Stripe Payment Sheet payment for a booking.
  /// Creates PaymentIntent in requires_payment_method status, returns client_secret.
  /// The booking is NOT confirmed here — webhook does that.
  @POST("/api/v1/bookings/{booking_id}/initiate-payment")
  Future<JsonMap> initiateBookingPayment(
    @Path('booking_id') String bookingId,
    @Body() Map<String, dynamic> body,
  );

  /// Confirm a booking after the Payment Sheet succeeds (client-side verification).
  /// Backend verifies the PaymentIntent with Stripe directly, then confirms the booking.
  @POST("/api/v1/bookings/{booking_id}/confirm-after-payment")
  Future<JsonMap> confirmAfterPayment(
    @Path('booking_id') String bookingId,
    @Body() Map<String, dynamic> body,
  );

  // FLIGHT BOOKING ENDPOINTS (existing backend)
  // ═════════════════════════════════════════════════════════════════════════

  /// Search cities/airports for autocomplete
  @GET("/api/v1/flights/cities")
  Future<List<CitySearchResult>> searchFlightCities(
    @Query('q') String query,
    @Query('max') int? max,
  );

  /// Smart search — resolves city names + searches flights
  @POST("/api/v1/flights/smart-search")
  Future<SmartFlightSearchResponse> smartSearchFlights(
    @Body() Map<String, dynamic> body,
  );

  /// Initiate flight booking — price offer + Stripe PaymentIntent
  @POST("/api/v1/flights/book/initiate")
  Future<FlightBookInitiateResponse> initiateFlightBooking(
    @Body() Map<String, dynamic> body,
  );

  /// Confirm flight booking after Stripe payment succeeded
  @POST("/api/v1/flights/book/confirm")
  Future<FlightBookingConfirmResponse> confirmFlightBooking(
    @Body() Map<String, dynamic> body,
  );

  /// Get trip flight context for pre-filling search
  @GET("/api/v1/flights/trip/{trip_id}/context")
  Future<TripFlightContext> getTripFlightContext(
    @Path('trip_id') String tripId,
  );

  /// Get a single flight booking
  @GET("/api/v1/flights/{booking_id}")
  Future<FlightBookingConfirmResponse> getFlightBooking(
    @Path('booking_id') String bookingId,
  );

  /// List flight bookings for a trip
  @GET("/api/v1/flights/trip/{trip_id}")
  Future<List<FlightBookingConfirmResponse>> listTripFlightBookings(
    @Path('trip_id') String tripId,
  );

  /// Cancel a flight booking
  @POST("/api/v1/flights/{booking_id}/cancel")
  Future<FlightBookingConfirmResponse> cancelFlightBooking(
    @Path('booking_id') String bookingId,
  );

  /// Cancel an entire trip — cancels all bookings, refunds payments, and marks trip as cancelled.
  /// Returns: {success, trip_id, status, cancelled_bookings, refunded_payments}
  @POST("/api/v1/trips/{trip_id}/cancel")
  Future<JsonMap> cancelTrip(
    @Path('trip_id') String tripId,
  );
}