import 'package:equatable/equatable.dart';

/// Matches the backend CitySearchResult schema from the Amadeus autocomplete API.
class CitySearchResult extends Equatable {
  final String iataCode;
  final String cityName;
  final String? airportName;
  final String countryName;
  final String subType; // "AIRPORT" or "CITY"

  const CitySearchResult({
    required this.iataCode,
    required this.cityName,
    this.airportName,
    required this.countryName,
    required this.subType,
  });

  factory CitySearchResult.fromJson(Map<String, dynamic> json) {
    return CitySearchResult(
      iataCode: json['iata_code'] as String? ?? '',
      cityName: json['city_name'] as String? ?? '',
      airportName: json['airport_name'] as String?,
      countryName: json['country_name'] as String? ?? '',
      subType: json['sub_type'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        iataCode, cityName, airportName, countryName, subType,
      ];
}
