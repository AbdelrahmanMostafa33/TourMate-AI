import 'package:flutter/material.dart';
import '../../data/models/user_response.dart';

/// A visually prominent card that showcases the user's traveler persona.
///
/// When the backend [UserResponse.travelerPersona] is null (the current
/// default), the card shows a friendly "Globe Trotter" default rather
/// than an empty space.
class PersonaCard extends StatelessWidget {
  final UserResponse profile;

  const PersonaCard({super.key, required this.profile});

  @override
  Widget build(BuildContext context) {
    final persona = _derivePersona(profile);
    final isDark = persona.themeBrightness == Brightness.dark;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: persona.gradient,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: persona.accentColor.withValues(alpha: 0.25),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header row ──────────────────────────────────────────
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: isDark
                      ? Colors.white.withValues(alpha: 0.15)
                      : Colors.black.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  persona.icon,
                  size: 26,
                  color: isDark ? Colors.white : Colors.black87,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "YOUR TRAVELER PERSONA",
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.5,
                        color: isDark
                            ? Colors.white.withValues(alpha: 0.6)
                            : Colors.black.withValues(alpha: 0.45),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      persona.name,
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        color: isDark ? Colors.white : Colors.black87,
                        letterSpacing: -0.3,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 14),

          // ── Description ─────────────────────────────────────────
          Text(
            persona.description,
            style: TextStyle(
              fontSize: 13,
              height: 1.4,
              color: isDark
                  ? Colors.white.withValues(alpha: 0.8)
                  : Colors.black.withValues(alpha: 0.65),
            ),
          ),

          // ── Trait chips ─────────────────────────────────────────
          if (persona.traits.isNotEmpty) ...[
            const SizedBox(height: 14),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: persona.traits.map((trait) {
                return Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: isDark
                        ? Colors.white.withValues(alpha: 0.15)
                        : persona.accentColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    trait,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: isDark ? Colors.white : persona.accentColor,
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  // ── Persona derivation ─────────────────────────────────────────────

  /// Derive a [DerivedPersona] from the user, falling back to a generic
  /// "Globe Trotter" when [travelerPersona] has not been set yet.
  static DerivedPersona _derivePersona(UserResponse profile) {
    final backendPersona = profile.travelerPersona;

    if (backendPersona != null && backendPersona.isNotEmpty) {
      // Derive a short name from the first sentence or use a generic title
      final shortName = _derivePersonaName(backendPersona);
      return DerivedPersona(
        name: shortName,
        description: backendPersona,
        icon: _defaultPersona.icon,
        accentColor: _defaultPersona.accentColor,
        gradient: _defaultPersona.gradient,
        traits: ['Personalized for you'],
        themeBrightness: Brightness.light,
      );
    }

    return _defaultPersona;
  }

  /// Extract a short, readable title from the full persona description.
  static String _derivePersonaName(String text) {
    final lower = text.toLowerCase();

    if (lower.contains('adventure') || lower.contains('thrill')) {
      return 'Adventure Seeker';
    }
    if (lower.contains('luxury') || lower.contains('premium') || lower.contains('comfort')) {
      return 'Luxury Traveler';
    }
    if (lower.contains('budget') && lower.contains('moderate')) {
      return 'Balanced Explorer';
    }
    if (lower.contains('budget') || lower.contains('cheap') || lower.contains('save')) {
      return 'Budget Traveler';
    }
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary') || lower.contains('local cuisine')) {
      return 'Food Explorer';
    }
    if (lower.contains('nature') || lower.contains('outdoor') || lower.contains('hike')) {
      return 'Nature Lover';
    }
    if (lower.contains('cultural') || lower.contains('history') || lower.contains('museum')) {
      return 'Culture Enthusiast';
    }
    if (lower.contains('slow') || lower.contains('relax')) {
      return 'Slow Traveler';
    }
    if (lower.contains('fast') || lower.contains('quick')) {
      return 'Fast Pacer';
    }
    if (lower.contains('sport') || lower.contains('active')) {
      return 'Active Traveler';
    }

    return 'Your Travel Style';
  }

  static const _defaultPersona = DerivedPersona(
    name: 'Globe Trotter',
    description:
        'You\'re ready for your next adventure. Start chatting with TourMate '
        'and we\'ll discover your travel personality!',
    icon: Icons.public_rounded,
    accentColor: Color(0xFF5E8B8F),
    gradient: LinearGradient(
      colors: [Color(0xFFE8F0F0), Color(0xFFD0E2E3)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    traits: ['Ready to explore', 'New adventures'],
    themeBrightness: Brightness.light,
  );
}

/// Internal data class holding the display values for a derived persona.
class DerivedPersona {
  final String name;
  final String description;
  final IconData icon;
  final Color accentColor;
  final LinearGradient gradient;
  final List<String> traits;
  final Brightness themeBrightness;

  const DerivedPersona({
    required this.name,
    required this.description,
    required this.icon,
    required this.accentColor,
    required this.gradient,
    required this.traits,
    required this.themeBrightness,
  });
}
