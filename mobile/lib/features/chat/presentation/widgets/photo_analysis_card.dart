import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/photo_analysis_data.dart';

/// ═══════════════════════════════════════════════════════════════════════════
/// PHOTO ANALYSIS CARD — Progressive Reveal
/// ═══════════════════════════════════════════════════════════════════════════
///
/// Shows a compact "Analyzing photo..." shimmer card first, then progressively
/// reveals each section (header → intro → interests → environment → vibe →
/// action buttons) with staggered slide-up + fade-in animations.  The total
/// reveal takes ~2.3 s so the user sees the AI "thinking" live.
///
/// Animation timeline (all driven by a single AnimationController):
///
///   0 – 200 ms    Card entry fade-in & slide-up
///   0 – 700 ms    "Analyzing photo…" shimmer placeholder
/// 700 – 900 ms    Shimmer cross-fades to content
/// 800 – 1050 ms   Header
/// 1050 – 1300 ms  Intro text
/// 1300 – 1550 ms  Interests chips  (if present)
/// 1550 – 1800 ms  Environment + Food (if present)
/// 1800 – 2100 ms  Vibe               (if present)
/// 2100 – 2300 ms  Divider + Description + Action buttons
///
/// ═══════════════════════════════════════════════════════════════════════════

class PhotoAnalysisCard extends StatefulWidget {
  final PhotoAnalysisData data;
  final VoidCallback? onPlanTrip;
  final VoidCallback? onModifyPreferences;
  final VoidCallback? onStartFresh;

  const PhotoAnalysisCard({
    super.key,
    required this.data,
    this.onPlanTrip,
    this.onModifyPreferences,
    this.onStartFresh,
  });

  @override
  State<PhotoAnalysisCard> createState() => _PhotoAnalysisCardState();
}

