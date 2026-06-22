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
      destination: json['destination'] as String? ?? 'Your Trip',
      durationDays: json['duration_days'] as int? ?? daysList.length,
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
      dayNumber: json['day_number'] as int? ?? 0,
      theme: json['theme'] as String? ?? '',
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
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? '',
      subCategory: json['sub_category'] as String? ?? '',
      cuisineType: json['cuisine_type'] as String? ?? '',
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lon: (json['lon'] as num?)?.toDouble() ?? 0.0,
      whyRecommended: json['why_recommended'] as String? ?? '',
      estimatedDurationMinutes: json['estimated_duration_minutes'] as int? ?? 0,
      suggestedTimeOfDay: json['suggested_time_of_day'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble(),
      address: json['address'] as String?,
      photoUrl: (json['photos'] as List<dynamic>?)?.isNotEmpty == true
          ? (json['photos']![0] as String)
          : null,
      travelTimeToNextMinutes: json['travel_time_to_next_minutes'] as int?,
      transportMode: json['transport_mode'] as String?,
      orderInDay: json['order_in_day'] as int?,
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
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      accommodationType: json['accommodation_type'] as String? ?? '',
      lat: (json['lat'] as num?)?.toDouble() ?? 0.0,
      lon: (json['lon'] as num?)?.toDouble() ?? 0.0,
      whyRecommended: json['why_recommended'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble(),
      photoUrl: (json['photos'] as List<dynamic>?)?.isNotEmpty == true
          ? (json['photos']![0] as String)
          : null,
      address: json['address'] as String?,
    );
  }
}
