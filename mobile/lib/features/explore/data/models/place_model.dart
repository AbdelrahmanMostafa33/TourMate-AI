class PlaceModel {
  final String id;
  final String name;
  final String category;
  final String subCategory;
  final String? description;
  final double rating;
  final int reviewCount;
  final double popularityScore;
  final List<String> photos;
  final String? address;
  final String? city;
  final String? country;
  final double? lat;
  final double? lon;
  final double? entryFee;
  final double? nightlyRate;
  final int? starClass;
  final int? priceLevel;
  final String? cuisineType;
  final String? accommodationType;

  PlaceModel({
    required this.id,
    required this.name,
    required this.category,
    this.subCategory = '',
    this.description,
    this.rating = 0,
    this.reviewCount = 0,
    this.popularityScore = 0,
    this.photos = const [],
    this.address,
    this.city,
    this.country,
    this.lat,
    this.lon,
    this.entryFee,
    this.nightlyRate,
    this.starClass,
    this.priceLevel,
    this.cuisineType,
    this.accommodationType,
  });

  /// Whether this place has at least one photo URL to display.
  bool get hasPhoto => photos.isNotEmpty && photos.first.isNotEmpty;

  /// The first photo URL (empty string if none).
  String get firstPhoto => hasPhoto ? photos.first : '';

  /// Category icon for the place type.
  String get categoryEmoji {
    switch (category.toLowerCase()) {
      case 'hotel':
        return '🏨';
      case 'restaurant':
        return '🍽️';
      case 'attraction':
        return '🏛️';
      default:
        return '📍';
    }
  }

  factory PlaceModel.fromJson(Map<String, dynamic> json) {
    return PlaceModel(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      subCategory: json['sub_category'] as String? ?? '',
      description: json['description'] as String?,
      rating: (json['rating'] as num?)?.toDouble() ?? 0,
      reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
      popularityScore: (json['popularity_score'] as num?)?.toDouble() ?? 0,
      photos: (json['photos'] as List<dynamic>?)
              ?.map((e) => e as String)
              .toList() ??
          [],
      address: json['address'] as String?,
      city: json['city'] as String?,
      country: json['country'] as String?,
      lat: (json['lat'] as num?)?.toDouble(),
      lon: (json['lon'] as num?)?.toDouble(),
      entryFee: (json['entry_fee'] as num?)?.toDouble(),
      nightlyRate: (json['nightly_rate'] as num?)?.toDouble(),
      starClass: (json['star_class'] as num?)?.toInt(),
      priceLevel: (json['price_level'] as num?)?.toInt(),
      cuisineType: json['cuisine_type'] as String?,
      accommodationType: json['accommodation_type'] as String?,
    );
  }
}
