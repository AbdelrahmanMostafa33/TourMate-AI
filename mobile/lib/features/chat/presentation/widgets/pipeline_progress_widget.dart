import 'package:flutter/material.dart';
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
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            /// ── Header ─────────────────────────────────────────────
            Row(
              children: [
                SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(
                      Colors.blue.shade600,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                const Text(
                  "Generating your itinerary\u2026",
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.black87,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),

            /// ── Steps ──────────────────────────────────────────────
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
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          /// ── Status icon ────────────────────────────────────────
          SizedBox(
            width: 18,
            height: 18,
            child: isRunning
                ? FadeTransition(
                    opacity: _pulseAnimation,
                    child: SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          Colors.blue.shade500,
                        ),
                      ),
                    ),
                  )
                : isDone
                    ? Icon(Icons.check_circle_rounded,
                        size: 16, color: Colors.green.shade600)
                    : Icon(Icons.error_rounded,
                        size: 16, color: Colors.red.shade500),
          ),
          const SizedBox(width: 10),

          /// ── Text ──────────────────────────────────────────────
          Expanded(
            child: Text(
              step.message.isNotEmpty ? step.message : step.agent,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isRunning ? FontWeight.w500 : FontWeight.w400,
                color: isRunning
                    ? Colors.black87
                    : isDone
                        ? Colors.grey.shade600
                        : Colors.red.shade700,
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
