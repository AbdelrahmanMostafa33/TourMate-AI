import 'package:equatable/equatable.dart';

/// Response from GET /places/explore/filters.
class ExploreFiltersResponse extends Equatable {
  final List<LocationFilter> locations;

  const ExploreFiltersResponse({required this.locations});

  factory ExploreFiltersResponse.fromJson(Map<String, dynamic> json) {
    final locationsList = (json['locations'] as List<dynamic>?)
            ?.map((e) => LocationFilter.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    return ExploreFiltersResponse(locations: locationsList);
  }

  ExploreFiltersResponse copyWith({List<LocationFilter>? locations}) {
    return ExploreFiltersResponse(locations: locations ?? this.locations);
  }

  @override
  List<Object?> get props => [locations];
}

class LocationFilter extends Equatable {
  final String? city;
  final String? country;

  const LocationFilter({this.city, this.country});

  factory LocationFilter.fromJson(Map<String, dynamic> json) {
    return LocationFilter(
      city: json['city'] as String?,
      country: json['country'] as String?,
    );
  }

  LocationFilter copyWith({String? city, String? country}) {
    return LocationFilter(
      city: city ?? this.city,
      country: country ?? this.country,
    );
  }

  @override
  List<Object?> get props => [city, country];
}
