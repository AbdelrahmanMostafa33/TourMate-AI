/// Structured photo analysis data extracted from a user-uploaded image.
///
/// Mirrors the backend ``VisionFeatures`` schema so the Flutter client
/// can render a rich AI analysis card instead of plain text.
class PhotoAnalysisData {
  final List<String> interests;
  final List<String> foodPreferences;
  final String? environmentType;
  final String? vibe;
  final String? travelStyle;
  final String? pace;
  final String? budgetLevel;
  final String confidence;

  const PhotoAnalysisData({
    required this.interests,
    this.foodPreferences = const [],
    this.environmentType,
    this.vibe,
    this.travelStyle,
    this.pace,
    this.budgetLevel,
    this.confidence = 'low',
  });

  factory PhotoAnalysisData.fromJson(Map<String, dynamic> json) {
    return PhotoAnalysisData(
      interests: (json['interests'] as List?)?.cast<String>() ?? [],
      foodPreferences: (json['food_preferences'] as List?)?.cast<String>() ?? [],
      environmentType: json['environment_type'] as String?,
      vibe: json['vibe'] as String?,
      travelStyle: json['travel_style'] as String?,
      pace: json['pace'] as String?,
      budgetLevel: json['budget_level'] as String?,
      confidence: json['confidence'] as String? ?? 'medium',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'interests': interests,
      'food_preferences': foodPreferences,
      'environment_type': environmentType,
      'vibe': vibe,
      'travel_style': travelStyle,
      'pace': pace,
      'budget_level': budgetLevel,
      'confidence': confidence,
    };
  }

  /// Whether this analysis has meaningful signal to display.
  bool get hasSignal => confidence != 'low' && interests.isNotEmpty;
}
