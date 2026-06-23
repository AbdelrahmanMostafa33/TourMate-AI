import 'package:equatable/equatable.dart';

import 'place_model.dart';

/// Response from GET /places/explore and POST /places/search/semantic.
class ExplorePlacesResponse extends Equatable {
  final List<PlaceModel> places;
  final int total;

  const ExplorePlacesResponse({
    required this.places,
    required this.total,
  });

  factory ExplorePlacesResponse.fromJson(Map<String, dynamic> json) {
    final placesList = (json['places'] as List<dynamic>?)
            ?.map((e) => PlaceModel.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    final total = (json['total'] as num?)?.toInt() ?? placesList.length;

    return ExplorePlacesResponse(places: placesList, total: total);
  }

  ExplorePlacesResponse copyWith({List<PlaceModel>? places, int? total}) {
    return ExplorePlacesResponse(
      places: places ?? this.places,
      total: total ?? this.total,
    );
  }

  @override
  List<Object?> get props => [places, total];
}
