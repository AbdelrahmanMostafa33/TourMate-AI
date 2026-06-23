class PlaceModel {
  final String placeId;
  final String name;
  final String category;
  final String? description;
  final double rating;
  final int reviewCount;
  final double? popularityScore;
  final List<String> photoUrls;
  final String? address;
  final String? city;
  final String? country;
  final double? lat;
  final double? lng;
  final double? entryFee;
  final double? nightlyRate;
  final int? starClass;
  final int? priceLevel;
  final String? cuisineType;
  final String? accommodationType;
  final String? phone;
  final String? website;
  final String? mapsLink;

  PlaceModel({
    required this.placeId,
    required this.name,
    required this.category,
    this.description,
    this.rating = 0,
    this.reviewCount = 0,
    this.popularityScore,
    this.photoUrls = const [],
    this.address,
    this.city,
    this.country,
    this.lat,
    this.lng,
    this.entryFee,
    this.nightlyRate,
    this.starClass,
    this.priceLevel,
    this.cuisineType,
    this.accommodationType,
    this.phone,
    this.website,
    this.mapsLink,
  });

  /// Whether this place has at least one photo URL to display.
  bool get hasPhoto => photoUrls.isNotEmpty && photoUrls.first.isNotEmpty;

  /// The first photo URL (empty string if none).
  String get firstPhoto => hasPhoto ? photoUrls.first : '';

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
    // Handle both:
    //   - Explore endpoint (legacy): id, lon, photos, sub_category
    //   - Detail endpoint (Pydantic): place_id, lng, photo_urls
    final id = json['place_id'] as String? ?? json['id'] as String? ?? '';
    final lon = json['lng'] as num? ?? json['lon'] as num?;
    final urls = (json['photo_urls'] as List<dynamic>?)
            ?.map((e) => e as String)
            .toList() ??
        (json['photos'] as List<dynamic>?)
            ?.map((e) => e as String)
            .toList() ??
        [];

    return PlaceModel(
      placeId: id,
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      description: json['description'] as String?,
      rating: (json['rating'] as num?)?.toDouble() ?? 0,
      reviewCount: (json['review_count'] as num?)?.toInt() ?? 0,
      popularityScore: (json['popularity_score'] as num?)?.toDouble(),
      photoUrls: urls,
      address: json['address'] as String?,
      city: json['city'] as String?,
      country: json['country'] as String?,
      lat: (json['lat'] as num?)?.toDouble(),
      lng: lon?.toDouble(),
      entryFee: (json['entry_fee'] as num?)?.toDouble(),
      nightlyRate: (json['nightly_rate'] as num?)?.toDouble(),
      starClass: (json['star_class'] as num?)?.toInt(),
      priceLevel: (json['price_level'] as num?)?.toInt(),
      cuisineType: json['cuisine_type'] as String?,
      accommodationType: json['accommodation_type'] as String?,
      phone: json['phone'] as String?,
      website: json['website'] as String?,
      mapsLink: json['maps_link'] as String?,
    );
  }
}
