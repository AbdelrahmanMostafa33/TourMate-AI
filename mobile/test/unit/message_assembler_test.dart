import 'package:flutter_test/flutter_test.dart';
import 'package:tourmate/features/chat/logic/chat_event.dart';
import 'package:tourmate/features/chat/logic/chat_segment.dart';
import 'package:tourmate/features/chat/logic/message_assembler.dart';

void main() {
  group('MessageAssembler', () {
    test('replace presentation swaps same-type card in the current response',
        () {
      final assembler = MessageAssembler();

      assembler.onEvent(const TextDeltaEvent(text: 'Updated itinerary below.'));
      assembler.onEvent(CardEvent(
        cardType: 'itinerary',
        data: _itinerary('old-stop'),
      ));
      assembler.onEvent(CardEvent(
        cardType: 'itinerary',
        data: _itinerary('new-stop'),
        presentation: 'replace',
      ));

      final cards = assembler.segments.whereType<CardSegment>().toList();
      expect(cards, hasLength(1));
      expect(cards.single.rawData['days'][0]['stops'][0]['id'], 'new-stop');
    });
  });
}

Map<String, dynamic> _itinerary(String stopId) => {
      'destination': 'Cairo',
      'duration_days': 1,
      'days': [
        {
          'day_number': 1,
          'stops': [
            {'id': stopId, 'name': stopId},
          ],
        },
      ],
    };
