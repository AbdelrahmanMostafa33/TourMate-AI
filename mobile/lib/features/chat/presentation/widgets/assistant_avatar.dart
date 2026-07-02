import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../../../app/app_theme.dart';

/// A premium avatar representing the TourMate AI concierge.
///
/// Features a deep blue gradient ring with a subtle glow, a dark center,
/// and a hand-crafted compass rose icon painted via [CustomPainter].
/// The avatar gently floats up and down with a subtle sine-wave animation
/// while idle — no spinning, shimmering, or gimmicky effects.
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
  late final Animation<double> _floatAnimation;

  @override
  void initState() {
    super.initState();
    _floatController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 4000),
    )..repeat(reverse: true);
    _floatAnimation = Tween<double>(begin: -2.0, end: 2.0).animate(
      CurvedAnimation(
        parent: _floatController,
        curve: Curves.easeInOutSine,
      ),
    );
  }

  @override
  void dispose() {
    _floatController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final outerRadius = switch (widget.size) {
      AssistantAvatarSize.small => 14.0,
      AssistantAvatarSize.medium => 18.0,
      AssistantAvatarSize.large => 24.0,
    };

    return AnimatedBuilder(
      animation: _floatAnimation,
      builder: (context, _) {
        return Transform.translate(
          offset: Offset(0, _floatAnimation.value),
          child: Container(
            width: outerRadius * 2,
            height: outerRadius * 2,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const SweepGradient(
                colors: [
                  Color(0xFF1E3A8A),
                  Color(0xFF2563EB),
                  Color(0xFF1E3A8A),
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: tm.deepRoyalBlue.withValues(alpha: 0.25),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            padding: const EdgeInsets.all(1.5),
            child: Container(
              decoration: const BoxDecoration(
                color: Color(0xFF0F172A),
                shape: BoxShape.circle,
              ),
              child: Padding(
                padding: const EdgeInsets.all(3.0),
                child: CustomPaint(
                  painter: _CompassPainter(
                    color: tm.sapphireLight,
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Custom painter that draws a refined compass rose icon.
///
/// The compass has:
/// - Four cardinal points (N, S, E, W) drawn as diamond shapes
/// - A small solid circle at the center representing AI intelligence
/// - Balanced proportions that scale with the available canvas
class _CompassPainter extends CustomPainter {
  final Color color;

  _CompassPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2;

    // ── North pointer (filled, largest) ──
    _drawCardinalPoint(canvas, center, radius, -math.pi / 2, true);

    // ── South pointer (filled) ──
    _drawCardinalPoint(canvas, center, radius, math.pi / 2, true);

    // ── East pointer (outlined, slightly smaller) ──
    _drawCardinalPoint(canvas, center, radius * 0.75, 0, false);

    // ── West pointer (outlined, slightly smaller) ──
    _drawCardinalPoint(canvas, center, radius * 0.75, math.pi, false);

    // ── Center AI dot ──
    final centerPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius * 0.18, centerPaint);

    // ── Small ring around center ──
    final ringPaint = Paint()
      ..color = color.withValues(alpha: 0.35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    canvas.drawCircle(center, radius * 0.32, ringPaint);
  }

  void _drawCardinalPoint(
    Canvas canvas,
    Offset center,
    double radius,
    double angle,
    bool filled,
  ) {
    final paint = Paint()
      ..color = filled ? color : color.withValues(alpha: 0.5)
      ..style = filled ? PaintingStyle.fill : PaintingStyle.stroke
      ..strokeWidth = 1.0;

    final path = Path();
    // Diamond shape pointing outward
    final tip = Offset(
      center.dx + math.cos(angle) * radius,
      center.dy + math.sin(angle) * radius,
    );
    final left = Offset(
      center.dx + math.cos(angle + math.pi / 2) * radius * 0.35,
      center.dy + math.sin(angle + math.pi / 2) * radius * 0.35,
    );
    final right = Offset(
      center.dx + math.cos(angle - math.pi / 2) * radius * 0.35,
      center.dy + math.sin(angle - math.pi / 2) * radius * 0.35,
    );
    final base = Offset(
      center.dx + math.cos(angle + math.pi) * radius * 0.25,
      center.dy + math.sin(angle + math.pi) * radius * 0.25,
    );

    path.moveTo(tip.dx, tip.dy);
    path.lineTo(left.dx, left.dy);
    path.lineTo(base.dx, base.dy);
    path.lineTo(right.dx, right.dy);
    path.close();

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(_CompassPainter oldDelegate) =>
      oldDelegate.color != color;
}

enum AssistantAvatarSize { small, medium, large }
