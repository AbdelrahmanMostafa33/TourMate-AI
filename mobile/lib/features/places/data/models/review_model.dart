import 'package:equatable/equatable.dart';

/// A single review for a place.
class ReviewModel extends Equatable {
  final String reviewId;
  final String userId;
  final String placeId;
  final int rating;
  final String? comment;
  final String? reviewDate;
  final int likesCount;
  final String? userName;

  const ReviewModel({
    required this.reviewId,
    required this.userId,
    required this.placeId,
    required this.rating,
    this.comment,
    this.reviewDate,
    this.likesCount = 0,
    this.userName,
  });

  /// Display name — uses `userName` (mapped from backend's `user_name` =
  /// user's full_name) when available, otherwise falls back to a short ID.
  String get displayName {
    if (userName != null && userName!.trim().isNotEmpty) return userName!;
    return 'User ${userId.length > 6 ? userId.substring(0, 6) : userId}';
  }

  String get initials {
    if (userName != null && userName!.isNotEmpty) {
      final parts = userName!.split(' ');
      if (parts.length >= 2) {
        return '${parts[0][0]}${parts[1][0]}'.toUpperCase();
      }
      return userName![0].toUpperCase();
    }
    return userId.isNotEmpty ? userId[0].toUpperCase() : '?';
  }

  factory ReviewModel.fromJson(Map<String, dynamic> json) {
    return ReviewModel(
      reviewId: json['review_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      placeId: json['place_id'] as String? ?? '',
      rating: (json['rating'] as num?)?.toInt() ?? 5,
      comment: json['comment'] as String?,
      reviewDate: json['review_date'] as String?,
      likesCount: (json['likes_count'] as num?)?.toInt() ?? 0,
      userName: json['user_name'] as String?,
    );
  }

  ReviewModel copyWith({
    String? reviewId,
    String? userId,
    String? placeId,
    int? rating,
    String? comment,
    String? reviewDate,
    int? likesCount,
    String? userName,
  }) {
    return ReviewModel(
      reviewId: reviewId ?? this.reviewId,
      userId: userId ?? this.userId,
      placeId: placeId ?? this.placeId,
      rating: rating ?? this.rating,
      comment: comment ?? this.comment,
      reviewDate: reviewDate ?? this.reviewDate,
      likesCount: likesCount ?? this.likesCount,
      userName: userName ?? this.userName,
    );
  }

  @override
  List<Object?> get props => [
        reviewId, userId, placeId, rating, comment,
        reviewDate, likesCount, userName,
      ];
}

/// Summary of reviews for a place returned by GET /reviews/place/{id}.
class PlaceReviewsResponse extends Equatable {
  final String placeId;
  final int totalReviews;
  final double? averageRating;
  final List<ReviewModel> reviews;

  const PlaceReviewsResponse({
    required this.placeId,
    required this.totalReviews,
    this.averageRating,
    required this.reviews,
  });

  factory PlaceReviewsResponse.fromJson(Map<String, dynamic> json) {
    return PlaceReviewsResponse(
      placeId: json['place_id'] as String? ?? '',
      totalReviews: (json['total_reviews'] as num?)?.toInt() ?? 0,
      averageRating: (json['average_rating'] as num?)?.toDouble(),
      reviews: (json['reviews'] as List<dynamic>?)
              ?.map((e) => ReviewModel.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  PlaceReviewsResponse copyWith({
    String? placeId,
    int? totalReviews,
    double? averageRating,
    List<ReviewModel>? reviews,
  }) {
    return PlaceReviewsResponse(
      placeId: placeId ?? this.placeId,
      totalReviews: totalReviews ?? this.totalReviews,
      averageRating: averageRating ?? this.averageRating,
      reviews: reviews ?? this.reviews,
    );
  }

  @override
  List<Object?> get props => [placeId, totalReviews, averageRating, reviews];
}
