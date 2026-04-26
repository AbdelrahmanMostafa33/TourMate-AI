import 'package:flutter/material.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/models/persona_response.dart';
import '../../data/models/quiz_answers.dart';
import '../../data/models/quiz_submit_request.dart';
import '../../data/repository/quiz_repository.dart';
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
  bool _isLoading = false;

  final QuizAnswers _answers = QuizAnswers();
  final QuizRepository _quizRepo = locator<QuizRepository>();

  // Holds the API response once we get it
  PersonaResponse? _personaResponse;

  // ── screen list ──────────────────────────────────────────
  List<Widget> _screens() => [
    Screen1Basics(answers: _answers, onNext: _next),
    Screen2Vacation(
      answers: _answers, onNext: _next,
      onBack: _back,
    ),
    Screen3Accommodation(
      answers: _answers, onNext: _next,
      onBack: _back,
    ),
    Screen4Activities(
      answers: _answers, onNext: _next,
      onBack: _back,
    ),
    Screen5Dining(
      answers: _answers, onNext: _next,
      onBack: _back,
    ),
    Screen6Interests(
      answers: _answers, onNext: _next,
      onBack: _back,
    ),
    Screen7TravelerType(
      answers: _answers,
      onNext: _submitAndGoToSummary, // calls API then navigates
      onBack: _back,
    ),
    Screen8Summary(
      persona: _personaResponse, // pass persona instead of answers
      onStartChat: _finish,
      onBack: _back,
    ),
  ];

  // ── normal next ──────────────────────────────────────────
  void _next() {
    _isForward = true;
    if (_currentScreen < _screens().length - 1) {
      setState(() => _currentScreen++);
    }
  }

  // ── back ─────────────────────────────────────────────────
  void _back() {
    _isForward = false;
    if (_currentScreen > 0) {
      setState(() => _currentScreen--);
    }
  }

  // ── Screen 7 → submit quiz then go to Screen 8 ──────────
  Future<void> _submitAndGoToSummary() async {
    setState(() => _isLoading = true);

    final body = QuizSubmitRequest(
      age: _answers.age,
      sex: _answers.sex,
      travelCompanion: _answers.travelCompanion,
      location: _answers.location,
      adventureRelaxing: _answers.adventureRelaxing,
      natureCulture: _answers.natureCulture,
      popularLocal: _answers.popularLocal,
      budgetLevel: _answers.budgetLevel,
      earlyNight: _answers.earlyNight,
      independentSocial: _answers.independentSocial,
      accommodationStyles: _answers.accommodationStyles,
      diningPreferences: _answers.diningPreferences,
      interests: _answers.interests,
      travelerTypes: _answers.travelerTypes,
    ).toJson();

    final result = await _quizRepo.submitQuiz(body);

    if (!mounted) return;

    result.when(
      success: (persona) {
        _personaResponse = persona;
        _isForward = true;
        setState(() {
          _isLoading = false;
          _currentScreen = _screens().length - 1; // jump to Screen 8
        });
      },
      failure: (msg) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to submit quiz: $msg')),
        );
      },
    );
  }


  // ── finish → leave quiz ──────────────────────────────────
  void _finish() {
    Navigator.pushReplacementNamed(context, "/profile");
  }

  // ── build ────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final screens = _screens();

    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            AnimatedSwitcher(
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

            // 🔥 full-screen loading overlay while API is in flight
            if (_isLoading)
              Container(
                color: Colors.black26,
                child: const Center(
                  child: CircularProgressIndicator(color: Colors.white),
                ),
              ),
          ],
        ),
      ),
    );
  }
}