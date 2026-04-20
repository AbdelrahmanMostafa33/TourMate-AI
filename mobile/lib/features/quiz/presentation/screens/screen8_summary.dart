import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';

class Screen8Summary extends StatelessWidget {
  final QuizAnswers answers;
  final VoidCallback onStartChat, onBack;
  const Screen8Summary(
      {super.key, required this.answers, required this.onStartChat, required this.onBack});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Hero
              Container(
                height: 180,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0D47A1), Color(0xFF1565C0)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                child: const Center(
                  child: Icon(Icons.nightlife, size: 72, color: Colors.white),
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'Adventurous\nIndependent ${answers.earlyNight == 100 ? "Nightowl" : "${answers.diningPreferences.join(", ")}!"}',
                style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Text(
                'I thrive on exciting adventures and cultural discoveries, embracing spontaneous explorations and always seeking out local experiences — especially after dark.',
                style: TextStyle(fontSize: 14, color: Colors.grey.shade700, height: 1.5),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () {},
                style: TextButton.styleFrom(padding: EdgeInsets.zero),
                child: const Text('Read more', style: TextStyle(color: Colors.black, fontWeight: FontWeight.w600)),
              ),
              if (answers.interests.isNotEmpty) ...[
                const SizedBox(height: 16),
                const Text('Interests', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: answers.interests
                      .take(5)
                      .map((i) => ChoiceChip2(label: i, selected: true, onTap: () {}))
                      .toList(),
                ),
              ],
              const SizedBox(height: 32),
              NavButtons(onBack: onBack, onNext: onStartChat, nextLabel: 'Start chatting'),
            ],
          ),
        ),
      ),
    );
  }
}
