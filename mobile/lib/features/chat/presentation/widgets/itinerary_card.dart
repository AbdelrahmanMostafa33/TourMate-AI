import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
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
        color: tm.pureWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.pureBlack.withValues(alpha: 0.06),
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
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0A0A0A), Color(0xFF1A1A1A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
            ),
            child: Icon(Icons.map_rounded, color: tm.goldLight, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  itinerary.destination,
                  style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
                ),
                const SizedBox(height: 2),
                Text(
                  '${itinerary.days.length} day${itinerary.days.length > 1 ? 's' : ''} • ${itinerary.totalStops} stop${itinerary.totalStops > 1 ? 's' : ''}',
                  style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: tm.gold.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: tm.gold.withValues(alpha: 0.2)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.auto_awesome, size: 12, color: tm.gold),
                const SizedBox(width: 4),
                Text(
                  'AI Planned',
                  style: GoogleFonts.inter(fontSize: 11, color: tm.gold, fontWeight: FontWeight.w600),
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

          // Gold-accented day header
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0A0A0A), Color(0xFF1A1A1A)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${day.dayNumber}',
                  style: GoogleFonts.inter(color: tm.goldLight, fontSize: 14, fontWeight: FontWeight.w800),
                ),
              ),
              const SizedBox(width: 10),
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
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: tm.gold.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: tm.gold.withValues(alpha: 0.2)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.access_time, size: 11, color: tm.gold),
                      const SizedBox(width: 3),
                      Text(
                        '${day.totalTravelTimeMinutes!.toInt()} min',
                        style: GoogleFonts.inter(fontSize: 11, color: tm.gold, fontWeight: FontWeight.w600),
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
          // ── Gold timeline column ────────────────────
          SizedBox(
            width: 28,
            child: Column(
              children: [
                const SizedBox(height: 4),
                // Gold-accented dot
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
                    border: Border.all(color: tm.pureWhite, width: 2),
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
                          colors: [tm.gold.withValues(alpha: 0.4), tm.gold.withValues(alpha: 0.1)],
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
              padding: EdgeInsets.only(bottom: isLast ? 0 : 8),
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
                  margin: const EdgeInsets.only(left: 8, bottom: 4),
                  padding: const EdgeInsets.all(Spacing.md),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                    border: Border.all(color: tm.borderLight),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Name + gold time badge
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
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: timeColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: timeColor.withValues(alpha: 0.2)),
                              ),
                              child: Text(
                                timeLabel,
                                style: GoogleFonts.inter(fontSize: 10, color: timeColor, fontWeight: FontWeight.w600),
                              ),
                            ),
                        ],
                      ),

                      const SizedBox(height: 6),

                      // Gold metadata chips
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          if (stop.estimatedDurationMinutes > 0)
                            _goldChip(
                              '${stop.estimatedDurationMinutes} min',
                              Icons.timer_outlined,
                              tm.gold,
                            ),
                          if (stop.category.isNotEmpty)
                            _goldChip(
                              stop.category,
                              Icons.category_outlined,
                              tm.gold,
                            ),
                          if (stop.rating != null)
                            _goldChip(
                              stop.rating!.toStringAsFixed(1),
                              Icons.star_rounded,
                              tm.gold,
                            ),
                        ],
                      ),

                      // Why recommended
                      if (stop.whyRecommended.isNotEmpty) ...[
                        const SizedBox(height: Spacing.sm),
                        Text(
                          stop.whyRecommended,
                          style: GoogleFonts.inter(fontSize: 12, color: tm.textSecondary, height: 1.4),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],

                      // Address
                      if (stop.address != null && stop.address!.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(Icons.location_on_outlined, size: 12, color: tm.goldLight),
                            const SizedBox(width: 3),
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

  Widget _goldChip(String label, IconData icon, Color accent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accent.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: accent),
          const SizedBox(width: 4),
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
        return const Color(0xFFD4A853);
      case 'afternoon':
        return const Color(0xFFB8860B);
      case 'evening':
        return const Color(0xFF8B7355);
      default:
        return const Color(0xFFC8A84E);
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
          icon: Icon(Icons.check_circle_rounded, size: 20, color: tm.goldLight),
          label: Text(
            'Approve Itinerary',
            style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700),
          ),
          style: ElevatedButton.styleFrom(
            backgroundColor: tm.pureBlack,
            foregroundColor: tm.pureWhite,
            padding: const EdgeInsets.symmetric(vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              side: BorderSide(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
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
