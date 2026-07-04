import '../../../trips/data/models/trip_detail_model.dart';

Map<String, dynamic>? _asJsonMap(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return null;
}

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

double _parseDouble(dynamic value, [double defaultValue = 0.0]) {
  if (value == null) return defaultValue;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? defaultValue;
  return defaultValue;
}

double? _parseDoubleOrNull(dynamic value) {
  if (value == null) return null;
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

String _parseString(dynamic value, [String defaultValue = '']) {
  if (value == null) return defaultValue;
  return value.toString();
}

String? _parseStringOrNull(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

/// Safely extract a photo URL from various backend shapes:
///   - null / absent → null
///   - a List → first element (string or map with url/photo_url key)
///   - a String → the string itself
///   - a Map → url or photo_url key
String? _parsePhotoUrl(dynamic photos) {
  if (photos == null) return null;
  if (photos is String) return photos.isEmpty ? null : photos;
  if (photos is List) {
    if (photos.isEmpty) return null;
    final first = photos.first;
    if (first is String) return first.isEmpty ? null : first;
    if (first is Map) {
      return _parseStringOrNull(first['url'] ?? first['photo_url']);
    }
    return null;
  }
  if (photos is Map) {
    return _parseStringOrNull(photos['url'] ?? photos['photo_url']);
  }
  return null;
}

List<ItineraryStop> _parseStops(dynamic rawStops) {
  final stops = <ItineraryStop>[];
  if (rawStops is! List) return stops;
  for (final rawStop in rawStops) {
    final stopMap = _asJsonMap(rawStop);
    if (stopMap == null) continue;
    try {
      stops.add(ItineraryStop.fromJson(stopMap));
    } catch (_) {}
  }
  return stops;
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
    this.accommodationSuggestions = const [],
  });

  factory ItineraryData.fromJson(Map<String, dynamic> json) {
    final daysList = <ItineraryDay>[];
    for (final rawDay in json['days'] as List<dynamic>? ?? []) {
      final dayMap = _asJsonMap(rawDay);
      if (dayMap == null) continue;
      try {
        daysList.add(ItineraryDay.fromJson(dayMap));
      } catch (_) {
        // Skip malformed day entries instead of failing the whole card.
      }
    }

    final accommodations = <AccommodationSuggestion>[];
    for (final rawHotel
        in json['accommodation_suggestions'] as List<dynamic>? ?? []) {
      final hotelMap = _asJsonMap(rawHotel);
      if (hotelMap == null) continue;
      try {
        accommodations.add(AccommodationSuggestion.fromJson(hotelMap));
      } catch (_) {}
    }

    return ItineraryData(
      destination: _parseString(
        json['destination'] ?? json['destination_city'],
        'Your Trip',
      ),
      durationDays: _parseInt(json['duration_days'], daysList.length),
      days: daysList,
      accommodationSuggestions: accommodations,
    );
  }

  /// Build card data from persisted trip detail (for chat history reload).
  static ItineraryData? fromTripDetail(TripDetailModel trip) {
    if (trip.itineraries.isEmpty) return null;

    final itinerary = trip.itineraries.reduce(
      (current, candidate) =>
          candidate.versionNumber >= current.versionNumber ? candidate : current,
    );
    if (itinerary.days.isEmpty) return null;

    // Collect hotel stops across all days to reconstruct
    // accommodationSuggestions (hotels are stored as stops in the DB
    // but should render in the dedicated accommodation section, not
    // as regular day stops).
    final hotelAccommodations = <AccommodationSuggestion>[];

    final parsedDays = itinerary.days.map((day) {
      final hotelStops = day.stops.where((stop) {
        final cat = (stop.category ?? '').toLowerCase();
        return cat == 'hotel' || cat == 'accommodation';
      }).toList();

      for (final hs in hotelStops) {
        hotelAccommodations.add(AccommodationSuggestion(
          id: hs.placeId ?? hs.stopId,
          name: hs.name ?? 'Unknown',
          accommodationType: hs.subCategory ?? '',
          lat: hs.lat ?? 0,
          lon: hs.lon ?? 0,
          whyRecommended: hs.aiNotes ?? '',
          rating: hs.rating,
          photoUrl: hs.photoUrl,
          address: hs.address,
        ));
      }

      return ItineraryDay(
        dayNumber: day.dayNumber,
        theme: day.theme ?? '',
        stops: day.stops
            .where((stop) {
              final cat = (stop.category ?? '').toLowerCase();
              return cat != 'hotel' && cat != 'accommodation';
            })
            .map((stop) {
          return ItineraryStop(
            id: stop.placeId ?? stop.stopId,
            name: stop.name ?? 'Unknown',
            category: stop.category ?? '',
            subCategory: stop.subCategory ?? '',
            lat: stop.lat ?? 0,
            lon: stop.lon ?? 0,
            whyRecommended: stop.aiNotes ?? '',
            estimatedDurationMinutes: stop.durationMinutes ?? 0,
            suggestedTimeOfDay: stop.timeOfDay ?? '',
            rating: stop.rating,
            address: stop.address,
            photoUrl: stop.photoUrl,
            travelTimeToNextMinutes: stop.minutesFromPrevStop,
            transportMode: stop.travelMode,
            orderInDay: stop.orderInDay,
          );
        }).toList(),
      );
    }).toList();

    return ItineraryData(
      destination: trip.destination,
      durationDays: trip.durationDays,
      days: parsedDays,
      accommodationSuggestions: hotelAccommodations,
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
          _parseDoubleOrNull(json['total_travel_time_minutes']),
      stops: _parseStops(json['stops']),
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
      id: _parseString(json['id'] ?? json['place_id']),
      name: _parseString(json['name']),
      category: _parseString(json['category']),
      subCategory: _parseString(json['sub_category']),
      cuisineType: _parseString(json['cuisine_type']),
      lat: _parseDouble(json['lat']),
      lon: _parseDouble(json['lon']),
      whyRecommended: _parseString(json['why_recommended']),
      estimatedDurationMinutes:
          _parseInt(json['estimated_duration_minutes']),
      suggestedTimeOfDay: _parseString(json['suggested_time_of_day']),
      rating: _parseDoubleOrNull(json['rating']),
      address: _parseStringOrNull(json['address']),
      photoUrl: _parsePhotoUrl(json['photos'] ?? json['photo']),
      travelTimeToNextMinutes:
          _parseIntOrNull(json['travel_time_to_next_minutes']),
      transportMode: _parseStringOrNull(json['transport_mode']),
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
      lat: _parseDouble(json['lat']),
      lon: _parseDouble(json['lon']),
      whyRecommended: _parseString(json['why_recommended']),
      rating: _parseDoubleOrNull(json['rating']),
      photoUrl: _parsePhotoUrl(json['photos'] ?? json['photo']),
      address: _parseStringOrNull(json['address']),
    );
  }
}
