import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/expandable_recommendation.dart';
import '../../data/models/itinerary_data.dart';

class ItineraryCard extends StatelessWidget {
  final ItineraryData itinerary;
  final VoidCallback? onApprove;

  const ItineraryCard({
    super.key,
    required this.itinerary,
    this.onApprove,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.deepNavy.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Premium Header ──────────────────────────────
          _buildHeader(tm),
          Container(height: 1, color: tm.divider),

          // ── Days ────────────────────────────────────────
          ...itinerary.days.map((day) => _DaySection(day: day)),

          // ── Premium Approve Button ──────────────────────
          if (onApprove != null) ...[
            Container(height: 1, color: tm.divider),
            _ApproveButton(onApprove: onApprove!),
          ],
        ],
      ),
    );
  }

  Widget _buildHeader(TourMateColors tm) {
    return Container(
      padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl4, Spacing.xl4, Spacing.xl3),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(Spacing.md),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(RadiusTokens.xl),
              border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
            ),
            child: Icon(Icons.map_rounded, color: tm.sapphireLight, size: 20),
          ),
          const SizedBox(width: Spacing.xl2),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  itinerary.destination,
                  style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
                ),
                const SizedBox(height: Spacing.xxs),
                Text(
                  '${itinerary.days.length} day${itinerary.days.length > 1 ? 's' : ''} • ${itinerary.totalStops} stop${itinerary.totalStops > 1 ? 's' : ''}',
                  style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.lg, vertical: Spacing.sm),
            decoration: BoxDecoration(
              color: tm.sapphire.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(RadiusTokens.xl4),
              border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.auto_awesome, size: 12, color: tm.sapphire),
                const SizedBox(width: Spacing.xs),
                Text(
                  'AI Planned',
                  style: GoogleFonts.inter(fontSize: 11, color: tm.sapphire, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Day Section ─────────────────────────────────────────────────────────────

class _DaySection extends StatelessWidget {
  final ItineraryDay day;

  const _DaySection({required this.day});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: Spacing.xl3),

          // sapphire-accented day header
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(RadiusTokens.lg),
                  border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${day.dayNumber}',
                  style: GoogleFonts.inter(color: tm.sapphireLight, fontSize: 14, fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: Spacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Day ${day.dayNumber}',
                      style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w700, color: tm.textPrimary),
                    ),
                    if (day.theme.isNotEmpty)
                      Text(
                        day.theme,
                        style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary, fontWeight: FontWeight.w500),
                      ),
                  ],
                ),
              ),
              if (day.totalTravelTimeMinutes != null && day.totalTravelTimeMinutes! > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.md, vertical: Spacing.xxs),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(RadiusTokens.xl),
                    border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.access_time, size: 11, color: tm.sapphire),
                      const SizedBox(width: Spacing.xxs),
                      Text(
                        '${day.totalTravelTimeMinutes!.toInt()} min',
                        style: GoogleFonts.inter(fontSize: 11, color: tm.sapphire, fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                ),
            ],
          ),

          const SizedBox(height: Spacing.md),

          // Premium stops timeline
          ...List.generate(day.stops.length, (i) {
            final stop = day.stops[i];
            final isLast = i == day.stops.length - 1;
            return _StopTimelineItem(
              stop: stop,
              isLast: isLast,
              showTravel: !isLast &&
                  stop.travelTimeToNextMinutes != null &&
                  stop.travelTimeToNextMinutes! > 0,
            );
          }),

          const SizedBox(height: Spacing.xl3),
        ],
      ),
    );
  }

}

// ── Stop Timeline Item ──────────────────────────────────────────────────────

class _StopTimelineItem extends StatelessWidget {
  final ItineraryStop stop;
  final bool isLast;
  final bool showTravel;

