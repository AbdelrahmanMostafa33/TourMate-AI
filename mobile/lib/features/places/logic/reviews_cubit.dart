import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/network/api_services.dart';
import '../data/models/review_model.dart';
import 'reviews_state.dart';

class ReviewsCubit extends Cubit<ReviewsState> {
  final ApiServices _api;

  ReviewsCubit(this._api) : super(const ReviewsState.initial());

  // ── Fetch ────────────────────────────────────────────────

  /// Fetch reviews for a place.
  Future<void> fetchReviews(String placeId) async {
    final prevSort = _getSort();
    final prevFilter = _getFilter();
    emit(const ReviewsState.loading());
    try {
      final json = await _api.getPlaceReviews(placeId);
      final data = PlaceReviewsResponse.fromJson(json);
      emit(ReviewsState.loaded(
        data: data,
        sortBy: prevSort,
        filterRating: prevFilter,
      ));
    } catch (e) {
      emit(ReviewsState.error(e.toString()));
    }
  }

  // ── Sort / Filter ────────────────────────────────────────

  /// Update the sort order.
  void setSortBy(ReviewSort sort) {
    state.maybeWhen(
      loaded: (data, submitting, _, filter) => emit(ReviewsState.loaded(
        data: data,
        isSubmitting: submitting,
        sortBy: sort,
        filterRating: filter,
      )),
      orElse: () {},
    );
  }

  /// Update the rating filter. null = show all.
  void setFilterRating(int? rating) {
    state.maybeWhen(
      loaded: (data, submitting, sort, _) => emit(ReviewsState.loaded(
        data: data,
        isSubmitting: submitting,
        sortBy: sort,
        filterRating: rating,
      )),
      orElse: () {},
    );
  }

  // ── Submit ───────────────────────────────────────────────

  /// Submit a new review.
  Future<bool> submitReview({
    required String placeId,
    required int rating,
    String? comment,
  }) async {
    _setSubmitting(true);

    try {
      await _api.createReview({
        'place_id': placeId,
        'rating': rating.clamp(1, 5),
        if (comment != null && comment.isNotEmpty) 'comment': comment,
      });
      await fetchReviews(placeId);
      return true;
    } catch (e) {
      _restoreAfterSubmit();
      return false;
    }
  }

  // ── Update ───────────────────────────────────────────────

  /// Update an existing review.
  Future<bool> updateReview({
    required String reviewId,
    required int rating,
    String? comment,
  }) async {
    _setSubmitting(true);

    try {
      await _api.updateReview(reviewId, {
        'rating': rating.clamp(1, 5),
        if (comment != null && comment.isNotEmpty) 'comment': comment,
      });
      // Re-fetch to refresh the list
      state.maybeWhen(
        loaded: (data, _, _, _) => fetchReviews(data.placeId),
        orElse: () {},
      );
      return true;
    } catch (e) {
      _restoreAfterSubmit();
      return false;
    }
  }

  // ── Delete ───────────────────────────────────────────────

  /// Delete a review by ID.
  Future<bool> deleteReview(String reviewId) async {
    try {
      await _api.deleteReview(reviewId);
      state.maybeWhen(
        loaded: (data, _, _, _) => fetchReviews(data.placeId),
        orElse: () {},
      );
      return true;
    } catch (e) {
      return false;
    }
  }

  // ── Helpers ──────────────────────────────────────────────

  void _setSubmitting(bool value) {
    state.maybeWhen(
      loaded: (data, _, sort, filter) => emit(ReviewsState.loaded(
        data: data,
        isSubmitting: value,
        sortBy: sort,
        filterRating: filter,
      )),
      orElse: () {},
    );
  }

  void _restoreAfterSubmit() {
    state.maybeWhen(
      loaded: (data, _, sort, filter) => emit(ReviewsState.loaded(
        data: data,
        sortBy: sort,
        filterRating: filter,
      )),
      orElse: () {},
    );
  }

  ReviewSort _getSort() => state.maybeWhen(
        loaded: (_, _, sort, _) => sort,
        orElse: () => ReviewSort.mostRecent,
      );

  int? _getFilter() => state.maybeWhen(
        loaded: (_, _, _, filter) => filter,
        orElse: () => null,
      );
}
