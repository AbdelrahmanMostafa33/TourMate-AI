/// Represents a hotel option delivered separately from the itinerary.
///
/// In the future two-phase flow, the model will first return the itinerary
/// (days/stops), then after the user approves, separate hotel options will
/// arrive for the user to pick from and start booking.
class HotelOption {
  final String id;
  final String name;
  final String accommodationType;
  final String subCategory;
  final double lat;
  final double lon;
  final String description;
  final double? rating;
  final double? pricePerNight;
  final String? currency;
  final String? photoUrl;
  final String? address;
  final List<String> amenities;
  final double? distanceFromCenter;

  HotelOption({
    required this.id,
    required this.name,
    this.accommodationType = '',
    this.subCategory = '',
    required this.lat,
    required this.lon,
    this.description = '',
    this.rating,
    this.pricePerNight,
    this.currency,
    this.photoUrl,
    this.address,
    this.amenities = const [],
    this.distanceFromCenter,
  });

  factory HotelOption.fromJson(Map<String, dynamic> json) {
    return HotelOption(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      accommodationType: (json['accommodation_type'] ?? json['type'] ?? '').toString(),
      subCategory: (json['sub_category'] ?? '').toString(),
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lon: (json['lon'] as num?)?.toDouble() ?? 0.0,
      description: (json['description'] ?? json['why_recommended'] ?? '').toString(),
      rating: (json['rating'] as num?)?.toDouble(),
      pricePerNight: (json['price_per_night'] as num?)?.toDouble() ??
                     (json['nightly_rate'] as num?)?.toDouble(),
      currency: json['currency']?.toString(),
      photoUrl: _parsePhotoUrl(json['photos'] ?? json['photo']),
      address: json['address']?.toString(),
      amenities: _parseStringList(json['amenities']),
      distanceFromCenter: (json['distance_from_center'] as num?)?.toDouble(),
    );
  }

  static String? _parsePhotoUrl(dynamic photos) {
    if (photos is! List || photos.isEmpty) return null;
    final first = photos.first;
    if (first is String) return first;
    if (first is Map) {
      return (first['url'] ?? first['photo_url'] ?? '').toString();
    }
    return null;
  }

  static List<String> _parseStringList(dynamic value) {
    if (value is List) {
      return value.map((e) => e.toString()).toList();
    }
    return [];
  }
}

/// A group of hotel options sent after itinerary approval.
class HotelOptionsPayload {
  final String? tripId;
  final List<HotelOption> options;
  final String? message;
  final List<String> accommodationPreferences;

  HotelOptionsPayload({
    this.tripId,
    required this.options,
    this.message,
    this.accommodationPreferences = const [],
  });

  factory HotelOptionsPayload.fromJson(Map<String, dynamic> json) {
    final optionsList = <HotelOption>[];
    final rawOptions = json['options'] ?? json['hotels'] ?? json['data'] ?? [];
    if (rawOptions is List) {
      for (final raw in rawOptions) {
        if (raw is Map) {
          try {
            optionsList.add(HotelOption.fromJson(Map<String, dynamic>.from(raw)));
          } catch (_) {}
        }
      }
    }
    // Parse accommodation_preferences - could be a list or comma-separated string
    final rawPrefs = json['accommodation_preferences'];
    List<String> prefs = [];
    if (rawPrefs is List) {
      prefs = rawPrefs.map((e) => e.toString()).toList();
    } else if (rawPrefs is String && rawPrefs.isNotEmpty) {
      prefs = rawPrefs.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    }
    return HotelOptionsPayload(
      tripId: json['trip_id']?.toString(),
      options: optionsList,
      message: json['message']?.toString(),
      accommodationPreferences: prefs,
    );
  }

  /// A human-readable label for the accommodation preference, e.g. "Resort" or "5-star Hotel"
  String get preferenceLabel {
    if (accommodationPreferences.isEmpty) return '';
    // Format: capitalize first letter, join with " & "
    return accommodationPreferences
        .map((p) => p.isEmpty
            ? ''
            : '${p[0].toUpperCase()}${p.substring(1)}')
        .where((p) => p.isNotEmpty)
        .join(' & ');
  }
}
