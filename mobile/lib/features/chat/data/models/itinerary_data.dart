int _parseInt(dynamic value, [int defaultValue = 0]) {
  if (value == null) return defaultValue;
  if (value is int) return value;
  if (value is num) return value.round();
  if (value is String) return int.tryParse(value) ?? defaultValue;
  return defaultValue;
}

int? _parseIntOrNull(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is num) return value.round();
  if (value is String) return int.tryParse(value);
  return null;
}

String _parseString(dynamic value, [String defaultValue = '']) {
  if (value == null) return defaultValue;
  return value.toString();
}

String? _parsePhotoUrl(dynamic photos) {
  if (photos is! List || photos.isEmpty) return null;
  final first = photos.first;
  if (first is String) return first;
  if (first is Map) {
    return first['url'] as String? ?? first['photo_url'] as String?;
  }
  return null;
}

class ItineraryData {
  final String destination;
  final int durationDays;
  final List<ItineraryDay> days;
  final List<AccommodationSuggestion> accommodationSuggestions;

  ItineraryData({
    required this.destination,
    required this.durationDays,
    required this.days,
    required this.accommodationSuggestions,
  });

  factory ItineraryData.fromJson(Map<String, dynamic> json) {
    final daysList = (json['days'] as List<dynamic>?)
            ?.map((d) => ItineraryDay.fromJson(d as Map<String, dynamic>))
            .toList() ??
        [];

    return ItineraryData(
      destination: _parseString(json['destination'], 'Your Trip'),
      durationDays: _parseInt(json['duration_days'], daysList.length),
      days: daysList,
      accommodationSuggestions:
          (json['accommodation_suggestions'] as List<dynamic>?)
                  ?.map(
                    (a) =>
                        AccommodationSuggestion.fromJson(a as Map<String, dynamic>),
                  )
                  .toList() ??
              [],
    );
  }
}

class ItineraryDay {
  final int dayNumber;
  final String theme;
  final double? totalTravelTimeMinutes;
  final List<ItineraryStop> stops;

  ItineraryDay({
    required this.dayNumber,
    required this.theme,
    this.totalTravelTimeMinutes,
    required this.stops,
  });

  factory ItineraryDay.fromJson(Map<String, dynamic> json) {
    return ItineraryDay(
      dayNumber: _parseInt(json['day_number']),
      theme: _parseString(json['theme']),
      totalTravelTimeMinutes:
          (json['total_travel_time_minutes'] as num?)?.toDouble(),
      stops: (json['stops'] as List<dynamic>?)
              ?.map(
                (s) => ItineraryStop.fromJson(s as Map<String, dynamic>),
              )
              .toList() ??
          [],
    );
  }
}

class ItineraryStop {
  final String id;
  final String name;
  final String category;
  final String subCategory;
  final String cuisineType;
  final double lat;
  final double lon;
  final String whyRecommended;
  final int estimatedDurationMinutes;
  final String suggestedTimeOfDay;
  final double? rating;
  final String? address;
  final String? photoUrl;
  final int? travelTimeToNextMinutes;
  final String? transportMode;
  final int? orderInDay;

  ItineraryStop({
    required this.id,
    required this.name,
    required this.category,
    required this.subCategory,
    this.cuisineType = '',
    required this.lat,
    required this.lon,
    this.whyRecommended = '',
    this.estimatedDurationMinutes = 0,
    this.suggestedTimeOfDay = '',
    this.rating,
    this.address,
    this.photoUrl,
    this.travelTimeToNextMinutes,
    this.transportMode,
    this.orderInDay,
  });

  factory ItineraryStop.fromJson(Map<String, dynamic> json) {
    return ItineraryStop(
      id: _parseString(json['id']),
      name: _parseString(json['name']),
      category: _parseString(json['category']),
      subCategory: _parseString(json['sub_category']),
      cuisineType: _parseString(json['cuisine_type']),
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lon: (json['lon'] as num?)?.toDouble() ?? 0.0,
      whyRecommended: _parseString(json['why_recommended']),
      estimatedDurationMinutes:
          _parseInt(json['estimated_duration_minutes']),
      suggestedTimeOfDay: _parseString(json['suggested_time_of_day']),
      rating: (json['rating'] as num?)?.toDouble(),
      address: json['address'] as String?,
      photoUrl: _parsePhotoUrl(json['photos']),
      travelTimeToNextMinutes:
          _parseIntOrNull(json['travel_time_to_next_minutes']),
      transportMode: json['transport_mode'] as String?,
      orderInDay: _parseIntOrNull(json['order_in_day']),
    );
  }
}

class AccommodationSuggestion {
  final String id;
  final String name;
  final String accommodationType;
  final double lat;
  final double lon;
  final String whyRecommended;
  final double? rating;
  final String? photoUrl;
  final String? address;

  AccommodationSuggestion({
    required this.id,
    required this.name,
    this.accommodationType = '',
    required this.lat,
    required this.lon,
    this.whyRecommended = '',
    this.rating,
    this.photoUrl,
    this.address,
  });

  factory AccommodationSuggestion.fromJson(Map<String, dynamic> json) {
    return AccommodationSuggestion(
      id: _parseString(json['id']),
      name: _parseString(json['name']),
      accommodationType: _parseString(json['accommodation_type']),
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lon: (json['lon'] as num?)?.toDouble() ?? 0.0,
      whyRecommended: _parseString(json['why_recommended']),
      rating: (json['rating'] as num?)?.toDouble(),
      photoUrl: _parsePhotoUrl(json['photos']),
      address: json['address'] as String?,
    );
  }
}
