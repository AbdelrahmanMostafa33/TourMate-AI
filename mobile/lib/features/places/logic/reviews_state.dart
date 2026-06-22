import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/review_model.dart';

part 'reviews_state.freezed.dart';

/// Sort order for reviews.
enum ReviewSort { mostRecent, highestRated, lowestRated }

@freezed
class ReviewsState with _$ReviewsState {
  const factory ReviewsState.initial() = _Initial;

  const factory ReviewsState.loading() = _Loading;

  const factory ReviewsState.loaded({
    required PlaceReviewsResponse data,
    @Default(false) bool isSubmitting,
    @Default(ReviewSort.mostRecent) ReviewSort sortBy,
    int? filterRating,
  }) = _Loaded;

  const factory ReviewsState.error(String message) = _Error;
}
