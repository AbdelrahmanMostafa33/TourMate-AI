import 'dart:math' as math;
import 'package:flutter/material.dart';

/// A premium **AI Travel Orb** representing the TourMate AI concierge.
///
/// The design communicates artificial intelligence, travel, guidance, and
/// discovery through a single cohesive illustration:
///
/// * A floating sapphire-blue glass orb
/// * A subtle translucent glass effect with radial gradient
/// * A thin orbit line wrapping around the orb
/// * A tiny airplane seamlessly integrated into the orbit
/// * Delicate sparkling highlights suggesting intelligence & responsiveness
/// * A soft ambient blue glow
///
/// Four sizes are available:
/// - [AssistantAvatarSize.small] (28px) – used in message bubbles
/// - [AssistantAvatarSize.medium] (36px) – used in compact contexts
/// - [AssistantAvatarSize.large] (48px) – used in headers
/// - [AssistantAvatarSize.xlarge] (120px) – used in the welcome/empty state
class AssistantAvatar extends StatelessWidget {
  final AssistantAvatarSize size;

  const AssistantAvatar({super.key, this.size = AssistantAvatarSize.small});

  @override
  Widget build(BuildContext context) {
    final outerRadius = switch (size) {
      AssistantAvatarSize.small => 14.0,
      AssistantAvatarSize.medium => 18.0,
      AssistantAvatarSize.large => 24.0,
      AssistantAvatarSize.xlarge => 60.0,
    };

    return SizedBox(
      width: outerRadius * 2,
      height: outerRadius * 2,
      child: CustomPaint(
        painter: _TravelOrbPainter(radius: outerRadius),
      ),
    );
  }
}

enum AssistantAvatarSize { small, medium, large, xlarge }

/// Custom painter that draws the complete Travel Orb illustration.
///
/// Renders in order:
/// 1. Outer ambient glow
/// 2. Glass orb body with radial gradient
/// 3. Thin edge ring
/// 4. Inner glow for depth
/// 5. Top-left light reflection (glass effect)
/// 6. Tilted orbit ellipse
/// 7. Tiny airplane positioned on the orbit
/// 8. Sparkle highlights
class _TravelOrbPainter extends CustomPainter {
  final double radius;

  static const Color _primary = Color(0xFF1E3A8A);  // Deep Royal Blue
  static const Color _accent = Color(0xFF2563EB);   // Sapphire
  static const Color _dark = Color(0xFF0F172A);     // Midnight Navy

  _TravelOrbPainter({required this.radius});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = radius;

