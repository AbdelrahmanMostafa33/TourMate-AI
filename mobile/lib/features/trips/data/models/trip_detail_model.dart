import 'package:latlong2/latlong.dart' show LatLng;

/// Full trip detail including itineraries, days, and stops.
class TripDetailModel {
  final String tripId;
  final String? tripName;
  final String destination;
  final String? startDate;
  final String? endDate;
  final int numberOfTravelers;
  final String? travelerGroupType;
  final double? budget;
  final String status;
  final String? createdAt;
  final String? updatedAt;
  final String? approvedAt;
  final String? autoMessage;
  final List<ItineraryDetail> itineraries;

  TripDetailModel({
    required this.tripId,
    this.tripName,
    required this.destination,
    this.startDate,
    this.endDate,
    required this.numberOfTravelers,
    this.travelerGroupType,
    this.budget,
    required this.status,
    this.createdAt,
    this.updatedAt,
    this.approvedAt,
    this.autoMessage,
    this.itineraries = const [],
  });

  /// Computed duration in days.
  int get durationDays {
    if (startDate == null || endDate == null) return 0;
    try {
      final start = DateTime.parse(startDate!);
      final end = DateTime.parse(endDate!);
      return end.difference(start).inDays + 1;
    } catch (_) {
      return 0;
    }
  }

  /// All stops across all days of all itineraries.
  List<StopDetail> get allStops {
    final stops = <StopDetail>[];
    for (final itin in itineraries) {
      for (final day in itin.days) {
        stops.addAll(day.stops);
      }
    }
    return stops;
  }

  /// All stops that have valid coordinates.
  List<StopDetail> get stopsWithCoords =>
      allStops.where((s) => s.hasCoords).toList();

  /// All unique LatLng points for the map.
  List<LatLng> get stopLatLngs =>
      stopsWithCoords.map((s) => LatLng(s.lat!, s.lon!)).toList();

