import 'package:flutter/material.dart';
import '../features/auth/presentation/screens/signin_screen.dart';
import '../features/auth/presentation/screens/signup_screen.dart';
import '../features/quiz/presentation/screens/onboarding_flow.dart';
import '../features/splash/splash_screen.dart';

class AppRouter {
  static Route generateRoute(RouteSettings settings) {
switch(settings.name){

case "/":
return MaterialPageRoute(builder: (_) => const SplashScreen());

case "/signin":
return MaterialPageRoute(builder: (_) => const SignInScreen());

case "/signup":
return MaterialPageRoute(builder: (_) => const SignUpScreen());

case"/quiz":
return MaterialPageRoute(builder: (_) => const OnboardingQuizFlow());

default:
return MaterialPageRoute(
builder: (_) => const Scaffold(
body: Center(child: Text("No Route Found")),
),
);
}
  }
}