    // ── 1. Outer ambient glow ──────────────────────────────────
    final glowPaint = Paint()
      ..color = _accent.withValues(alpha: 0.12)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8.0);
    canvas.drawCircle(center, r * 0.95, glowPaint);

    // Wider, softer glow ring
    final softGlowPaint = Paint()
      ..color = _accent.withValues(alpha: 0.06)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 16.0);
    canvas.drawCircle(center, r * 1.05, softGlowPaint);

    // ── 2. Glass orb body ─────────────────────────────────────
    final orbPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.35, -0.35),
        radius: 1.1,
        colors: [
          _accent.withValues(alpha: 0.04),
          _primary.withValues(alpha: 0.12),
          _accent.withValues(alpha: 0.22),
          _primary.withValues(alpha: 0.38),
          _dark.withValues(alpha: 0.48),
        ],
        stops: const [0.0, 0.3, 0.6, 0.85, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, orbPaint);

    // ── 3. Thin edge ring ─────────────────────────────────────
    final edgePaint = Paint()
      ..color = _accent.withValues(alpha: 0.18)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawCircle(center, r - 0.5, edgePaint);

    // ── 4. Inner glow for depth ───────────────────────────────
    final innerGlowPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(0.2, 0.2),
        radius: 0.8,
        colors: [
          _accent.withValues(alpha: 0.0),
          _accent.withValues(alpha: 0.0),
          _accent.withValues(alpha: 0.06),
          _accent.withValues(alpha: 0.10),
        ],
        stops: const [0.0, 0.6, 0.85, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, innerGlowPaint);

    // ── 5. Light reflection (top-left glass highlight) ────────
    final reflectionPaint = Paint()
      ..shader = RadialGradient(
        center: const Alignment(-0.4, -0.4),
        radius: 0.5,
        colors: [
          Colors.white.withValues(alpha: 0.12),
          Colors.white.withValues(alpha: 0.04),
          Colors.white.withValues(alpha: 0.0),
        ],
        stops: const [0.0, 0.5, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, reflectionPaint);

    // ── 6. Orbit ellipse (tilted ~25°) ─────────────────────────
    final orbitPaint = Paint()
      ..color = _accent.withValues(alpha: 0.28)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(-0.45); // ~25 degree tilt

    final orbitWidth = r * 1.65;
    final orbitHeight = r * 0.72;
    final orbitRect = Rect.fromCenter(
      center: Offset.zero,
      width: orbitWidth,
      height: orbitHeight,
    );
    canvas.drawOval(orbitRect, orbitPaint);

    // ── 7. Airplane on orbit ──────────────────────────────────
    // Position at ~30° from the right side of the ellipse
    final planeAngle = 0.6;
    final px = math.cos(planeAngle) * (orbitWidth / 2);
    final py = -math.sin(planeAngle) * (orbitHeight / 2);

    // Tangent angle at this point on the ellipse
    final tangentAngle = math.atan2(
      -math.cos(planeAngle) * orbitHeight,
      -math.sin(planeAngle) * orbitWidth,
    );

    _drawAirplane(canvas, Offset(px, py), tangentAngle, r);

    // ── 7b. Second airplane on opposite side (more subtle) ────
    final planeAngle2 = planeAngle + math.pi;
    final px2 = math.cos(planeAngle2) * (orbitWidth / 2);
    final py2 = -math.sin(planeAngle2) * (orbitHeight / 2);
    final tangentAngle2 = math.atan2(
      -math.cos(planeAngle2) * orbitHeight,
      -math.sin(planeAngle2) * orbitWidth,
    );
    _drawAirplane(canvas, Offset(px2, py2), tangentAngle2, r,
        opacity: 0.35, scale: 0.7);

    canvas.restore();

    // ── 8. Sparkle highlights ─────────────────────────────────
    _drawSparkle(canvas, center + Offset(-r * 0.45, -r * 0.45), r * 0.09);
    _drawSparkle(canvas, center + Offset(-r * 0.12, -r * 0.75), r * 0.06);
    _drawSparkle(canvas, center + Offset(r * 0.6, -r * 0.2), r * 0.04,
        opacity: 0.5);
  }

  void _drawAirplane(
    Canvas canvas,
    Offset position,
    double angle,
    double r, {
    double opacity = 0.8,
    double scale = 1.0,
  }) {
    final planeScale = r * 0.12 * scale;
    if (planeScale < 1.2) return;

    canvas.save();
    canvas.translate(position.dx, position.dy);
    canvas.rotate(angle);

    final planePaint = Paint()
      ..color = _accent.withValues(alpha: opacity)
      ..style = PaintingStyle.fill;

    // Fuselage
    final fuselagePath = Path()
      ..addOval(Rect.fromCenter(
        center: Offset.zero,
        width: planeScale * 2.2,
        height: planeScale * 0.45,
      ));
    canvas.drawPath(fuselagePath, planePaint);

    // Wings (left side extending back)
    final wingPath = Path()
      ..moveTo(planeScale * 0.15, 0)
      ..lineTo(-planeScale * 0.3, -planeScale * 0.55)
      ..lineTo(-planeScale * 0.05, 0)
      ..close();
    canvas.drawPath(wingPath, planePaint);

    // Wings (right side)
    final wingPath2 = Path()
      ..moveTo(planeScale * 0.15, 0)
      ..lineTo(-planeScale * 0.3, planeScale * 0.55)
      ..lineTo(-planeScale * 0.05, 0)
      ..close();
    canvas.drawPath(wingPath2, planePaint);

    // Tail fin
    final tailPaint = Paint()
      ..color = _accent.withValues(alpha: opacity * 0.6)
      ..style = PaintingStyle.fill;
    final tailPath = Path()
      ..moveTo(-planeScale * 0.85, 0)
      ..lineTo(-planeScale * 1.15, -planeScale * 0.25)
      ..lineTo(-planeScale * 1.15, planeScale * 0.25)
      ..close();
    canvas.drawPath(tailPath, tailPaint);

    canvas.restore();
  }

  void _drawSparkle(
    Canvas canvas,
    Offset position,
    double size, {
    double opacity = 0.9,
  }) {
    if (size < 0.8) return;

    // Main bright dot
    final dotPaint = Paint()
      ..color = Colors.white.withValues(alpha: opacity);
    canvas.drawCircle(position, size, dotPaint);

    // Cross shine (subtle)
    final shineLength = size * 2.5;
    final shinePaint = Paint()
      ..color = Colors.white.withValues(alpha: opacity * 0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.5;

    canvas.drawLine(
      position - Offset(shineLength, 0),
      position + Offset(shineLength, 0),
      shinePaint,
    );
    canvas.drawLine(
      position - Offset(0, shineLength),
      position + Offset(0, shineLength),
      shinePaint,
    );
  }

  @override
  bool shouldRepaint(_TravelOrbPainter oldDelegate) =>
      oldDelegate.radius != radius;
}
