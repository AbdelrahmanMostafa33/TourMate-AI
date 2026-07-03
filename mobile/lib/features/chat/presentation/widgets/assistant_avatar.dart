import 'dart:math' as math;
import 'package:flutter/material.dart';

/// A premium **AI Travel Companion** avatar representing TourMate's concierge.
///
/// The illustration centers on the concept of *"an AI guiding your journey
/// around the world"* — a refined glass globe with a graceful flight path
/// orbiting around it:
///
/// * A minimalist glass globe with subtle latitude/longitude grid lines
/// * A thin, elegant orbit line wrapping around the globe (the flight path)
/// * A premium airplane silhouette integrated into the orbit
/// * Delicate sparkling highlights suggesting intelligence
/// * A soft sapphire-blue ambient glow
///
/// ### Ambient animations (all derived from a single 18s controller)
///
/// 1. **Globe glow** — A soft sapphire glow that gently "breathes" (~5s cycle)
/// 2. **Flight path rotation** — The orbit rotates slowly (~18s per revolution)
/// 3. **Sparkles** — Three highlights fade independently (staggered timing)
/// 4. **Glass reflection** — A gentle highlight drift across the surface (~36s)
///
/// The globe itself remains stable — only the flight path moves.
///
/// Four sizes are available:
/// - [AssistantAvatarSize.small] (28px) – message bubbles
/// - [AssistantAvatarSize.medium] (36px) – compact contexts
/// - [AssistantAvatarSize.large] (48px) – headers
/// - [AssistantAvatarSize.xlarge] (120px) – welcome/empty state
class AssistantAvatar extends StatefulWidget {
  final AssistantAvatarSize size;

  const AssistantAvatar({super.key, this.size = AssistantAvatarSize.small});

  @override
  State<AssistantAvatar> createState() => _AssistantAvatarState();
}

class _AssistantAvatarState extends State<AssistantAvatar>
    with TickerProviderStateMixin {
  /// Single master controller at 18 seconds.
  ///
  /// All animations derive from this one linear controller:
  ///   - Glow:     3.6 cycles → ~5s per breath
  ///   - Orbit:    1.0 cycles → 18s per rotation
  ///   - Sparkles: staggered frequencies (1.7–2.5)
  ///   - Reflection: 0.5 cycles → 36s per drift
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 18000),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final outerRadius = switch (widget.size) {
      AssistantAvatarSize.small => 14.0,
      AssistantAvatarSize.medium => 18.0,
      AssistantAvatarSize.large => 24.0,
      AssistantAvatarSize.xlarge => 60.0,
    };

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final v = _controller.value;

        // ── 1. Ambient glow (sine-based breathing) ───────────────
        final glowRaw = math.sin(v * 2 * math.pi * 3.6);
        final glowBreath = (glowRaw + 1.0) / 2.0;
        final glowOpacity = 0.50 + glowBreath * 0.50;

        // ── 2. Orbit rotation (flight path) ──────────────────────
        final orbitAngle = v * 2 * math.pi;

        // ── 3. Sparkle opacities ─────────────────────────────────
        final s1 = _sparkleOpacity(v, frequency: 2.0, phase: 0.0);
        final s2 = _sparkleOpacity(v, frequency: 2.5, phase: 1.8);
        final s3 = _sparkleOpacity(v, frequency: 1.7, phase: 3.6);

        // ── 4. Glass reflection drift ────────────────────────────
        final refX = math.sin(v * 2 * math.pi * 0.5) * 0.12;
        final refY = math.cos(v * 2 * math.pi * 0.5) * 0.08;

        return SizedBox(
          width: outerRadius * 2,
          height: outerRadius * 2,
          child: CustomPaint(
            painter: _TravelGlobePainter(
              radius: outerRadius,
              glowOpacity: glowOpacity,
              orbitAngle: orbitAngle,
              sparkleOpacities: [s1, s2, s3],
              reflectionOffset: Offset(refX, refY),
            ),
          ),
        );
      },
    );
  }

  double _sparkleOpacity(double t,
      {required double frequency, required double phase}) {
    final raw = math.sin(t * 2 * math.pi * frequency + phase);
    return (raw * 0.35) + 0.65;
  }
}

enum AssistantAvatarSize { small, medium, large, xlarge }

/// Custom painter that draws the Travel Globe with flight path.
///
/// Render order:
/// 1. Ambient glow (breathing)
/// 2. Globe body (radial gradient)
/// 3. Inner glow for depth
/// 4. Glass reflection (animated drift)
/// 5. Globe grid lines (lat/long, clipped to orb)
/// 6. Edge ring (covers clip artifacts)
/// 7. Flight path orbit + airplane (rotating)
/// 8. Sparkle highlights
class _TravelGlobePainter extends CustomPainter {
  final double radius;
  final double glowOpacity;
  final double orbitAngle;
  final List<double> sparkleOpacities;
  final Offset reflectionOffset;

  static const Color _primary = Color(0xFF1E3A8A);
  static const Color _accent = Color(0xFF2563EB);
  static const Color _dark = Color(0xFF0F172A);

