import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
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
    final tm = context.tm;
    final persona = _derivePersona(profile);
    final isDark = persona.themeBrightness == Brightness.dark;
    final hasBackendData = profile.travelerPersona != null &&
        profile.travelerPersona!.isNotEmpty;

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: persona.gradient,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(
          color: persona.accentColor.withValues(alpha: 0.3),
          width: 0.5,
        ),
        boxShadow: [
          BoxShadow(
            color: persona.accentColor.withValues(alpha: 0.25),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(Spacing.xl4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header row ────────────────────────────────────────
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // Icon with accent border accent
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: isDark
                        ? tm.pureWhite.withValues(alpha: 0.15)
                        : tm.pureBlack.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(RadiusTokens.xl2),
                    border: Border.all(
                      color: persona.accentColor.withValues(alpha: 0.25),
                      width: 0.5,
                    ),
                  ),
                  child: Icon(
                    persona.icon,
                    size: 26,
                    color: isDark ? tm.pureWhite : tm.textPrimary,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        "YOUR TRAVELER PERSONA",
                        style: GoogleFonts.inter(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.5,
                          color: isDark
                              ? tm.pureWhite.withValues(alpha: 0.6)
                              : tm.textPrimary.withValues(alpha: 0.45),
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        persona.name,
                        style: GoogleFonts.inter(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: isDark ? tm.pureWhite : tm.textPrimary,
                          letterSpacing: -0.3,
                        ),
                      ),
                    ],
                  ),
                ),
                // Confidentiality gauge
                if (hasBackendData)
                  _ConfidenceGauge(
                    accentColor: persona.accentColor,
                    isDark: isDark,
                    tm: tm,
                  ),
              ],
            ),

            const SizedBox(height: 14),

            // ── Description ───────────────────────────────────────
            Text(
              persona.description,
              style: GoogleFonts.inter(
                fontSize: 13,
                height: 1.45,
                color: isDark
                    ? tm.pureWhite.withValues(alpha: 0.8)
                    : tm.textPrimary.withValues(alpha: 0.65),
              ),
            ),

            // ── Trait chips with icons ────────────────────────────
            if (persona.traits.isNotEmpty) ...[
              const SizedBox(height: Spacing.xl3),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: persona.traits.map((trait) {
                  final traitInfo = _traitDisplay(trait);
                  return Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 5,
                    ),
                    decoration: BoxDecoration(
                      color: isDark
                          ? tm.pureWhite.withValues(alpha: 0.15)
                          : persona.accentColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(RadiusTokens.xl),
                      border: Border.all(
                        color: persona.accentColor.withValues(alpha: 0.15),
                        width: 0.5,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          traitInfo.icon,
                          size: 12,
                          color: isDark
                              ? tm.pureWhite
                              : persona.accentColor,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          traitInfo.label,
                          style: GoogleFonts.inter(
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                            color: isDark
                                ? tm.pureWhite
                                : persona.accentColor,
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ],

            // ── Knowledge progress bar (only for default state) ───
            if (!hasBackendData) ...[
              const SizedBox(height: Spacing.xl3),
              _KnowledgeProgress(tm: tm),
            ],
          ],
        ),
      ),
    );
  }

  /// Maps a raw trait string to an icon + display label.
  static _TraitDisplay _traitDisplay(String trait) {
    final lower = trait.toLowerCase();
    if (lower.contains('ready') || lower.contains('new')) {
      return _TraitDisplay(Icons.explore_outlined, trait);
    }
    if (lower.contains('adventure') || lower.contains('thrill')) {
      return _TraitDisplay(Icons.flash_on_rounded, trait);
    }
    if (lower.contains('luxury') || lower.contains('premium') || lower.contains('comfort')) {
      return _TraitDisplay(Icons.star_rounded, trait);
    }
    if (lower.contains('budget') || lower.contains('save')) {
      return _TraitDisplay(Icons.savings_outlined, trait);
    }
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary')) {
      return _TraitDisplay(Icons.restaurant_outlined, trait);
    }
    if (lower.contains('nature') || lower.contains('outdoor') || lower.contains('hike')) {
      return _TraitDisplay(Icons.forest_outlined, trait);
    }
    if (lower.contains('culture') || lower.contains('history') || lower.contains('museum')) {
      return _TraitDisplay(Icons.museum_outlined, trait);
    }
    if (lower.contains('slow') || lower.contains('relax')) {
      return _TraitDisplay(Icons.self_improvement, trait);
    }
    if (lower.contains('fast') || lower.contains('quick') || lower.contains('active')) {
      return _TraitDisplay(Icons.directions_run, trait);
    }
    if (lower.contains('personalized')) {
      return _TraitDisplay(Icons.auto_awesome, trait);
    }
    if (lower.contains('sport')) {
      return _TraitDisplay(Icons.sports_soccer, trait);
    }
    return _TraitDisplay(Icons.favorite_outline_rounded, trait);
  }

  // ── Persona derivation ─────────────────────────────────────────────

  /// Derive a [DerivedPersona] from the user, falling back to a generic
  /// "Globe Trotter" when [travelerPersona] has not been set yet.
  static DerivedPersona _derivePersona(UserResponse profile) {
    final backendPersona = profile.travelerPersona;

    if (backendPersona != null && backendPersona.isNotEmpty) {
      final shortName = _derivePersonaName(backendPersona);
      final personaInfo = _derivePersonaStyle(backendPersona);
      return DerivedPersona(
        name: shortName,
        description: backendPersona,
        icon: personaInfo.icon,
        accentColor: personaInfo.accentColor,
        gradient: personaInfo.gradient,
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
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary') ||
        lower.contains('local cuisine')) {
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

  /// Derive a matching icon/color/gradient based on the persona text.
  static _PersonaStyle _derivePersonaStyle(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('adventure') || lower.contains('thrill')) {
      return _PersonaStyle(
        icon: Icons.flash_on_rounded,
        accentColor: const Color(0xFFE65100),
        gradient: const LinearGradient(
          colors: [Color(0x33FF6D00), Color(0x0DFF6D00)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('luxury') || lower.contains('premium') || lower.contains('comfort')) {
      return _PersonaStyle(
        icon: Icons.star_rounded,
        accentColor: const Color(0xFF2563EB),
        gradient: const LinearGradient(
          colors: [Color(0x66DBEAFE), Color(0xFFEFF6FF)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('nature') || lower.contains('outdoor') || lower.contains('hike')) {
      return _PersonaStyle(
        icon: Icons.forest_outlined,
        accentColor: const Color(0xFF2E7D32),
        gradient: const LinearGradient(
          colors: [Color(0x33A5D6A7), Color(0x0DA5D6A7)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary')) {
      return _PersonaStyle(
        icon: Icons.restaurant_outlined,
        accentColor: const Color(0xFFC62828),
        gradient: const LinearGradient(
          colors: [Color(0x33EF9A9A), Color(0x0DEF9A9A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('culture') || lower.contains('history') || lower.contains('museum')) {
      return _PersonaStyle(
        icon: Icons.museum_outlined,
        accentColor: const Color(0xFF1565C0),
        gradient: const LinearGradient(
          colors: [Color(0x3390CAF9), Color(0x0D90CAF9)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('budget') || lower.contains('save')) {
      return _PersonaStyle(
        icon: Icons.savings_outlined,
        accentColor: const Color(0xFF6B6B6B),
        gradient: const LinearGradient(
          colors: [Color(0x339E9E9E), Color(0x0D9E9E9E)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    return _PersonaStyle(
      icon: Icons.public_rounded,
      accentColor: const Color(0xFF2563EB),
      gradient: const LinearGradient(
        colors: [Color(0x66DBEAFE), Color(0xFFEFF6FF)],
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
      ),
    );
  }

  static const _defaultPersona = DerivedPersona(
    name: 'Globe Trotter',
    description:
        'You\'re ready for your next adventure. Start chatting with TourMate '
        'and we\'ll discover your travel personality!',
    icon: Icons.public_rounded,
    accentColor: Color(0xFF2563EB),
    gradient: LinearGradient(
      colors: [Color(0x66DBEAFE), Color(0xFFEFF6FF)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    traits: ['Ready to explore', 'New adventures'],
    themeBrightness: Brightness.light,
  );
}

/// A small circular confidence gauge that shows when the persona has
/// been backed by backend data.
class _ConfidenceGauge extends StatelessWidget {
  final Color accentColor;
  final bool isDark;
  final TourMateColors tm;

  const _ConfidenceGauge({
    required this.accentColor,
    required this.isDark,
    required this.tm,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: isDark
            ? tm.pureWhite.withValues(alpha: 0.10)
            : accentColor.withValues(alpha: 0.10),
        shape: BoxShape.circle,
        border: Border.all(
          color: accentColor.withValues(alpha: 0.25),
          width: 1,
        ),
      ),
      child: Center(
        child: Text(
          '90%',
          style: GoogleFonts.inter(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            color: accentColor,
          ),
        ),
      ),
    );
  }
}

/// Knowledge progress indicator shown when no backend persona exists yet.
class _KnowledgeProgress extends StatelessWidget {
  final TourMateColors tm;

  const _KnowledgeProgress({required this.tm});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.auto_awesome, size: 12, color: tm.sapphire.withValues(alpha: 0.6)),
            const SizedBox(width: 6),
            Text(
              'Getting to know you',
              style: GoogleFonts.inter(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: tm.textTertiary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: SizedBox(
            height: 3,
            child: LinearProgressIndicator(
              value: 0.15,
              backgroundColor: tm.pureBlack.withValues(alpha: 0.06),
              valueColor: AlwaysStoppedAnimation<Color>(tm.deepRoyalBlue),
            ),
          ),
        ),
      ],
    );
  }
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

class _TraitDisplay {
  final IconData icon;
  final String label;

  const _TraitDisplay(this.icon, this.label);
}

class _PersonaStyle {
  final IconData icon;
  final Color accentColor;
  final LinearGradient gradient;

  const _PersonaStyle({
    required this.icon,
    required this.accentColor,
    required this.gradient,
  });
}