  const _StopTimelineItem({
    required this.stop,
    required this.isLast,
    required this.showTravel,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final timeColor = _timeColor(stop.suggestedTimeOfDay);
    final timeLabel = _timeLabel(stop.suggestedTimeOfDay);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── timeline column ────────────────────
          SizedBox(
            width: 28,
            child: Column(
              children: [
                const SizedBox(height: Spacing.xs),
                // sapphire-accented dot
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [timeColor, timeColor.withValues(alpha: 0.8)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    shape: BoxShape.circle,
                    border: Border.all(color: tm.brandWhite, width: 2),
                    boxShadow: [
                      BoxShadow(
                        color: timeColor.withValues(alpha: 0.3),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                ),
                // Gold connecting line
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 1.5,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [tm.sapphire.withValues(alpha: 0.4), tm.sapphire.withValues(alpha: 0.1)],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // ── Premium stop content ─────────────────────
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : Spacing.md),
              child: GestureDetector(
                onTap: () {
                  if (stop.id.isNotEmpty) {
                    Navigator.of(context).pushNamed(
                      '/place-detail',
                      arguments: stop.id,
                    );
                  }
                },
                child: Container(
                  margin: const EdgeInsets.only(left: Spacing.md, bottom: Spacing.xs),
                  padding: const EdgeInsets.all(Spacing.md),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                    border: Border.all(color: tm.borderLight),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Name + time badge
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              stop.name,
                              style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, color: tm.textPrimary),
                            ),
                          ),
                          if (timeLabel.isNotEmpty)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: Spacing.sm, vertical: Spacing.xxs),
                              decoration: BoxDecoration(
                                color: timeColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(RadiusTokens.md),
                                border: Border.all(color: timeColor.withValues(alpha: 0.2)),
                              ),
                              child: Text(
                                timeLabel,
                                style: GoogleFonts.inter(fontSize: 10, color: timeColor, fontWeight: FontWeight.w600),
                              ),
                            ),
                        ],
                      ),

                      const SizedBox(height: Spacing.sm),

                      // Gold metadata chips
                      Wrap(
                        spacing: Spacing.sm,
                        runSpacing: Spacing.xs,
                        children: [
                          if (stop.estimatedDurationMinutes > 0)
                            _accentChip(
                              '${stop.estimatedDurationMinutes} min',
                              Icons.timer_outlined,
                              tm.sapphire,
                            ),
                          if (stop.category.isNotEmpty)
                            _accentChip(
                              stop.category,
                              Icons.category_outlined,
                              tm.sapphire,
                            ),
                          if (stop.rating != null)
                            _accentChip(
                              stop.rating!.toStringAsFixed(1),
                              Icons.star_rounded,
                              tm.sapphire,
                            ),
                        ],
                      ),

                      // Why recommended — with lightbulb icon, styled container, and expandable text
                      if (stop.whyRecommended.isNotEmpty) ...[
                        const SizedBox(height: Spacing.sm),
                        ExpandableRecommendation(
                          text: stop.whyRecommended,
                          maxLinesCollapsed: 3,
                        ),
                      ],

                      // Address
                      if (stop.address != null && stop.address!.isNotEmpty) ...[
                        const SizedBox(height: Spacing.xs),
                        Row(
                          children: [
                            Icon(Icons.location_on_outlined, size: 12, color: tm.sapphireLight),
                            const SizedBox(width: Spacing.xxs),
                            Expanded(
                              child: Text(
                                stop.address!,
                                style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _accentChip(String label, IconData icon, Color accent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.md, vertical: Spacing.xxs),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(RadiusTokens.md),
        border: Border.all(color: accent.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: accent),
          const SizedBox(width: Spacing.xs),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 10, color: accent, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  Color _timeColor(String tod) {
    switch (tod.toLowerCase()) {
      case 'morning':
        return const Color(0xFF3B82F6);
      case 'afternoon':
        return const Color(0xFF2563EB);
      case 'evening':
        return const Color(0xFF1D4ED8);
      default:
        return const Color(0xFF2563EB);
    }
  }

  String _timeLabel(String tod) {
    switch (tod.toLowerCase()) {
      case 'morning':
        return 'AM';
      case 'afternoon':
        return 'PM';
      case 'evening':
        return 'Eve';
      default:
        return '';
    }
  }
}

// ── Premium Approve Button ───────────────────────────────────────────────────

class _ApproveButton extends StatelessWidget {
  final VoidCallback onApprove;

  const _ApproveButton({required this.onApprove});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, Spacing.xl4),
      child: SizedBox(
        width: double.infinity,
        child: ElevatedButton.icon(
          onPressed: onApprove,
          icon: Icon(Icons.check_circle_rounded, size: 20, color: tm.sapphireLight),
          label: Text(
            'Approve Itinerary',
            style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          style: ElevatedButton.styleFrom(
            backgroundColor: tm.deepNavy,
            foregroundColor: tm.brandWhite,
            padding: const EdgeInsets.symmetric(vertical: Spacing.xl3),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
            ),
            elevation: 0,
          ),
        ),
      ),
    );
  }
}

// ── Helper extension ─────────────────────────────────────────────────────────

extension ItineraryDataStats on ItineraryData {
  int get totalStops {
    return days.fold(0, (sum, day) => sum + day.stops.length);
  }
}
