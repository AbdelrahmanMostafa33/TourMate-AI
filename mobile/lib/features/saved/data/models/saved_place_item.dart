import 'package:equatable/equatable.dart';

import '../../../../features/explore/data/models/place_model.dart';

/// A saved-place entry: a user's saved place with its saved_place_id
/// and the full [PlaceModel] data nested inside.
class SavedPlaceItem extends Equatable {
  final String savedPlaceId;
  final String userId;
  final String placeId;
  final PlaceModel place;

  const SavedPlaceItem({
    required this.savedPlaceId,
    required this.userId,
    required this.placeId,
    required this.place,
  });

  factory SavedPlaceItem.fromJson(Map<String, dynamic> json) {
    final placeData = json['place'] as Map<String, dynamic>? ?? {};
    return SavedPlaceItem(
      savedPlaceId: json['saved_place_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      placeId: json['place_id'] as String? ?? '',
      place: PlaceModel.fromJson(placeData),
    );
  }

  SavedPlaceItem copyWith({
    String? savedPlaceId,
    String? userId,
    String? placeId,
    PlaceModel? place,
  }) {
    return SavedPlaceItem(
      savedPlaceId: savedPlaceId ?? this.savedPlaceId,
      userId: userId ?? this.userId,
      placeId: placeId ?? this.placeId,
      place: place ?? this.place,
    );
  }

  @override
  List<Object?> get props => [savedPlaceId, userId, placeId, place];
}
