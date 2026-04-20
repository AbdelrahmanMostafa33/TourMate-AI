import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';
import '../widgets/save_exit_button.dart';

class Screen6Interests extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack, onSaveExit;
  const Screen6Interests(
      {super.key,
      required this.answers,
      required this.onNext,
      required this.onBack,
      required this.onSaveExit});

  @override
  State<Screen6Interests> createState() => _Screen6InterestsState();
}

class _Screen6InterestsState extends State<Screen6Interests> {
  late List<String> _selected;

  final _options = [
    'Adventure Sports', 'Theatre', 'Beach', 'Hiking', 'Mountains', 'Mountain Slopes',
    'Spas / Wellness', 'Photography', 'Cooking Classes', 'Fine Dining',
    'Nightlife', 'Wine Tasting', 'Shopping', 'Water Sports', 'Cycling',
    'The Atlantic', 'The Mediterranean', 'The Abyss', 'Snorkelling', 'Wildlife',
    'The Galapagos Travel', 'The Underground Travel',
  ];

  @override
  void initState() {
    super.initState();
    _selected = List.from(widget.answers.interests);
  }

  @override
  Widget build(BuildContext context) {
    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen6.png',
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text('What are your interests or favorite things todo while traveling?',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                ),
                SaveExitButton(onTap: widget.onSaveExit),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 6, 24, 0),
            child: Text('Select any of the following or add your own.',
                style: TextStyle(fontSize: 13, color: Colors.grey.shade600)),
          ),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                ..._options.map((o) {
                  final sel = _selected.contains(o);
                  return ChoiceChip2(
                    label: o,
                    selected: sel,
                    onTap: () => setState(() => sel ? _selected.remove(o) : _selected.add(o)),
                  );
                }),
                GestureDetector(
                  onTap: () {},
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      border: Border.all(color: Colors.grey.shade300),
                      borderRadius: BorderRadius.circular(24),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.add, size: 16, color: Colors.grey.shade600),
                        const SizedBox(width: 4),
                        Text('Add your own', style: TextStyle(fontSize: 13, color: Colors.grey.shade600)),
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
              widget.answers.interests = _selected;
              widget.onNext();
            },
          ),
        ],
      ),
    );
  }
}
