import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';

class Screen6Interests extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack;

  const Screen6Interests({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
  });

  @override
  State<Screen6Interests> createState() => _Screen6InterestsState();
}

class _Screen6InterestsState extends State<Screen6Interests> {
  late List<String> _selected;
  final List<String> _customOptions = [];

  final List<String> _options = [
    'Adventure Sports',
    'Theatre',
    'Beach',
    'Hiking',
    'Mountains',
    'Mountain Slopes',
    'Spas / Wellness',
    'Photography',
    'Cooking Classes',
    'Fine Dining',
    'Nightlife',
    'Wine Tasting',
    'Shopping',
    'Water Sports',
    'Cycling',
    'The Atlantic',
    'The Mediterranean',
    'The Abyss',
    'Snorkelling',
    'Wildlife',
    'The Galapagos Travel',
    'The Underground Travel',
  ];

  @override
  void initState() {
    super.initState();
    _selected = List.from(widget.answers.interests);
  }

  /// 🔥 SAME LOGIC AS SCREEN 3
  void _showAddCustomOptionDialog() {
    final controller = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Add your own"),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: "Enter interest",
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
                  _selected.contains(value) ||
                      _options.contains(value) ||
                      _customOptions.contains(value);

              if (value.isNotEmpty && !exists) {
                setState(() {
                  _customOptions.add(value);
                  _selected.add(value);
                });
              }

              Navigator.pop(context);
            },
            child: const Text("Add"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final allOptions = [..._options, ..._customOptions];

    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen6.png',
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              /// TITLE
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
                child: Row(
                  children: const [
                    Expanded(
                      child: Text(
                        'What are your interests or favorite things to do while traveling?',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              /// SUBTITLE
              Padding(
                padding: const EdgeInsets.fromLTRB(24, 6, 24, 0),
                child: Text(
                  'Select any of the following or add your own.',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey.shade600,
                  ),
                ),
              ),

              const SizedBox(height: 16),

              /// OPTIONS
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

                    /// ✅ ADD YOUR OWN (NOW WORKING)
                    GestureDetector(
                      onTap: _showAddCustomOptionDialog,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 10,
                        ),
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.grey.shade300),
                          borderRadius: BorderRadius.circular(24),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.add,
                                size: 16, color: Colors.grey.shade600),
                            const SizedBox(width: 6),
                            Text(
                              'Add your own',
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.grey.shade600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 24),

              /// NAV BUTTONS
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: NavButtons(
                  onBack: widget.onBack,
                  onNext: () {
                    widget.answers.interests = _selected;
                    widget.onNext();
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}