import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../../app/app_theme.dart';

/// A premium avatar representing the TourMate AI concierge.
///
/// Features a gold-gradient ring with a subtle glow, a dark center,
/// and the TourMate compass icon. The avatar gently floats up and down
/// with a subtle sine-wave animation while idle.
///
/// Three sizes are available:
/// [AssistantAvatarSize.small] (28px), .medium (36px), .large (48px).
class AssistantAvatar extends StatefulWidget {
  final AssistantAvatarSize size;

  const AssistantAvatar({super.key, this.size = AssistantAvatarSize.small});

  @override
  State<AssistantAvatar> createState() => _AssistantAvatarState();
}

class _AssistantAvatarState extends State<AssistantAvatar>
    with TickerProviderStateMixin {
  late final AnimationController _floatController;
  late final AnimationController _shimmerController;

  @override
  void initState() {
    super.initState();
    _floatController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3000),
    )..repeat();
    _shimmerController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 5000),
    )..repeat();
  }

  @override
  void dispose() {
    _floatController.dispose();
    _shimmerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final (outerRadius, innerRadius, iconSize) = switch (widget.size) {
      AssistantAvatarSize.small => (14.0, 11.0, 14.0),
      AssistantAvatarSize.medium => (18.0, 14.5, 18.0),
      AssistantAvatarSize.large => (24.0, 20.0, 22.0),
    };

    return AnimatedBuilder(
      animation: _floatController,
      builder: (context, _) {
        // Gentle sine-wave float: ±3 pixels over 3 seconds
        final floatY = math.sin(_floatController.value * 2 * math.pi) * 3.0;
        // Shimmer rotation: full sweep over 5 seconds
        final shimmerAngle = _shimmerController.value * 2 * math.pi;
        // Gentle pulse: 0→1 sine wave over the same 5s cycle
        final pulse = (math.sin(_shimmerController.value * 2 * math.pi) + 1) / 2;
        final blurRadius = 4.0 + pulse * 4.0;   // 4 → 8
        final shadowAlpha = 0.15 + pulse * 0.2;  // 0.15 → 0.35
        return Transform.translate(
          offset: Offset(0, floatY),
          child: Container(
            width: outerRadius * 2,
            height: outerRadius * 2,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: SweepGradient(
                startAngle: shimmerAngle,
                endAngle: shimmerAngle + 3.14159 * 2,
                colors: const [
                  Color(0xFFC8A84E),
                  Color(0x66C8A84E),
                  Color(0xFFC8A84E),
                  Color(0x33C8A84E),
                  Color(0xFFC8A84E),
                ],
                stops: const [0.0, 0.25, 0.5, 0.75, 1.0],
              ),
              boxShadow: [
                BoxShadow(
                  color: tm.gold.withValues(alpha: shadowAlpha),
                  blurRadius: blurRadius,
                  offset: const Offset(0, 1),
                ),
              ],
            ),
            padding: const EdgeInsets.all(1.5),
            child: Container(
              decoration: const BoxDecoration(
                color: Color(0xFF0A0A0A),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.explore_outlined,
                size: iconSize,
                color: tm.goldLight,
              ),
            ),
          ),
        );
      },
    );
  }
}

enum AssistantAvatarSize { small, medium, large }
