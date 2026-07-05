import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../app/app_theme.dart';
import '../theme/design_tokens.dart';

/// An expandable container that shows a short preview of recommendation text
/// with a lightbulb icon and a "Show more / Show less" toggle.
class ExpandableRecommendation extends StatefulWidget {
  final String text;
  final int maxLinesCollapsed;

  const ExpandableRecommendation({
    super.key,
    required this.text,
    this.maxLinesCollapsed = 3,
  });

  @override
  State<ExpandableRecommendation> createState() => _ExpandableRecommendationState();
}

class _ExpandableRecommendationState extends State<ExpandableRecommendation> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(Spacing.sm),
      decoration: BoxDecoration(
        color: tm.sapphire.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(RadiusTokens.md),
        border: Border.all(color: tm.sapphire.withValues(alpha: 0.12)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Icon(
                  Icons.auto_awesome,
                  size: 14,
                  color: tm.sapphire,
                ),
              ),
              const SizedBox(width: Spacing.sm),
              Expanded(
                child: Text(
                  widget.text,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    color: tm.textPrimary,
                    height: 1.4,
                    fontWeight: FontWeight.w500,
                  ),
                  maxLines: _expanded ? null : widget.maxLinesCollapsed,
                  overflow: _expanded ? null : TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          // Show more/less toggle
          const SizedBox(height: Spacing.xxs),
          GestureDetector(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  _expanded ? Icons.expand_less_rounded : Icons.expand_more_rounded,
                  size: 14,
                  color: tm.sapphire,
                ),
                const SizedBox(width: Spacing.xxs),
                Text(
                  _expanded ? 'Show less' : 'Show more',
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
}
