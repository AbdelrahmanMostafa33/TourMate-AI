class QuizSubmitRequest {
  final int age;
  final String sex;
  final String travelCompanion;
  final String location;

  // Sliders (0-100)
  final int adventureRelaxing;
  final int natureCulture;
  final int popularLocal;
  final int budgetLevel;
  final int earlyNight;
  final int independentSocial;

  // Multi-select
  final List<String> accommodationStyles;
  final List<String> diningPreferences;
  final List<String> interests;
  final List<String> travelerTypes;

  const QuizSubmitRequest({
    required this.age,
    required this.sex,
    required this.travelCompanion,
    required this.location,
    required this.adventureRelaxing,
    required this.natureCulture,
    required this.popularLocal,
    required this.budgetLevel,
    required this.earlyNight,
    required this.independentSocial,
    required this.accommodationStyles,
    required this.diningPreferences,
    required this.interests,
    required this.travelerTypes,
  });

  Map<String, dynamic> toJson() => {
    'age': age,
    'sex': sex,
    'travel_companion': travelCompanion,
    'location': location,
    'adventure_relaxing': adventureRelaxing,
    'nature_culture': natureCulture,
    'popular_local': popularLocal,
    'budget_level': budgetLevel,
    'early_night': earlyNight,
    'independent_social': independentSocial,
    'accommodation_styles': accommodationStyles,
    'dining_preferences': diningPreferences,
    'interests': interests,
    'traveler_types': travelerTypes,
  };
}