  _TravelGlobePainter({
    required this.radius,
    required this.glowOpacity,
    required this.orbitAngle,
    required this.sparkleOpacities,
    required this.reflectionOffset,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = radius;
    if (r < 2) return;

    // ── 1. Animated ambient glow ──────────────────────────────────
    final glowPaint = Paint()
      ..color = _accent.withValues(alpha: 0.20 * glowOpacity)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8.0);
    canvas.drawCircle(center, r * 1.0, glowPaint);

    final softGlowPaint = Paint()
      ..color = _accent.withValues(alpha: 0.10 * glowOpacity)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 20.0);
    canvas.drawCircle(center, r * 1.15, softGlowPaint);

    // ── 2. Globe body ─────────────────────────────────────────────
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

    // ── 3. Inner glow for depth ──────────────────────────────────
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

    // ── 4. Animated glass reflection ─────────────────────────────
    final refCenter = Alignment(
      -0.4 + reflectionOffset.dx,
      -0.4 + reflectionOffset.dy,
    );
    final reflectionPaint = Paint()
      ..shader = RadialGradient(
        center: refCenter,
        radius: 0.5,
        colors: [
          Colors.white.withValues(alpha: 0.12),
          Colors.white.withValues(alpha: 0.04),
          Colors.white.withValues(alpha: 0.0),
        ],
        stops: const [0.0, 0.5, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: r));
    canvas.drawCircle(center, r, reflectionPaint);

    // ── 5. Globe grid lines (latitudes + longitude) ──────────────
    // Clipped to the globe circle so lines don't extend past the edge.
    final globeBounds = Rect.fromCircle(center: center, radius: r);
    canvas.save();
    canvas.clipPath(Path()..addOval(globeBounds));

    final gridPaint = Paint()
      ..color = _accent.withValues(alpha: 0.12)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;

    // Equator line
    canvas.drawOval(
      Rect.fromCenter(center: center, width: r * 2.2, height: r * 0.5),
      gridPaint,
    );

    // Northern parallel
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(center.dx, center.dy - r * 0.45),
        width: r * 2.2,
        height: r * 0.65,
      ),
      gridPaint,
    );

    // Southern parallel
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(center.dx, center.dy + r * 0.45),
        width: r * 2.2,
        height: r * 0.65,
      ),
      gridPaint,
    );

    // Prime meridian (longitude)
    final lonPaint = Paint()
      ..color = _accent.withValues(alpha: 0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.6;
    canvas.drawOval(
      Rect.fromCenter(center: center, width: r * 0.45, height: r * 2.2),
      lonPaint,
    );

    canvas.restore(); // remove clip

    // ── 6. Edge ring (over grid lines to cover clip edge) ───────
    final edgePaint = Paint()
      ..color = _accent.withValues(alpha: 0.18)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawCircle(center, r - 0.5, edgePaint);

    // ── 7. Flight path orbit + airplane ─────────────────────────
    // The orbit rotates continuously around the stationary globe.
    final orbitPaint = Paint()
      ..color = _accent.withValues(alpha: 0.28)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(-0.45 + orbitAngle);

    final orbitWidth = r * 1.65;
    final orbitHeight = r * 0.72;
    final orbitRect = Rect.fromCenter(
      center: Offset.zero,
      width: orbitWidth,
      height: orbitHeight,
    );
    canvas.drawOval(orbitRect, orbitPaint);

    // Primary airplane (actively traveling along the orbit)
    final planeAngle = 0.6;
    final px = math.cos(planeAngle) * (orbitWidth / 2);
    final py = -math.sin(planeAngle) * (orbitHeight / 2);
    final tangentAngle = math.atan2(
      -math.cos(planeAngle) * orbitHeight,
      -math.sin(planeAngle) * orbitWidth,
    );
    _drawAirplane(canvas, Offset(px, py), tangentAngle, r);

    // Secondary airplane (opposite side, subtle)
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

    // ── 8. Sparkle highlights ────────────────────────────────────
    if (sparkleOpacities.length >= 3) {
      _drawSparkle(
        canvas,
        center + Offset(-r * 0.45, -r * 0.45),
        r * 0.09,
        opacity: sparkleOpacities[0],
      );
      _drawSparkle(
        canvas,
        center + Offset(-r * 0.12, -r * 0.75),
        r * 0.06,
        opacity: sparkleOpacities[1],
      );
      _drawSparkle(
        canvas,
        center + Offset(r * 0.6, -r * 0.2),
        r * 0.04,
        opacity: sparkleOpacities[2] * 0.6,
      );
    }
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

    // Wings
    final wingPath = Path()
      ..moveTo(planeScale * 0.15, 0)
      ..lineTo(-planeScale * 0.3, -planeScale * 0.55)
      ..lineTo(-planeScale * 0.05, 0)
      ..close();
    canvas.drawPath(wingPath, planePaint);

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

    final dotPaint = Paint()
      ..color = Colors.white.withValues(alpha: opacity);
    canvas.drawCircle(position, size, dotPaint);

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
  bool shouldRepaint(_TravelGlobePainter oldDelegate) =>
      oldDelegate.radius != radius ||
      (oldDelegate.glowOpacity - glowOpacity).abs() > 0.001 ||
      (oldDelegate.orbitAngle - orbitAngle).abs() > 0.001 ||
      oldDelegate.reflectionOffset != reflectionOffset ||
      _opacitiesChanged(oldDelegate.sparkleOpacities);

  bool _opacitiesChanged(List<double> old) {
    if (old.length != sparkleOpacities.length) return true;
    for (var i = 0; i < old.length; i++) {
      if ((old[i] - sparkleOpacities[i]).abs() > 0.001) return true;
    }
    return false;
  }
}