class _PhotoAnalysisCardState extends State<PhotoAnalysisCard>
    with SingleTickerProviderStateMixin {
  /// ── Animation ─────────────────────────────────────────────────────────────
  // Single controller drives the entire progressive reveal.
  static const _totalDuration = Duration(milliseconds: 2400);
  late final AnimationController _ctrl;

  // Pre-computed intervals for each phase.
  static const _cardInterval = Interval(0.00, 0.10, curve: Curves.easeOutCubic);
  static const _shimmerInterval = Interval(0.00, 0.30, curve: Curves.easeOut);
  static const _headerInterval = Interval(0.32, 0.44, curve: Curves.easeOutCubic);
  static const _introInterval = Interval(0.44, 0.54, curve: Curves.easeOutCubic);
  static const _interestsInterval = Interval(0.54, 0.65, curve: Curves.easeOutCubic);
  static const _envInterval = Interval(0.65, 0.75, curve: Curves.easeOutCubic);
  static const _vibeInterval = Interval(0.75, 0.88, curve: Curves.easeOutCubic);
  static const _actionsInterval = Interval(0.88, 1.00, curve: Curves.easeOutCubic);

  // Animations
  late final Animation<double> _cardFade;
  late final Animation<double> _shimmerFade;
  late final Animation<double> _headerFade;
  late final Animation<Offset> _headerSlide;
  late final Animation<double> _introFade;
  late final Animation<Offset> _introSlide;
  late final Animation<double> _interestsFade;
  late final Animation<Offset> _interestsSlide;
  late final Animation<double> _envFade;
  late final Animation<Offset> _envSlide;
  late final Animation<double> _vibeFade;
  late final Animation<Offset> _vibeSlide;
  late final Animation<double> _actionsFade;
  late final Animation<Offset> _actionsSlide;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: _totalDuration);

    _cardFade = _ctrl.drive(CurveTween(curve: _cardInterval));

    _shimmerFade = _ctrl.drive(CurveTween(curve: _shimmerInterval));

    _headerFade = _ctrl.drive(CurveTween(curve: _headerInterval));
    _headerSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _headerInterval)),
    );

    _introFade = _ctrl.drive(CurveTween(curve: _introInterval));
    _introSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _introInterval)),
    );

    _interestsFade = _ctrl.drive(CurveTween(curve: _interestsInterval));
    _interestsSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _interestsInterval)),
    );

    _envFade = _ctrl.drive(CurveTween(curve: _envInterval));
    _envSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _envInterval)),
    );

    _vibeFade = _ctrl.drive(CurveTween(curve: _vibeInterval));
    _vibeSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _vibeInterval)),
    );

    _actionsFade = _ctrl.drive(CurveTween(curve: _actionsInterval));
    _actionsSlide = _ctrl.drive(
      Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .chain(CurveTween(curve: _actionsInterval)),
    );

    _ctrl.forward();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  /// Build a fade + slide wrapper driven by [fade] and [slide] animations.
  Widget _staggered({
    required Animation<double> fade,
    required Animation<Offset> slide,
    required Widget child,
  }) =>
      SlideTransition(
        position: slide,
        child: FadeTransition(opacity: fade, child: child),
      );

  // ── Emoji maps ──────────────────────────────────────────────────────────

  static const _interestEmoji = <String, String>{
    'history': '🏛️',
    'food': '🍽️',
    'museums': '🎭',
    'shopping': '🛍️',
    'nightlife': '🌃',
    'hiking': '🥾',
    'beach': '🏖️',
    'nature': '🌿',
    'adventure': '🏔️',
    'photography': '📸',
    'architecture': '🏗️',
    'culture': '🎭',
    'art': '🎨',
    'music': '🎵',
    'wellness': '🧘',
    'wildlife': '🦁',
    'desert': '🏜️',
    'water sports': '🏄',
    'urban exploration': '🏙️',
    'pop culture': '🎭',
    'local markets': '🛒',
    'temples': '🛕',
    'ruins': '🏚️',
    'cafes': '☕',
    'sightseeing': '🔭',
    'relaxation': '😌',
    'photography spots': '📷',
    'scenic views': '🌄',
    'gardens': '🌺',
    'cruises': '🚢',
    'wine tasting': '🍷',
    'street food': '🌮',
  };

  static const _envEmoji = <String, String>{
    'urban': '🏙️',
    'nature': '🌿',
    'beach': '🏖️',
    'desert': '🏜️',
    'mountain': '🏔️',
    'mixed': '🌍',
    'coastal': '🌊',
    'rural': '🌾',
    'tropical': '🌴',
    'historical': '🏛️',
  };

  String _interestIcon(String interest) {
    final lower = interest.toLowerCase();
    if (_interestEmoji.containsKey(lower)) return _interestEmoji[lower]!;
    for (final entry in _interestEmoji.entries) {
      if (lower.contains(entry.key) || entry.key.contains(lower)) {
        return entry.value;
      }
    }
    return '✨';
  }

  String _envIcon(String env) {
    final lower = env.toLowerCase();
    for (final entry in _envEmoji.entries) {
      if (lower.contains(entry.key) || entry.key.contains(lower)) {
        return entry.value;
      }
    }
    return '🌍';
  }

  // ── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final data = widget.data;

    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        // ── Card entry ────────────────────────────────────────────────
        return Opacity(
          opacity: _cardFade.value,
          child: Transform.translate(
            offset: Offset(0, 8 * (1 - _cardFade.value)),
            child: Container(
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
              child: ClipRRect(
                borderRadius: BorderRadius.circular(RadiusTokens.xl4 - 1),
                child: Stack(
                  children: [
                    // ── Content (hidden during shimmer phase, fades in) ─
                    Opacity(
                      opacity: _shimmerFade.value,
                      child: _buildContent(tm, data),
                    ),
                    // ── Shimmer overlay (visible initially, fades out) ───
                    Opacity(
                      opacity: 1 - _shimmerFade.value,
                      child: _buildShimmer(tm),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  /// The full analysis card — each section is wrapped in a staggered
  /// animated reveal.
  Widget _buildContent(TourMateColors tm, PhotoAnalysisData data) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Header ────────────────────────────────────────────────────
        _staggered(
          fade: _headerFade,
          slide: _headerSlide,
          child: _buildHeader(tm),
        ),
        _staggered(
          fade: _headerFade,
          slide: _headerSlide,
          child: Container(height: 1, color: tm.divider),
        ),

        // ── Intro text ────────────────────────────────────────────────
        _staggered(
          fade: _introFade,
          slide: _introSlide,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, 0),
            child: Text(
              'Based on your photo, I found these travel preferences:',
              style: GoogleFonts.inter(
                fontSize: 14,
                color: tm.textSecondary,
                height: 1.5,
              ),
            ),
          ),
        ),

        if (data.interests.isNotEmpty) ...[
          const SizedBox(height: Spacing.xl2),
          _staggered(
            fade: _interestsFade,
            slide: _interestsSlide,
            child: _buildInterestsSection(tm, data),
          ),
        ],

        if (data.foodPreferences.isNotEmpty)
          _staggered(
            fade: _envFade,
            slide: _envSlide,
            child: _buildFoodSection(tm, data),
          ),

        if (data.environmentType != null && data.environmentType!.isNotEmpty)
          _staggered(
            fade: _envFade,
            slide: _envSlide,
            child: _buildEnvironmentSection(tm, data),
          ),

        if (data.vibe != null && data.vibe!.isNotEmpty)
          _staggered(
            fade: _vibeFade,
            slide: _vibeSlide,
            child: _buildVibeSection(tm, data),
          ),

        // ── Divider ───────────────────────────────────────────────────
        _staggered(
          fade: _actionsFade,
          slide: _actionsSlide,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
            child: Container(height: 1, color: tm.divider),
          ),
        ),

        // ── Description ───────────────────────────────────────────────
        _staggered(
          fade: _actionsFade,
          slide: _actionsSlide,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, 0),
            child: Text(
              'I can personalize your itinerary using these insights.',
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textTertiary,
                height: 1.5,
              ),
            ),
          ),
        ),

        // ── Action Buttons ────────────────────────────────────────────
        _staggered(
          fade: _actionsFade,
          slide: _actionsSlide,
          child: _buildActionButtons(tm),
        ),
      ],
    );
  }

  // ── Shimmer "Analyzing photo…" placeholder ───────────────────────────────

  Widget _buildShimmer(TourMateColors tm) {
    return Container(
      padding: const EdgeInsets.all(Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Shimmer header row
          Row(
            children: [
              _ShimmerBox(width: 40, height: 40, borderRadius: RadiusTokens.xl, tm: tm),
              const SizedBox(width: Spacing.xl2),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _ShimmerBox(width: 160, height: 18, borderRadius: RadiusTokens.sm, tm: tm),
                    const SizedBox(height: Spacing.sm),
                    _ShimmerBox(width: 120, height: 12, borderRadius: RadiusTokens.sm, tm: tm),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: Spacing.xl6),
          // Animated "Analyzing…" row
          Row(
            children: [
              _PulsingDot(tm: tm),
              const SizedBox(width: Spacing.xl2),
              Text(
                'Analyzing your photo',
                style: GoogleFonts.inter(
                  fontSize: 15,
                  fontWeight: FontWeight.w500,
                  color: tm.textSecondary,
                ),
              ),
              const SizedBox(width: Spacing.sm),
              _AnimatedEllipsis(tm: tm),
            ],
          ),
          const SizedBox(height: Spacing.xl5),
          // Shimmer content placeholders
          _ShimmerBox(width: 80, height: 12, borderRadius: RadiusTokens.sm, tm: tm),
          const SizedBox(height: Spacing.xl2),
          Wrap(
            spacing: Spacing.sm,
            runSpacing: Spacing.sm,
            children: List.generate(4, (i) => _ShimmerBox(
              width: 80 + (i % 2) * 40,
              height: 30,
              borderRadius: RadiusTokens.xl3,
              tm: tm,
            )),
          ),
          const SizedBox(height: Spacing.xl5),
          _ShimmerBox(width: 100, height: 12, borderRadius: RadiusTokens.sm, tm: tm),
          const SizedBox(height: Spacing.md),
          _ShimmerBox(width: double.infinity, height: 38, borderRadius: RadiusTokens.md, tm: tm),
          const SizedBox(height: Spacing.xl4),
          _ShimmerBox(width: double.infinity, height: 44, borderRadius: RadiusTokens.xl3, tm: tm),
        ],
      ),
    );
  }

  // ── Section builders ─────────────────────────────────────────────────────

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
            child: Icon(Icons.photo_camera_rounded, color: tm.sapphireLight, size: 20),
          ),
          const SizedBox(width: Spacing.xl2),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Photo Analysis',
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.3,
                  ),
                ),
                const SizedBox(height: Spacing.xxs),
                Text(
                  'AI-detected travel preferences',
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    color: tm.textTertiary,
                    fontWeight: FontWeight.w500,
                  ),
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
                  'AI Analyzed',
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    color: tm.sapphire,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInterestsSection(TourMateColors tm, PhotoAnalysisData data) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionLabel('Interests', tm),
          const SizedBox(height: Spacing.md),
          Wrap(
            spacing: Spacing.sm,
            runSpacing: Spacing.sm,
            children: data.interests.map((interest) {
              final emoji = _interestIcon(interest);
              return _InterestChip(emoji: emoji, label: interest, tm: tm);
            }).toList(),
          ),
          const SizedBox(height: Spacing.xl3),
        ],
      ),
    );
  }

  Widget _buildFoodSection(TourMateColors tm, PhotoAnalysisData data) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionLabel('Food Preferences', tm),
          const SizedBox(height: Spacing.md),
          Wrap(
            spacing: Spacing.sm,
            runSpacing: Spacing.sm,
            children: data.foodPreferences.map((pref) {
              return _InterestChip(emoji: '🍽️', label: pref, tm: tm);
            }).toList(),
          ),
          const SizedBox(height: Spacing.xl3),
        ],
      ),
    );
  }

  Widget _buildEnvironmentSection(TourMateColors tm, PhotoAnalysisData data) {
    final emoji = _envIcon(data.environmentType!);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionLabel('Environment', tm),
          const SizedBox(height: Spacing.md),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.md),
            decoration: BoxDecoration(
              color: tm.sapphire.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(RadiusTokens.md),
              border: Border.all(color: tm.sapphire.withValues(alpha: 0.15)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(emoji, style: const TextStyle(fontSize: 16)),
                const SizedBox(width: Spacing.sm),
                Text(
                  _capitalizeWords(data.environmentType!.replaceAll('_', ' ')),
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: tm.textPrimary,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: Spacing.xl3),
        ],
      ),
    );
  }

  Widget _buildVibeSection(TourMateColors tm, PhotoAnalysisData data) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _sectionLabel('Overall Vibe', tm),
          const SizedBox(height: Spacing.md),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.md),
            decoration: BoxDecoration(
              color: tm.surface,
              borderRadius: BorderRadius.circular(RadiusTokens.md),
              border: Border.all(color: tm.borderLight),
            ),
            child: Row(
              children: [
                Text('✨', style: const TextStyle(fontSize: 16)),
                const SizedBox(width: Spacing.sm),
                Expanded(
                  child: Text(
                    data.vibe!,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: tm.textPrimary,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: Spacing.xl3),
        ],
      ),
    );
  }

  Widget _buildActionButtons(TourMateColors tm) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, Spacing.xl4),
      child: Column(
        children: [
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: widget.onPlanTrip,
              icon: const Icon(Icons.rocket_launch_rounded, size: 18),
              label: Text(
                'Plan My Trip',
                style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w700),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: tm.deepNavy,
                foregroundColor: tm.brandWhite,
                padding: const EdgeInsets.symmetric(vertical: Spacing.xl2),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                  side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                ),
                elevation: 0,
              ),
            ),
          ),
          const SizedBox(height: Spacing.md),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: widget.onModifyPreferences,
                  icon: Icon(Icons.edit_rounded, size: 15, color: tm.textSecondary),
                  label: Text(
                    'Modify',
                    style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: tm.textSecondary),
                  ),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: Spacing.md),
                    side: BorderSide(color: tm.borderLight),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
                  ),
                ),
              ),
              const SizedBox(width: Spacing.md),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: widget.onStartFresh,
                  icon: Icon(Icons.refresh_rounded, size: 15, color: tm.textSecondary),
                  label: Text(
                    'Start Fresh',
                    style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: tm.textSecondary),
                  ),
                  style: OutlinedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: Spacing.md),
                    side: BorderSide(color: tm.borderLight),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _sectionLabel(String label, TourMateColors tm) {
    return Text(
      label,
      style: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        color: tm.textTertiary,
        letterSpacing: 0.3,
        height: 1,
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// PRIVATE HELPERS
// ═════════════════════════════════════════════════════════════════════════════

String _capitalizeWords(String input) {
  if (input.isEmpty) return input;
  return input.split(' ').map((w) {
    if (w.isEmpty) return w;
    return w[0].toUpperCase() + w.substring(1);
  }).join(' ');
}

// ── Interest Chip ──────────────────────────────────────────────────────────

class _InterestChip extends StatelessWidget {
  final String emoji;
  final String label;
  final TourMateColors tm;

  const _InterestChip({required this.emoji, required this.label, required this.tm});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.sapphire.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        border: Border.all(color: tm.sapphire.withValues(alpha: 0.15)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(emoji, style: const TextStyle(fontSize: 14)),
          const SizedBox(width: Spacing.xs),
          Text(
            _capitalizeWords(label.replaceAll('_', ' ')),
            style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: tm.textPrimary),
          ),
        ],
      ),
    );
  }
}

