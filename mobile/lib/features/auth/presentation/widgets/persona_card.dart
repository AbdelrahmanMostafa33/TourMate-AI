import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/user_response.dart';

/// A redesigned, premium traveler persona card with modern layout and
/// visual style — dark gradient header, large icon, trait chips, and
/// a subtle stats section.
class PersonaCard extends StatelessWidget {
  final UserResponse profile;

  const PersonaCard({super.key, required this.profile});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final persona = _derivePersona(profile);
    final hasBackendData =
        profile.travelerPersona != null && profile.travelerPersona!.isNotEmpty;

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: tm.pureWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.pureBlack.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
          BoxShadow(
            color: persona.accentColor.withValues(alpha: 0.08),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        children: [
          // ── Top gradient header ───────────────────────────────────────
          _HeaderSection(persona: persona, tm: tm),

          // ── Body ──────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Persona title
                Text(
                  persona.name,
                  style: GoogleFonts.inter(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: tm.textPrimary,
                    letterSpacing: -0.4,
                    height: 1.1,
                  ),
                ),

                // Accent underline
                const SizedBox(height: 8),
                Container(
                  width: 32,
                  height: 3,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        persona.accentColor,
                        persona.accentColor.withValues(alpha: 0.4),
                      ],
                    ),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),

                // Description
                const SizedBox(height: 14),
                Text(
                  persona.description,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    height: 1.55,
                    color: tm.textSecondary.withValues(alpha: 0.85),
                  ),
                ),

                // ── Trait chips ──────────────────────────────────────────
                if (persona.traits.isNotEmpty) ...[
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: persona.traits.map((trait) {
                      final traitInfo = _traitDisplay(trait);
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              persona.accentColor.withValues(alpha: 0.1),
                              persona.accentColor.withValues(alpha: 0.04),
                            ],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius:
                              BorderRadius.circular(RadiusTokens.full),
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
                              size: 13,
                              color: persona.accentColor,
                            ),
                            const SizedBox(width: 5),
                            Text(
                              traitInfo.label,
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: persona.accentColor,
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 4),

          // ── Bottom stats bar ──────────────────────────────────────────
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 16),
            decoration: BoxDecoration(
              color: tm.surface.withValues(alpha: 0.5),
              border: Border(
                top: BorderSide(color: tm.borderLight.withValues(alpha: 0.5)),
              ),
            ),
            child: hasBackendData
                ? _DataStatsRow(tm: tm, persona: persona)
                : _DefaultStatsRow(tm: tm, persona: persona),
          ),
        ],
      ),
    );
  }

  // ── Trait display mapping ───────────────────────────────────────────

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
        traits: _extractTraits(backendPersona),
        themeBrightness: Brightness.light,
      );
    }

    return _defaultPersona;
  }

  /// Extract meaningful traits from the persona description.
  static List<String> _extractTraits(String text) {
    final lower = text.toLowerCase();
    final traits = <String>[];

    if (lower.contains('adventure') || lower.contains('thrill')) {
      traits.add('Adventure');
    }
    if (lower.contains('luxury') || lower.contains('premium') || lower.contains('comfort')) {
      traits.add('Luxury');
    }
    if (lower.contains('budget') || lower.contains('save')) {
      traits.add('Budget-conscious');
    }
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary')) {
      traits.add('Foodie');
    }
    if (lower.contains('nature') || lower.contains('outdoor') || lower.contains('hike')) {
      traits.add('Nature');
    }
    if (lower.contains('culture') || lower.contains('history') || lower.contains('museum')) {
      traits.add('Culture');
    }
    if (lower.contains('slow') || lower.contains('relax')) {
      traits.add('Slow-paced');
    }
    if (lower.contains('fast') || lower.contains('quick')) {
      traits.add('Fast-paced');
    }
    if (lower.contains('sport') || lower.contains('active')) {
      traits.add('Active');
    }
    if (lower.contains('personalized')) {
      traits.add('Personalized');
    }

    if (traits.isEmpty) {
      traits.add('Personalized');
    }

    return traits;
  }

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

  static _PersonaStyle _derivePersonaStyle(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('adventure') || lower.contains('thrill')) {
      return _PersonaStyle(
        icon: Icons.flash_on_rounded,
        accentColor: const Color(0xFF3B82F6),
        gradient: const LinearGradient(
          colors: [Color(0x1A3B82F6), Color(0x003B82F6)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('luxury') || lower.contains('premium') || lower.contains('comfort')) {
      return _PersonaStyle(
        icon: Icons.star_rounded,
        accentColor: const Color(0xFF1E3A8A),
        gradient: const LinearGradient(
          colors: [Color(0x1A1E3A8A), Color(0x001E3A8A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('nature') || lower.contains('outdoor') || lower.contains('hike')) {
      return _PersonaStyle(
        icon: Icons.forest_outlined,
        accentColor: const Color(0xFF60A5FA),
        gradient: const LinearGradient(
          colors: [Color(0x1A60A5FA), Color(0x0060A5FA)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('food') || lower.contains('cuisine') || lower.contains('culinary')) {
      return _PersonaStyle(
        icon: Icons.restaurant_outlined,
        accentColor: const Color(0xFF2563EB),
        gradient: const LinearGradient(
          colors: [Color(0x1A2563EB), Color(0x002563EB)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('culture') || lower.contains('history') || lower.contains('museum')) {
      return _PersonaStyle(
        icon: Icons.museum_outlined,
        accentColor: const Color(0xFF1D4ED8),
        gradient: const LinearGradient(
          colors: [Color(0x1A1D4ED8), Color(0x001D4ED8)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    if (lower.contains('budget') || lower.contains('save')) {
      return _PersonaStyle(
        icon: Icons.savings_outlined,
        accentColor: const Color(0xFF64748B),
        gradient: const LinearGradient(
          colors: [Color(0x1A64748B), Color(0x0064748B)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      );
    }
    return _PersonaStyle(
      icon: Icons.public_rounded,
      accentColor: const Color(0xFF2563EB),
      gradient: const LinearGradient(
        colors: [Color(0x1A2563EB), Color(0x002563EB)],
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
      colors: [Color(0x1A2563EB), Color(0x002563EB)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    ),
    traits: ['Ready to explore', 'New adventures'],
    themeBrightness: Brightness.light,
  );
}

// ── Header section ────────────────────────────────────────────────────

class _HeaderSection extends StatelessWidget {
  final DerivedPersona persona;
  final TourMateColors tm;

  const _HeaderSection({
    required this.persona,
    required this.tm,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            tm.surfaceDark,
            tm.deepRoyalBlue.withValues(alpha: 0.85),
            persona.accentColor.withValues(alpha: 0.7),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Row(
        children: [
          // Large persona icon in a glowing circle
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [
                  tm.pureWhite.withValues(alpha: 0.25),
                  tm.pureWhite.withValues(alpha: 0.08),
                ],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              border: Border.all(
                color: tm.pureWhite.withValues(alpha: 0.25),
                width: 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: tm.pureWhite.withValues(alpha: 0.1),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Icon(
              persona.icon,
              size: 28,
              color: tm.pureWhite,
            ),
          ),
          const SizedBox(width: 16),
          // Label + confidence
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'TRAVELER PERSONA',
                  style: GoogleFonts.inter(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.8,
                    color: tm.pureWhite.withValues(alpha: 0.6),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  persona.name,
                  style: GoogleFonts.inter(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: tm.pureWhite,
                    letterSpacing: -0.3,
                    height: 1.1,
                  ),
                ),
              ],
            ),
          ),

        ],
      ),
    );
  }
}

// ── Stats row for backend data ────────────────────────────────────────

class _DataStatsRow extends StatelessWidget {
  final TourMateColors tm;
  final DerivedPersona persona;

  const _DataStatsRow({required this.tm, required this.persona});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _StatItem(
          icon: Icons.travel_explore_rounded,
          label: 'Learned from',
          value: 'your trips',
          accentColor: persona.accentColor,
          tm: tm,
        ),
        const SizedBox(width: 24),
        _StatItem(
          icon: Icons.auto_awesome_rounded,
          label: 'Confidence',
          value: 'High',
          accentColor: persona.accentColor,
          tm: tm,
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: persona.accentColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(RadiusTokens.full),
            border: Border.all(
              color: persona.accentColor.withValues(alpha: 0.15),
              width: 0.5,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.check_circle_rounded,
                size: 12,
                color: persona.accentColor,
              ),
              const SizedBox(width: 4),
              Text(
                'Verified',
                style: GoogleFonts.inter(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: persona.accentColor,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// ── Stats row for default (no backend data) ───────────────────────────

class _DefaultStatsRow extends StatelessWidget {
  final TourMateColors tm;
  final DerivedPersona persona;

  const _DefaultStatsRow({required this.tm, required this.persona});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          Icons.auto_awesome_rounded,
          size: 14,
          color: persona.accentColor.withValues(alpha: 0.6),
        ),
        const SizedBox(width: 8),
        Text(
          'Getting to know you',
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: tm.textTertiary,
          ),
        ),
        const Spacer(),
        SizedBox(
          width: 80,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: 0.15,
              minHeight: 4,
              backgroundColor: tm.pureBlack.withValues(alpha: 0.06),
              valueColor: AlwaysStoppedAnimation<Color>(persona.accentColor),
            ),
          ),
        ),
      ],
    );
  }
}

// ── Individual stat item ─────────────────────────────────────────────

class _StatItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final Color accentColor;
  final TourMateColors tm;

  const _StatItem({
    required this.icon,
    required this.label,
    required this.value,
    required this.accentColor,
    required this.tm,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          icon,
          size: 14,
          color: accentColor.withValues(alpha: 0.6),
        ),
        const SizedBox(width: 6),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 9,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
                color: tm.textTertiary,
              ),
            ),
            Text(
              value,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: tm.textSecondary,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ── Data classes ─────────────────────────────────────────────────────

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
