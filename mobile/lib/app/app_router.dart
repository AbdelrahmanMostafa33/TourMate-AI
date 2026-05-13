import 'package:flutter/material.dart';
import '../core/layout/main_shell.dart';
import '../features/auth/presentation/screens/quiz_decision_screen.dart';
import '../features/auth/presentation/screens/signin_screen.dart';
import '../features/auth/presentation/screens/signup_screen.dart';
import '../features/auth/presentation/screens/profile_screen.dart';
import '../features/chat/presentation/screens/chat_screen.dart';
import '../features/quiz/presentation/screens/onboarding_flow.dart';
import '../features/splash/splash_screen.dart';
import '../features/trips/presentation/screens/create_trip_screen.dart';
import '../features/trips/presentation/screens/trips_screen.dart';

class AppRouter {
  static Route generateRoute(RouteSettings settings) {
    switch(settings.name){

      case "/":
        return MaterialPageRoute(builder: (_) => const SplashScreen());

      case "/home":
        return MaterialPageRoute(builder: (_) => const MainShell());

      case "/signin":
        return MaterialPageRoute(builder: (_) => const SignInScreen());

      case "/signup":
        return MaterialPageRoute(builder: (_) => const SignUpScreen());

      case"/quiz":
        return MaterialPageRoute(builder: (_) => const OnboardingQuizFlow());

      case "/profile":
        return MaterialPageRoute(builder: (_) => const ProfileScreen());

      case "/quiz-decision":
        return MaterialPageRoute(builder: (_) => const QuizDecisionScreen());

      case "/chat":
        return MaterialPageRoute(builder: (_) => const ChatScreen());

      case "/trips":
        return MaterialPageRoute(builder: (_) => const TripsScreen());

      case "/create-trip":
        return MaterialPageRoute(builder: (_) => const CreateTripScreen());

      default:
        return MaterialPageRoute(
          builder: (_) => const Scaffold(
            body: Center(child: Text("No Route Found")),
          ),
        );
    }
  }
}