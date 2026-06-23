/// Countries and their major cities for home city dropdown selection.
///
/// Covers the most common home countries for TourMate users.
class CountriesCities {
  static const Map<String, List<String>> data = {
    'Egypt': [
      'Cairo',
      'Alexandria',
      'Giza',
      'Luxor',
      'Aswan',
      'Hurghada',
      'Sharm El Sheikh',
      'Marsa Matrouh',
      'Port Said',
      'Suez',
      'Ismailia',
      'Tanta',
      'Mansoura',
      'Zagazig',
      'Assiut',
    ],
    'United Arab Emirates': [
      'Dubai',
      'Abu Dhabi',
      'Sharjah',
      'Ajman',
      'Ras Al Khaimah',
      'Fujairah',
      'Al Ain',
    ],
    'Saudi Arabia': [
      'Riyadh',
      'Jeddah',
      'Mecca',
      'Medina',
      'Dammam',
      'Khobar',
      'Taif',
    ],
    'Kuwait': [
      'Kuwait City',
      'Hawalli',
      'Salmiya',
      'Farwaniya',
    ],
    'Qatar': [
      'Doha',
      'Al Wakrah',
      'Al Khor',
    ],
    'Bahrain': [
      'Manama',
      'Riffa',
      'Muharraq',
    ],
    'Oman': [
      'Muscat',
      'Salalah',
      'Sohar',
      'Nizwa',
    ],
    'Jordan': [
      'Amman',
      'Irbid',
      'Zarqa',
      'Aqaba',
      'Petra',
    ],
    'Lebanon': [
      'Beirut',
      'Tripoli',
      'Sidon',
      'Tyre',
    ],
    'Palestine': [
      'Ramallah',
      'Gaza',
      'Hebron',
      'Nablus',
      'Bethlehem',
      'Jericho',
    ],
    'Turkey': [
      'Istanbul',
      'Ankara',
      'Izmir',
      'Antalya',
      'Bodrum',
      'Cappadocia',
      'Marmaris',
    ],
    'Morocco': [
      'Casablanca',
      'Marrakech',
      'Rabat',
      'Fes',
      'Tangier',
      'Agadir',
      'Chefchaouen',
    ],
    'Tunisia': [
      'Tunis',
      'Sousse',
      'Sfax',
      'Hammamet',
      'Djerba',
    ],
    'Algeria': [
      'Algiers',
      'Oran',
      'Constantine',
      'Annaba',
    ],
    'Libya': [
      'Tripoli',
      'Benghazi',
      'Misrata',
    ],
    'Sudan': [
      'Khartoum',
      'Omdurman',
      'Port Sudan',
    ],
    'United Kingdom': [
      'London',
      'Manchester',
      'Birmingham',
      'Liverpool',
      'Edinburgh',
      'Glasgow',
      'Leeds',
      'Bristol',
    ],
    'United States': [
      'New York',
      'Los Angeles',
      'Chicago',
      'Houston',
      'Miami',
      'San Francisco',
      'Washington DC',
      'Boston',
      'Seattle',
      'Dallas',
      'Atlanta',
      'Denver',
    ],
    'Canada': [
      'Toronto',
      'Vancouver',
      'Montreal',
      'Calgary',
      'Ottawa',
      'Edmonton',
    ],
    'France': [
      'Paris',
      'Marseille',
      'Lyon',
      'Toulouse',
      'Nice',
    ],
    'Germany': [
      'Berlin',
      'Munich',
      'Hamburg',
      'Frankfurt',
      'Cologne',
      'Stuttgart',
    ],
    'Italy': [
      'Rome',
      'Milan',
      'Naples',
      'Florence',
      'Venice',
      'Bologna',
    ],
    'Spain': [
      'Madrid',
      'Barcelona',
      'Valencia',
      'Seville',
      'Malaga',
      'Palma',
    ],
    'Netherlands': [
      'Amsterdam',
      'Rotterdam',
      'The Hague',
      'Utrecht',
    ],
    'Switzerland': [
      'Zurich',
      'Geneva',
      'Bern',
      'Basel',
      'Lucerne',
    ],
    'Australia': [
      'Sydney',
      'Melbourne',
      'Brisbane',
      'Perth',
      'Adelaide',
      'Gold Coast',
    ],
    'India': [
      'Mumbai',
      'Delhi',
      'Bangalore',
      'Chennai',
      'Kolkata',
      'Hyderabad',
      'Goa',
    ],
    'China': [
      'Beijing',
      'Shanghai',
      'Guangzhou',
      'Shenzhen',
      'Hong Kong',
    ],
    'Japan': [
      'Tokyo',
      'Osaka',
      'Kyoto',
      'Yokohama',
      'Sapporo',
    ],
    'South Korea': [
      'Seoul',
      'Busan',
      'Incheon',
      'Daegu',
    ],
    'Malaysia': [
      'Kuala Lumpur',
      'Penang',
      'Johor Bahru',
      'Kota Kinabalu',
    ],
    'Singapore': [
      'Singapore',
    ],
    'Thailand': [
      'Bangkok',
      'Phuket',
      'Chiang Mai',
      'Pattaya',
      'Krabi',
    ],
    'Brazil': [
      'Rio de Janeiro',
      'São Paulo',
      'Brasília',
      'Salvador',
      'Fortaleza',
    ],
    'South Africa': [
      'Cape Town',
      'Johannesburg',
      'Durban',
      'Pretoria',
    ],
  };

  /// All country names sorted alphabetically.
  static List<String> get countries =>
      data.keys.toList()..sort((a, b) => a.compareTo(b));

  /// Cities for a given country, or an empty list if not found.
  static List<String> citiesFor(String country) =>
      data[country] ?? [];

  /// Try to extract country and city from a combined string like "Cairo, Egypt".
  /// Returns (country, city) if the city is found in a known country.
  static (String? country, String? city) parse(String? combined) {
    if (combined == null || combined.isEmpty) return (null, null);
    final parts = combined.split(',').map((p) => p.trim()).toList();
    if (parts.length == 2) {
      final city = parts[0];
      final country = parts[1];
      if (data.containsKey(country) && data[country]!.contains(city)) {
        return (country, city);
      }
    }
    return (null, null);
  }
}
