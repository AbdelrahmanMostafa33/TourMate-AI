/// A single review for a place.
class ReviewModel {
  final String reviewId;
  final String userId;
  final String placeId;
  final int rating;
  final String? comment;
  final String? reviewDate;
  final int likesCount;
  final String? userName;

  ReviewModel({
    required this.reviewId,
    required this.userId,
    required this.placeId,
    required this.rating,
    this.comment,
    this.reviewDate,
    this.likesCount = 0,
    this.userName,
  });

  String get displayName =>
      userName ?? 'User ${userId.length > 6 ? userId.substring(0, 6) : userId}';

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
}

/// Summary of reviews for a place returned by GET /reviews/place/{id}.
class PlaceReviewsResponse {
  final String placeId;
  final int totalReviews;
  final double? averageRating;
  final List<ReviewModel> reviews;

  PlaceReviewsResponse({
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
}
