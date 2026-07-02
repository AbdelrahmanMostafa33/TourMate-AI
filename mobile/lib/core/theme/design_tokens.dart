import 'package:flutter/material.dart';

// ═══════════════════════════════════════════════════════════════════════════════
// TOURMATE DESIGN TOKENS — Spacing · Radius · Shadows · Motion · Gradients
// ═══════════════════════════════════════════════════════════════════════════════
//
// Centralized constants based on a 4px grid, extended for a luxury design system.
// Every value here is intentional — nothing is arbitrary.
//
// ═══════════════════════════════════════════════════════════════════════════════

// ─────────────────────────────────────────────────────────────────────────────
// SPACING — 4px base grid
// ─────────────────────────────────────────────────────────────────────────────

class Spacing {
  Spacing._();

  static const double xxs = 2;
  static const double xs = 4;
  static const double sm = 6;
  static const double md = 8;
  static const double lg = 10;
  static const double xl = 12;
  static const double xl2 = 14;
  static const double xl3 = 16;
  static const double xl4 = 20;
  static const double xl5 = 24;
  static const double xl6 = 28;
  static const double xl7 = 32;
  static const double xl8 = 40;
  static const double xl9 = 48;
  static const double xl10 = 56;
  static const double xl11 = 64;
}

// ─────────────────────────────────────────────────────────────────────────────
// BORDER RADIUS — from subtle to bold
// ─────────────────────────────────────────────────────────────────────────────

class RadiusTokens {
  RadiusTokens._();

  static const double none = 0;
  static const double xxs = 2;
  static const double xs = 4;
  static const double sm = 6;
  static const double md = 8;
  static const double lg = 10;
  static const double xl = 12;
  static const double xl2 = 14;
  static const double xl3 = 16;
  static const double xl4 = 20;
  static const double xl5 = 24;
  static const double xl6 = 28;
  static const double xl7 = 32;
  static const double xl8 = 40;
  static const double full = 999;
}

// ─────────────────────────────────────────────────────────────────────────────
// SHADOWS — layered from subtle to dramatic
// ─────────────────────────────────────────────────────────────────────────────

class ShadowTokens {
  ShadowTokens._();

  /// Subtle shadow for cards at rest.
  static List<BoxShadow> subtle(Color shadowColor) => [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.04),
          blurRadius: 4,
          offset: const Offset(0, 1),
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.02),
          blurRadius: 8,
          offset: const Offset(0, 2),
        ),
      ];

  /// Medium shadow for elevated cards.
  static List<BoxShadow> medium(Color shadowColor) => [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.06),
          blurRadius: 6,
          offset: const Offset(0, 2),
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.04),
          blurRadius: 16,
          offset: const Offset(0, 6),
        ),
      ];

  /// Large shadow for modals, bottom sheets.
  static List<BoxShadow> large(Color shadowColor) => [
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.08),
          blurRadius: 10,
          offset: const Offset(0, 4),
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.06),
          blurRadius: 24,
          offset: const Offset(0, 12),
        ),
      ];

  /// Premium gold-tinted shadow for VIP elements.
  static List<BoxShadow> premium(Color goldColor, Color shadowColor) => [
        BoxShadow(
          color: goldColor.withValues(alpha: 0.12),
          blurRadius: 8,
          offset: const Offset(0, 2),
        ),
        BoxShadow(
          color: goldColor.withValues(alpha: 0.06),
          blurRadius: 20,
          offset: const Offset(0, 8),
        ),
        BoxShadow(
          color: shadowColor.withValues(alpha: 0.04),
          blurRadius: 32,
          offset: const Offset(0, 16),
        ),
      ];
}

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION / MOTION — durations & curves for premium feel
// ─────────────────────────────────────────────────────────────────────────────

class MotionTokens {
  MotionTokens._();

  // Durations
  static const Duration instant = Duration(milliseconds: 100);
  static const Duration fast = Duration(milliseconds: 200);
  static const Duration normal = Duration(milliseconds: 300);
  static const Duration slow = Duration(milliseconds: 500);
  static const Duration deliberate = Duration(milliseconds: 800);

  // Curves
  static const Curve defaultCurve = Curves.easeInOut;
  static const Curve emphasis = Curves.easeOutCubic;
  static const Curve decelerate = Curves.easeOutQuint;
  static const Curve accelerate = Curves.easeInQuint;
  static const Curve spring = Curves.elasticOut;
  static const Curve swift = Curves.fastOutSlowIn;
}

// ─────────────────────────────────────────────────────────────────────────────
// GRADIENTS — luxury linear gradients
// ─────────────────────────────────────────────────────────────────────────────

class GradientTokens {
  GradientTokens._();

  /// Dark, sophisticated background gradient (black → dark gray).
  static const LinearGradient darkBackground = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [
      Color(0xFF0A0A0A),
      Color(0xFF141414),
    ],
  );

  /// Gold accent gradient for premium buttons and highlights.
  static const LinearGradient goldAccent = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFD4AF37),
      Color(0xFFC8A84E),
      Color(0xFFB8942E),
    ],
  );

  /// Gold-to-black for dramatic premium moments.
  static const LinearGradient goldToBlack = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFC8A84E),
      Color(0xFF0A0A0A),
    ],
  );

  /// Subtle gold shimmer for loading states.
  static const LinearGradient goldShimmer = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [
      Color(0xFFFFF9EC),
      Color(0xFFF5ECCE),
      Color(0xFFFFF9EC),
    ],
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ICON SIZES — consistent icon sizing
// ─────────────────────────────────────────────────────────────────────────────

class IconSizes {
  IconSizes._();

  static const double xxs = 12;
  static const double xs = 14;
  static const double sm = 16;
  static const double md = 18;
  static const double lg = 20;
  static const double xl = 22;
  static const double xl2 = 24;
  static const double xl3 = 28;
  static const double xl4 = 32;
  static const double xl5 = 40;
  static const double xl6 = 48;
}

// ─────────────────────────────────────────────────────────────────────────────
// INSETS — reusable EdgeInsets composites
// ─────────────────────────────────────────────────────────────────────────────

class Insets {
  Insets._();

  static const EdgeInsets chip = EdgeInsets.symmetric(horizontal: 12, vertical: 6);
  static const EdgeInsets button = EdgeInsets.symmetric(horizontal: 28, vertical: 16);
  static const EdgeInsets buttonCompact = EdgeInsets.symmetric(horizontal: 20, vertical: 12);
  static const EdgeInsets input = EdgeInsets.symmetric(horizontal: 16, vertical: 16);
  static const EdgeInsets buttonLarge = EdgeInsets.symmetric(horizontal: 24, vertical: 18);
  static const EdgeInsets message = EdgeInsets.symmetric(horizontal: 16, vertical: 12);
  static const EdgeInsets cardHeader = EdgeInsets.fromLTRB(20, 20, 20, 16);
  static const EdgeInsets cardFooter = EdgeInsets.fromLTRB(20, 16, 20, 20);
  static const EdgeInsets screenContent = EdgeInsets.fromLTRB(16, 4, 16, 16);
  static const EdgeInsets page = EdgeInsets.symmetric(horizontal: 20);
  static const EdgeInsets pageWide = EdgeInsets.symmetric(horizontal: 24);
}
