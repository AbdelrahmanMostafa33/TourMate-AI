import 'package:flutter/material.dart';

/// Wraps a card widget with a staggered entrance animation (fade + slide up).
///
/// Automatically triggers when the widget first renders, using a 500ms
/// [AnimationController] with [Curves.easeOutCubic] for a premium feel.
/// The animation is client-side only and does not depend on any server state.
class AnimatedCardEntry extends StatefulWidget {
  final Widget child;
  final Duration duration;
  final Curve curve;

  const AnimatedCardEntry({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 500),
    this.curve = Curves.easeOutCubic,
  });

  @override
  State<AnimatedCardEntry> createState() => _AnimatedCardEntryState();
}

class _AnimatedCardEntryState extends State<AnimatedCardEntry>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration,
    )..forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
        CurvedAnimation(
          parent: _controller,
          curve: widget.curve,
        ),
      ),
      child: ScaleTransition(
        scale: Tween<double>(begin: 1.02, end: 1.0).animate(
          CurvedAnimation(
            parent: _controller,
            curve: widget.curve,
          ),
        ),
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.12),
            end: Offset.zero,
          ).animate(
            CurvedAnimation(
              parent: _controller,
              curve: widget.curve,
            ),
          ),
          child: widget.child,
        ),
      ),
    );
  }
}
