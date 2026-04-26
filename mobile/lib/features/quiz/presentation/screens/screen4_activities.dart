import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';
import '../widgets/slider_toggle.dart';

class Screen4Activities extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack;

  const Screen4Activities({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
  });

  @override
  State<Screen4Activities> createState() => _Screen4ActivitiesState();
}

class _Screen4ActivitiesState extends State<Screen4Activities> {
  double _budgetValue = 0.5;
  double _scheduleValue = 0.5;
  double _independenceValue = 0.5;

  @override
  void initState() {
    super.initState();

    _budgetValue = widget.answers.budgetLevel / 100;
    _scheduleValue = widget.answers.earlyNight / 100;
    _independenceValue = widget.answers.independentSocial / 100;
  }

  void _save() {
    widget.answers
      ..budgetLevel = (_budgetValue * 100).round()
      ..earlyNight = (_scheduleValue * 100).round()
      ..independentSocial = (_independenceValue * 100).round();

    widget.onNext();
  }

  @override
  Widget build(BuildContext context) {
    return QuizScaffold(
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ─────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    'What do you like to do?',
                    style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 10),

          // ── Budget ─────────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'What best describes your travel spending habits?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Budget conscious',
              rightLabel: 'Luxurious',
              value: _budgetValue,
              onChanged: (v) {
                setState(() => _budgetValue = v);
              },
            ),
          ),

          if (_budgetValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Smart spender 💰'),
            ),

          if (_budgetValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Go big or go home 💸'),
            ),

          const SizedBox(height: 24),

          // ── Schedule ─────────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Would you rather get an early start or stay out late?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Early bird',
              rightLabel: 'Night owl',
              value: _scheduleValue,
              onChanged: (v) {
                setState(() => _scheduleValue = v);
              },
            ),
          ),

          if (_scheduleValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Fresh mornings 🌅'),
            ),

          if (_scheduleValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Night owl 🌙'),
            ),

          const SizedBox(height: 24),

          // ── Independence ─────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Independent streak or social traveler?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Independent',
              rightLabel: 'Social',
              value: _independenceValue,
              onChanged: (v) {
                setState(() => _independenceValue = v);
              },
            ),
          ),

          if (_independenceValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Solo explorer 🧭'),
            ),

          if (_independenceValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('People person 👥'),
            ),

          const SizedBox(height: 20),

          NavButtons(
            onBack: widget.onBack,
            onNext: _save,
          ),
        ],
      ),
    );
  }
}