  factory TripDetailModel.fromJson(Map<String, dynamic> json) {
    return TripDetailModel(
      tripId: json['trip_id'] as String? ?? '',
      tripName: json['trip_name'] as String?,
      destination: json['destination'] as String? ?? '',
      startDate: json['start_date'] as String?,
      endDate: json['end_date'] as String?,
      numberOfTravelers: (json['number_of_travelers'] as num?)?.toInt() ?? 1,
      travelerGroupType: json['traveler_group_type'] as String?,
      budget: (json['budget'] as num?)?.toDouble(),
      status: json['status'] as String? ?? 'planning',
      createdAt: json['created_at'] as String?,
      updatedAt: json['updated_at'] as String?,
      approvedAt: json['approved_at'] as String?,
      autoMessage: json['auto_message'] as String?,
      itineraries: (json['itineraries'] as List<dynamic>?)
              ?.map((e) =>
                  ItineraryDetail.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

/// An itinerary version within a trip.
class ItineraryDetail {
  final String itineraryId;
  final int versionNumber;
  final String? description;
  final String status;
  final String? createdAt;
  final String? updatedAt;
  final List<DayDetail> days;

  ItineraryDetail({
    required this.itineraryId,
    required this.versionNumber,
    this.description,
    required this.status,
    this.createdAt,
    this.updatedAt,
    this.days = const [],
  });

  factory ItineraryDetail.fromJson(Map<String, dynamic> json) {
    return ItineraryDetail(
      itineraryId: json['itinerary_id'] as String? ?? '',
      versionNumber: (json['version_number'] as num?)?.toInt() ?? 0,
      description: json['description'] as String?,
      status: json['status'] as String? ?? 'draft',
      createdAt: json['created_at'] as String?,
      updatedAt: json['updated_at'] as String?,
      days: (json['days'] as List<dynamic>?)
              ?.map((e) => DayDetail.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

/// A single day within an itinerary.
class DayDetail {
  final String dayId;
  final int dayNumber;
  final String? date;
  final String? theme;
  final String? description;
  final List<StopDetail> stops;

  DayDetail({
    required this.dayId,
    required this.dayNumber,
    this.date,
    this.theme,
    this.description,
    this.stops = const [],
  });

  factory DayDetail.fromJson(Map<String, dynamic> json) {
    return DayDetail(
      dayId: json['day_id'] as String? ?? '',
      dayNumber: (json['day_number'] as num?)?.toInt() ?? 0,
      date: json['date'] as String?,
      theme: json['theme'] as String?,
      description: json['description'] as String?,
      stops: (json['stops'] as List<dynamic>?)
              ?.map((e) => StopDetail.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

/// A stop (place visit) within a day.
class StopDetail {
  final String stopId;
  final String? placeId;
  final String? name;
  final String? category;
  final String? subCategory;
  final double? lat;
  final double? lon;
  final double? rating;
  final String? address;
  final String? photoUrl;
  final String? description;
  final String? phone;
  final String? website;
  final String? mapsLink;
  final int? durationMinutes;
  final int? orderInDay;
  final String? timeOfDay;
  final int? minutesFromPrevStop;
  final String? travelMode;
  final double? estimatedCost;
  final String? aiNotes;
  final String? userNotes;
  final String status;

  StopDetail({
    required this.stopId,
    this.placeId,
    this.name,
    this.category,
    this.subCategory,
    this.lat,
    this.lon,
    this.rating,
    this.address,
    this.photoUrl,
    this.description,
    this.phone,
    this.website,
    this.mapsLink,
    this.durationMinutes,
    this.orderInDay,
    this.timeOfDay,
    this.minutesFromPrevStop,
    this.travelMode,
    this.estimatedCost,
    this.aiNotes,
    this.userNotes,
    this.status = 'planned',
  });

  bool get hasCoords => lat != null && lon != null;

  /// Build from a place_snapshot dict nested inside the stop JSON.
  factory StopDetail.fromJson(Map<String, dynamic> json) {
    final snapshot = json['place_snapshot'] as Map<String, dynamic>?;

    return StopDetail(
      stopId: json['stop_id'] as String? ?? '',
      placeId: json['place_id'] as String?,
      name: snapshot?['name'] as String? ?? json['name'] as String?,
      category: snapshot?['category'] as String?,
      subCategory: snapshot?['sub_category'] as String?,
      lat: (snapshot?['lat'] as num?)?.toDouble(),
      lon: (snapshot?['lon'] as num?)?.toDouble(),
      rating: (snapshot?['rating'] as num?)?.toDouble(),
      address: snapshot?['address'] as String?,
      photoUrl: snapshot?['photo'] as String?,
      description: snapshot?['description'] as String?,
      phone: snapshot?['phone'] as String?,
      website: snapshot?['website'] as String?,
      mapsLink: snapshot?['maps_link'] as String?,
      durationMinutes: (json['duration_minutes'] as num?)?.toInt(),
      orderInDay: (json['order_in_day'] as num?)?.toInt(),
      timeOfDay: _serializeTimeOfDay(json['time_of_day']),
      minutesFromPrevStop:
          (json['minutes_from_prev_stop'] as num?)?.toInt(),
      travelMode: _serializeTravelMode(json['travel_mode']),
      estimatedCost: (json['estimated_cost'] as num?)?.toDouble(),
      aiNotes: json['ai_notes'] as String?,
      userNotes: json['user_notes'] as String?,
      status: json['status'] as String? ?? 'planned',
    );
  }

  static String? _serializeTimeOfDay(dynamic tod) {
    if (tod == null) return null;
    // Enum serialization: could be a string or an object with "value"
    if (tod is String) return tod;
    if (tod is Map) return tod['value'] as String? ?? tod.toString();
    return tod.toString();
  }

  static String? _serializeTravelMode(dynamic mode) {
    if (mode == null) return null;
    if (mode is String) return mode;
    if (mode is Map) return mode['value'] as String? ?? mode.toString();
    return mode.toString();
  }
}
