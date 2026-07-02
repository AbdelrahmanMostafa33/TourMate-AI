import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';

/// A row of premium suggestion chips that let users quickly start a
/// conversation with TourMate by tapping a pre-written prompt.
///
/// Each chip shows an icon + label in a sapphire-accented container.
/// Chips stagger-in with a subtle fade + slide-up animation on first render.
/// Place below the welcome message in the empty state.
class SuggestionChips extends StatefulWidget {
  final void Function(String message) onChipTapped;

  const SuggestionChips({super.key, required this.onChipTapped});

  @override
  State<SuggestionChips> createState() => _SuggestionChipsState();
}

class _SuggestionChipsState extends State<SuggestionChips>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  static const _suggestions = [
    _ChipData(Icons.flight_takeoff_outlined, 'Plan a 3-day Cairo itinerary'),
    _ChipData(Icons.explore_outlined, 'Top historical sites in Luxor'),
    _ChipData(Icons.restaurant_outlined, 'Best local food in Alexandria'),
    _ChipData(Icons.directions_boat_outlined, 'Aswan & Abu Simbel day trip'),
    _ChipData(Icons.map_outlined, 'Cairo, Luxor & Aswan multi-city trip'),
    _ChipData(Icons.shopping_bag_outlined, 'Khan El Khalili & local markets'),
  ];

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        children: [
          // Animated section label
          FadeTransition(
            opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
              CurvedAnimation(
                parent: _controller,
                curve: const Interval(0.0, 0.25, curve: Curves.easeOut),
              ),
            ),
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.3),
                end: Offset.zero,
              ).animate(
                CurvedAnimation(
                  parent: _controller,
                  curve: const Interval(0.0, 0.25, curve: Curves.easeOutCubic),
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.only(bottom: Spacing.xl3),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.auto_awesome,
                      size: 14,
                      color: tm.sapphire.withValues(alpha: 0.6),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'GET STARTED',
                      style: GoogleFonts.inter(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 1.5,
                        color: tm.textTertiary,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          // Animated chips with staggered entrance
          Wrap(
            spacing: Spacing.sm,
            runSpacing: Spacing.sm,
            alignment: WrapAlignment.center,
            children: List.generate(_suggestions.length, (i) {
              final chip = _suggestions[i];
              // Stagger each chip: 0.1 → 0.35, 0.2 → 0.45, 0.3 → 0.55, 0.4 → 0.65
              final start = 0.1 + i * 0.1;
              final end = start + 0.25;
              return FadeTransition(
                opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
                  CurvedAnimation(
                    parent: _controller,
                    curve: Interval(start, end, curve: Curves.easeOut),
                  ),
                ),
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.25),
                    end: Offset.zero,
                  ).animate(
                    CurvedAnimation(
                      parent: _controller,
                      curve: Interval(start, end, curve: Curves.easeOutCubic),
                    ),
                  ),
                  child: _SuggestionChip(
                    icon: chip.icon,
                    label: chip.label,
                    onTap: () => widget.onChipTapped(chip.label),
                    tm: tm,
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

/// Individual sapphire-accented suggestion chip with icon.
class _SuggestionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final TourMateColors tm;

  const _SuggestionChip({
    required this.icon,
    required this.label,
    required this.onTap,
    required this.tm,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(RadiusTokens.full),
        onTap: onTap,
        splashColor: tm.sapphire.withValues(alpha: 0.08),
        highlightColor: tm.sapphire.withValues(alpha: 0.05),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            color: tm.pureWhite,
            borderRadius: BorderRadius.circular(RadiusTokens.full),
            border: Border.all(
              color: tm.sapphire.withValues(alpha: 0.25),
              width: 0.5,
            ),
            boxShadow: [
              BoxShadow(
                color: tm.sapphire.withValues(alpha: 0.06),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 14, color: tm.sapphire),
              const SizedBox(width: 6),
              Text(
                label,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: tm.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Internal data for a suggestion chip.
class _ChipData {
  final IconData icon;
  final String label;
  const _ChipData(this.icon, this.label);
}
