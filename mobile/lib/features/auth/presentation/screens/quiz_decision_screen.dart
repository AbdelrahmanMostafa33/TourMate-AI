import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../../quiz/logic/quiz_cubit.dart';
import '../../../quiz/logic/quiz_state.dart';


class QuizDecisionScreen extends StatelessWidget {
  const QuizDecisionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => QuizCubit(locator()),
      child: const _QuizDecisionView(),
    );
  }
}

class _QuizDecisionView extends StatelessWidget {
  const _QuizDecisionView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: BlocListener<QuizCubit, QuizState>(
          listener: (context, state) {
            state.whenOrNull(
              skipSuccess: () {
                Navigator.pushReplacementNamed(context, "/profile");
              },
              error: (msg) {
                ScaffoldMessenger.of(context)
                    .showSnackBar(SnackBar(content: Text(msg)));
              },
            );
          },
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                "Do you want to take a quick quiz to personalize your experience?",
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 18),
              ),

              const SizedBox(height: 40),

              /// YES → QUIZ
              ElevatedButton(
                onPressed: () {
                  Navigator.pushReplacementNamed(context, "/quiz");
                },
                child: const Text(
                  "Take the Quiz",
                  style: TextStyle(color: Colors.black),
                ),
              ),

              const SizedBox(height: 12),

              /// NO → SKIP
              OutlinedButton(
                onPressed: () {
                  Navigator.pushReplacementNamed(context, "/chat");
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("You can take the quiz later from your profile until then we have assigned you a default persona.")),
                  );
                },
                child: const Text(
                  "Do it later",
                  style: TextStyle(color: Colors.black),),
              ),
            ],
          ),
        ),
      ),
    );
  }
}