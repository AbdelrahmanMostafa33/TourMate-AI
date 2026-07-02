import 'package:flutter/material.dart';
import '../core/layout/main_shell.dart';
import '../features/auth/presentation/screens/signin_screen.dart';
import '../features/auth/presentation/screens/signup_screen.dart';
import '../features/auth/presentation/screens/profile_screen.dart';
import '../features/chat/presentation/screens/chat_screen.dart';
import '../features/places/presentation/screens/place_detail_screen.dart';
import '../features/splash/splash_screen.dart';
import '../features/trips/presentation/screens/create_trip_screen.dart';
import '../features/trips/presentation/screens/trip_detail_screen.dart';
import '../features/trips/presentation/screens/trips_screen.dart';

class AppRouter {
  /// A premium fade-through route transition for the splash → home
  /// handoff. The new screen fades in over 600ms with an easeOut curve.
  static Route _fadeThroughRoute(Widget page) {
    return PageRouteBuilder(
      pageBuilder: (context, animation, secondaryAnimation) => page,
      transitionsBuilder: (context, animation, secondaryAnimation, child) {
        return FadeTransition(
          opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
            CurvedAnimation(
              parent: animation,
              curve: Curves.easeOut,
            ),
          ),
          child: child,
        );
      },
      transitionDuration: const Duration(milliseconds: 600),
    );
  }

  static Route generateRoute(RouteSettings settings) {
    switch(settings.name){

      case "/":
        return MaterialPageRoute(builder: (_) => const SplashScreen());

      case "/home":
        return _fadeThroughRoute(const MainShell());

      case "/signin":
        return _fadeThroughRoute(const SignInScreen());

      case "/signup":
        return MaterialPageRoute(builder: (_) => const SignUpScreen());

      case "/profile":
        return MaterialPageRoute(builder: (_) => const ProfileScreen());

      case "/chat":
        final chatArgs = settings.arguments;
        if (chatArgs is Map<String, dynamic>) {
          final tripId = chatArgs['trip_id'] as String?;
          return MaterialPageRoute(
            builder: (_) => ChatScreen(initialTripId: tripId),
          );
        }
        return MaterialPageRoute(builder: (_) => const ChatScreen());

      case "/trips":
        return MaterialPageRoute(builder: (_) => const TripsScreen());

      case "/trip-detail":
        final tripId = settings.arguments as String;
        return MaterialPageRoute(
          builder: (_) => TripDetailScreen(tripId: tripId),
        );

      case "/create-trip":
        return MaterialPageRoute(builder: (_) => const CreateTripScreen());

      case "/place-detail":
        final placeId = settings.arguments as String;
        return MaterialPageRoute(
          builder: (_) => PlaceDetailScreen(placeId: placeId),
        );

      default:
        return MaterialPageRoute(
          builder: (_) => const Scaffold(
            body: Center(child: Text("No Route Found")),
          ),
        );
    }
  }
}