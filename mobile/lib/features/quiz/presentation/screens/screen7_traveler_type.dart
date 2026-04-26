import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';

class Screen7TravelerType extends StatefulWidget {
  final QuizAnswers answers;
  final Future<void> Function() onNext;
  final VoidCallback onBack;
  const Screen7TravelerType({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
  });

  @override
  State<Screen7TravelerType> createState() => _Screen7TravelerTypeState();
}

class _Screen7TravelerTypeState extends State<Screen7TravelerType> {
  late List<String> _selectedTypes;

  final _types = const [
    {
      'label': 'The Adventurous Seeker',
      'desc': 'Thrives on exciting adventures and cultural discoveries.',
    },
    {
      'label': 'The Budget Backpacker',
      'desc': 'Maximizes experiences while minimizing cost.',
    },
    {
      'label': 'The Serial Romantic',
      'desc': 'Romantic getaways and couple-focused experiences.',
    },
    {
      'label': 'The Urban Explorer',
      'desc': 'City life, culture, and nightlife.',
    },
    {
      'label': 'The Mindful Wanderer',
      'desc': 'Wellness, nature, and slow travel.',
    },
    {
      'label': 'The Coastal Traveler',
      'desc': 'Beaches, oceans, and water activities.',
    },
    {
      'label': 'The Road Tripper',
      'desc': 'Freedom of open roads and spontaneous stops.',
    },
    {
      'label': 'The Gastronomic Traveler',
      'desc': 'Food tours, local markets, and cooking classes.',
    },
  ];

  @override
  void initState() {
    super.initState();
    _selectedTypes = List.from(widget.answers.travelerTypes);
  }

  void _toggleSelection(String label) {
    setState(() {
      if (_selectedTypes.contains(label)) {
        _selectedTypes.remove(label);
      } else {
        if (_selectedTypes.length < 3) {
          _selectedTypes.add(label);
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen7.png',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'What describes you as a traveler?',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.fromLTRB(24, 6, 24, 0),
            child: Text(
              'Select up to 3 traveler types that resonate with you the most.',
              style: TextStyle(fontSize: 13, color: Colors.black),
            ),
          ),

          const SizedBox(height: 16),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: _types.map((t) {
                final lbl = t['label']!;
                final sel = _selectedTypes.contains(lbl);

                return ChoiceChip2(
                  label: lbl,
                  selected: sel,
                  onTap: () => _toggleSelection(lbl),
                );
              }).toList(),
            ),
          ),

          const SizedBox(height: 10),

          if (_selectedTypes.length >= 3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24),
              child: Text(
                'You can select up to 3 types only.',
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ),

          NavButtons(
            onBack: widget.onBack,
            onNext: () {
              widget.answers.travelerTypes = _selectedTypes;
              widget.onNext();
            },
          ),
        ],
      ),
    );
  }
}