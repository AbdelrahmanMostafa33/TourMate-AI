import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../logic/chat_cubit.dart';

/// Animated progress indicator showing the AI pipeline steps during
/// itinerary generation (60–90 s).
///
/// Each step shows:
///   - Agent name (e.g. "RetrievalAgent")
///   - A live status icon (spinner / check / error)
///   - A human-readable message
///   - A smooth height transition when new steps appear
class PipelineProgressWidget extends StatefulWidget {
  final List<PipelineStep> steps;

  const PipelineProgressWidget({super.key, required this.steps});

  @override
  State<PipelineProgressWidget> createState() => _PipelineProgressWidgetState();
}

class _PipelineProgressWidgetState extends State<PipelineProgressWidget>
    with SingleTickerProviderStateMixin {
  TourMateColors get tm => context.tm;

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
    _pulseAnimation = Tween<double>(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.steps.isEmpty) return const SizedBox.shrink();

    return AnimatedSize(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: Spacing.xl, vertical: Spacing.sm),
        padding: const EdgeInsets.all(Spacing.xl3),
        decoration: BoxDecoration(
          color: tm.surface,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          border: Border.all(color: tm.borderLight),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            /// ── Premium Header ──────────────────────────────────────
            Row(
              children: [
                SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(tm.deepRoyalBlue),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  'Generating your itinerary…',
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: tm.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: Spacing.md),

            /// ── Premium Steps ───────────────────────────────────────
            ...widget.steps.map(_buildStep),
          ],
        ),
      ),
    );
  }

  Widget _buildStep(PipelineStep step) {
    final isRunning = step.status == 'running';
    final isDone = step.status == 'done';

    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.sm),
      child: Row(
        children: [
          /// ── sapphire-accented status icon ────────────────────────────
          SizedBox(
            width: 20,
            height: 20,
            child: isRunning
                ? FadeTransition(
                    opacity: _pulseAnimation,
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(tm.deepRoyalBlue),
                      ),
                    ),
                  )
                : isDone
                    ? Icon(Icons.check_circle_rounded, size: 18, color: tm.deepRoyalBlue)
                    : Icon(Icons.error_rounded, size: 18, color: tm.error),
          ),
          const SizedBox(width: 10),

          /// ── sapphire-accented text ───────────────────────────────────
          Expanded(
            child: Text(
              step.message.isNotEmpty ? step.message : step.agent,
              style: GoogleFonts.inter(
                fontSize: 13,
                fontWeight: isRunning ? FontWeight.w600 : FontWeight.w400,
                color: isRunning
                    ? tm.textPrimary
                    : isDone
                        ? tm.textSecondary
                        : tm.error,
              ),
              overflow: TextOverflow.ellipsis,
              maxLines: 2,
            ),
          ),
        ],
      ),
    );
  }
}
