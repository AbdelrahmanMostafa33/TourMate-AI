import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import 'screen1_basics.dart';
import 'screen2_vacation.dart';
import 'screen3_accommodation.dart';
import 'screen4_activities.dart';
import 'screen5_dining.dart';
import 'screen6_interests.dart';
import 'screen7_traveler_type.dart';
import 'screen8_summary.dart';

class OnboardingQuizFlow extends StatefulWidget {
  const OnboardingQuizFlow({super.key});

  @override
  State<OnboardingQuizFlow> createState() => _OnboardingQuizFlowState();
}

class _OnboardingQuizFlowState extends State<OnboardingQuizFlow> {
  int _currentScreen = 0;
  bool _isForward = true;

  final QuizAnswers _answers = QuizAnswers();

  // 🔥 SCREENS LIST OUTSIDE BUILD
  List<Widget> _screens() => [
        Screen1Basics(answers: _answers, onNext: _next),

        Screen2Vacation(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen3Accommodation(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen4Activities(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen5Dining(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen6Interests(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen7TravelerType(
          answers: _answers,
          onNext: _next,
          onBack: _back,
          onSaveExit: _saveAndExit,
        ),

        Screen8Summary(
          answers: _answers,
          onStartChat: _finish,
          onBack: _back,
        ),
      ];

  void _next() {
    _isForward = true;

    if (_currentScreen < _screens().length - 1) {
      setState(() => _currentScreen++);
    } else {
      _finish();
    }
  }

  void _back() {
    _isForward = false;

    if (_currentScreen > 0) {
      setState(() => _currentScreen--);
    }
  }

  void _saveAndExit() {
    Navigator.pop(context);
  }

  void _finish() {
    // 🔥 navigate using named route
    Navigator.pushReplacementNamed(context, "/signin");

    // later: send answers to backend here
    // print(_answers.toJson());
  }

  @override
  Widget build(BuildContext context) {
    final screens = _screens();

    return Scaffold(
      body: SafeArea(
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 350),
          transitionBuilder: (child, animation) {
            final offsetAnimation = Tween<Offset>(
              begin: _isForward
                  ? const Offset(1, 0)
                  : const Offset(-1, 0),
              end: Offset.zero,
            ).animate(CurvedAnimation(
              parent: animation,
              curve: Curves.easeInOut,
            ));

            return SlideTransition(
              position: offsetAnimation,
              child: child,
            );
          },
          child: KeyedSubtree(
            key: ValueKey(_currentScreen),
            child: screens[_currentScreen],
          ),
        ),
      ),
    );
  }
}