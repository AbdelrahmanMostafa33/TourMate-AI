import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';
import '../widgets/save_exit_button.dart';
import '../widgets/slider_toggle.dart';

class Screen2Vacation extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack, onSaveExit;

  const Screen2Vacation({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
    required this.onSaveExit,
  });

  @override
  State<Screen2Vacation> createState() => _Screen2VacationState();
}

class _Screen2VacationState extends State<Screen2Vacation> {
  double _styleValue = 0.5;
  double _natureValue = 0.5;
  double _attractionsValue = 0.5;

  @override
  void initState() {
    super.initState();

    _styleValue = widget.answers.adventureRelaxing / 100;
    _natureValue = widget.answers.natureCulture / 100;
    _attractionsValue = widget.answers.popularLocal / 100;
  }

  void _save() {
    widget.answers
      ..adventureRelaxing = (_styleValue * 100).round()
      ..natureCulture = (_natureValue * 100).round()
      ..popularLocal = (_attractionsValue * 100).round();

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
                    'How do you like to vacation?',
                    style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
                  ),
                ),
                SaveExitButton(onTap: widget.onSaveExit),
              ],
            ),
          ),

          const SizedBox(height: 10),

          // ── STYLE ─────────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Do you prefer adventure or relaxation?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Adventurous',
              rightLabel: 'Relaxing',
              value: _styleValue,
              onChanged: (v) => setState(() => _styleValue = v),
            ),
          ),

          if (_styleValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Adventure mode on!'),
            ),

          if (_styleValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Relax & unwind'),
            ),

          const SizedBox(height: 24),

          // ── NATURE ─────────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Do you prefer nature or culture?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Nature',
              rightLabel: 'Culture',
              value: _natureValue,
              onChanged: (v) => setState(() => _natureValue = v),
            ),
          ),

          if (_natureValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Nature lover 🌿'),
            ),

          if (_natureValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Culture explorer 🏛️'),
            ),

          const SizedBox(height: 24),

          // ── ATTRACTIONS ─────────────────────────
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 24),
            child: Text(
              'Do you like popular places or local experiences?',
              style: TextStyle(fontSize: 20, color: Colors.black),
            ),
          ),

          const SizedBox(height: 12),

          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: SliderToggle(
              leftLabel: 'Popular',
              rightLabel: 'Local',
              value: _attractionsValue,
              onChanged: (v) => setState(() => _attractionsValue = v),
            ),
          ),

          if (_attractionsValue <= 0.3)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Tourist hotspots 📍'),
            ),

          if (_attractionsValue >= 0.7)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
              child: Text('Hidden gems ✨'),
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