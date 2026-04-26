import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';

class Screen5Dining extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack;

  const Screen5Dining({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
  });

  @override
  State<Screen5Dining> createState() => _Screen5DiningState();
}

class _Screen5DiningState extends State<Screen5Dining> {
  late List<String> _selected;
  final List<String> _customOptions = [];

  final List<String> _options = [
    'Fine Dining & Gourmet',
    'Casual Dining',
    'Local Street Food',
    'Cafes & Bistros',
    'Family Restaurants',
    'Vegetarian / Vegan',
    'Ethnic Cuisine',
    'Food Trucks',
    'Buffet Dining',
    'Fast Food',
    'Seafood Restaurants',
    'BBQ & Grills',
    'Bakeries & Desserts',
    'Coffee Shops',
    'Farm-to-Table',
    'Pub / Tavern Dining',
  ];

  @override
  void initState() {
    super.initState();
    _selected = List.from(widget.answers.diningPreferences);
  }

  void _showAddCustomOptionDialog() {
    final controller = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: const Text("Add your own"),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(
              hintText: "Enter dining preference",
              border: OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancel"),
            ),
            ElevatedButton(
              onPressed: () {
                final value = controller.text.trim();

                final exists =
                    _options.contains(value) || _customOptions.contains(value);

                if (value.isNotEmpty && !exists) {
                  setState(() {
                    _customOptions.add(value);
                    _selected.add(value); // auto-select
                  });
                }

                Navigator.pop(context);
              },
              child: const Text("Add"),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final allOptions = [..._options, ..._customOptions];

    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen5.png',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'What type of dining experiences do you usually look for?',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),

          Padding(
            padding: const EdgeInsets.fromLTRB(24, 6, 24, 0),
            child: Text(
              'Select any of the following or add your own.',
              style: TextStyle(fontSize: 13, color: Colors.grey.shade600),
            ),
          ),

          const SizedBox(height: 16),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                ...allOptions.map((o) {
                  final sel = _selected.contains(o);

                  return ChoiceChip2(
                    label: o,
                    selected: sel,
                    onTap: () => setState(() {
                      sel ? _selected.remove(o) : _selected.add(o);
                    }),
                  );
                }),

                GestureDetector(
                  onTap: _showAddCustomOptionDialog,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.grey.shade300),
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: const [
                        Icon(Icons.add, size: 16, color: Colors.black54),
                        SizedBox(width: 6),
                        Text(
                          'Add your own',
                          style: TextStyle(fontSize: 13),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),

          NavButtons(
            onBack: widget.onBack,
            onNext: () {
              widget.answers.diningPreferences = _selected;
              widget.onNext();
            },
          ),
        ],
      ),
    );
  }
}