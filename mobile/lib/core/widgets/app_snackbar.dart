import 'package:flutter/material.dart';

/// A polished, reusable snackbar utility for consistent app-wide feedback.
///
/// Usage:
/// ```dart
/// AppSnackbar.success(context, 'Welcome back!');
/// AppSnackbar.error(context, 'Something went wrong');
/// AppSnackbar.info(context, 'Trip created!');
/// AppSnackbar.warning(context, 'Please fill in all fields');
/// ```
class AppSnackbar {
  AppSnackbar._();

  /// Shows a green success snackbar with a checkmark icon.
  static void success(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 3),
  }) {
    _show(
      context,
      message: message,
      icon: Icons.check_circle_rounded,
      backgroundColor: const Color(0xFF2E7D32),
      duration: duration,
    );
  }

  /// Shows a red error snackbar with an error icon.
  static void error(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 4),
  }) {
    _show(
      context,
      message: message,
      icon: Icons.error_rounded,
      backgroundColor: const Color(0xFFC62828),
      duration: duration,
    );
  }

  /// Shows a blue info snackbar with an info icon.
  static void info(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 3),
  }) {
    _show(
      context,
      message: message,
      icon: Icons.info_rounded,
      backgroundColor: const Color(0xFF1565C0),
      duration: duration,
    );
  }

  /// Shows an orange warning snackbar with a warning icon.
  static void warning(
    BuildContext context,
    String message, {
    Duration duration = const Duration(seconds: 3),
  }) {
    _show(
      context,
      message: message,
      icon: Icons.warning_rounded,
      backgroundColor: const Color(0xFFE65100),
      duration: duration,
    );
  }

  static void _show(
    BuildContext context, {
    required String message,
    required IconData icon,
    required Color backgroundColor,
    Duration duration = const Duration(seconds: 3),
  }) {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(icon, color: Colors.white, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: Colors.white,
                    height: 1.3,
                  ),
                ),
              ),
            ],
          ),
          backgroundColor: backgroundColor,
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          duration: duration,
          dismissDirection: DismissDirection.horizontal,
          elevation: 6,
        ),
      );
  }
}
