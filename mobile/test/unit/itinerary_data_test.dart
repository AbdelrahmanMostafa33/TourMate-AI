import 'package:flutter_test/flutter_test.dart';
import 'package:tourmate/features/chat/data/models/itinerary_data.dart';

void main() {
  group('ItineraryData.fromJson', () {
    test('parses float travel times from backend JSON', () {
      final data = ItineraryData.fromJson({
        'destination': 'Cairo',
        'duration_days': 3,
        'days': [
          {
            'day_number': 1,
            'theme': 'Ancient wonders',
            'total_travel_time_minutes': 16.0,
            'stops': [
              {
                'id': 'place-1',
                'name': 'Pyramids of Giza',
                'category': 'attraction',
                'sub_category': 'landmark',
                'lat': 29.9792,
                'lon': 31.1342,
                'estimated_duration_minutes': 120.0,
                'suggested_time_of_day': 'morning',
                'travel_time_to_next_minutes': 8.0,
                'transport_mode': 'walking',
                'photos': ['https://example.com/giza.jpg'],
              },
              {
                'id': 42,
                'name': 'Egyptian Museum',
                'category': 'attraction',
                'lat': 30.0478,
                'lon': 31.2336,
              },
            ],
          },
        ],
        'accommodation_suggestions': [
          {
            'id': 'hotel-1',
            'name': 'Nile View Hotel',
            'accommodation_type': 'resort',
            'lat': 30.0444,
            'lon': 31.2357,
            'rating': 4.5,
          },
        ],
      });

      expect(data.destination, 'Cairo');
      expect(data.days, hasLength(1));
      expect(data.days.first.totalTravelTimeMinutes, 16.0);

      final firstStop = data.days.first.stops.first;
      expect(firstStop.estimatedDurationMinutes, 120);
      expect(firstStop.travelTimeToNextMinutes, 8);
      expect(firstStop.photoUrl, 'https://example.com/giza.jpg');

      final secondStop = data.days.first.stops[1];
      expect(secondStop.id, '42');

      expect(data.accommodationSuggestions, hasLength(1));
      expect(data.accommodationSuggestions.first.rating, 4.5);
    });
  });
}