// ── Shimmer Box ────────────────────────────────────────────────────────────

class _ShimmerBox extends StatefulWidget {
  final double width;
  final double height;
  final double borderRadius;
  final TourMateColors tm;

  const _ShimmerBox({
    required this.width,
    required this.height,
    required this.borderRadius,
    required this.tm,
  });

  @override
  State<_ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<_ShimmerBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        return Container(
          width: widget.width.isFinite ? widget.width : double.infinity,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(widget.borderRadius),
            gradient: LinearGradient(
              begin: Alignment(-1.0 + _ctrl.value * 2, 0),
              end: Alignment(1.0 + _ctrl.value * 2, 0),
              colors: const [
                Color(0xFFF1F5F9),
                Color(0xFFEFF6FF),
                Color(0xFFDBEAFE),
                Color(0xFFEFF6FF),
                Color(0xFFF1F5F9),
              ],
              stops: const [0.0, 0.3, 0.5, 0.7, 1.0],
            ),
          ),
        );
      },
    );
  }
}

// ── Pulsing Dot ────────────────────────────────────────────────────────────

class _PulsingDot extends StatefulWidget {
  final TourMateColors tm;
  const _PulsingDot({required this.tm});

  @override
  State<_PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<_PulsingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))
      ..repeat(reverse: true);
    _scale = Tween<double>(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _scale,
      builder: (context, _) {
        return Transform.scale(
          scale: _scale.value,
          child: Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF1E3A8A), Color(0xFF2563EB)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: widget.tm.sapphire.withValues(alpha: 0.3),
                  blurRadius: 4,
                  offset: const Offset(0, 0),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

// ── Animated Ellipsis ──────────────────────────────────────────────────────

class _AnimatedEllipsis extends StatefulWidget {
  final TourMateColors tm;
  const _AnimatedEllipsis({required this.tm});

  @override
  State<_AnimatedEllipsis> createState() => _AnimatedEllipsisState();
}

class _AnimatedEllipsisState extends State<_AnimatedEllipsis>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (context, _) {
        final dots = '.' * ((_ctrl.value * 3).floor() % 4);
        return Text(
          dots,
          style: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: widget.tm.textSecondary,
            height: 0.8,
          ),
        );
      },
    );
  }
}
