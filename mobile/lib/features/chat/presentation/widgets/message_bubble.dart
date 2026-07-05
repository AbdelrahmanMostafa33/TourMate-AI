import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/chat_message.dart';
import '../../logic/card_renderer.dart';
import '../../logic/chat_segment.dart';
import 'assistant_avatar.dart';
import 'animated_card_entry.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage msg;
  final VoidCallback? onApproveItinerary;
  final void Function(dynamic)? onSelectHotel;
  final void Function(dynamic)? onSelectFlight;
  final VoidCallback? onBookingPayNow;
  final VoidCallback? onBookingLater;
  final VoidCallback? onPlanTrip;
  final VoidCallback? onModifyPreferences;
  final VoidCallback? onStartFresh;

  const MessageBubble({
    super.key,
    required this.msg,
    this.onApproveItinerary,
    this.onSelectHotel,
    this.onSelectFlight,
    this.onBookingPayNow,
    this.onBookingLater,
    this.onPlanTrip,
    this.onModifyPreferences,
    this.onStartFresh,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final isUser = msg.isUser;

    // Build list of segment widgets from the message's segment list.
    // Each segment type maps to a specific widget type.
    final segmentWidgets = <Widget>[];
    for (final seg in msg.segments) {
      switch (seg) {
        case TextSegment(:final text, :final isStreaming):
          if (text.isNotEmpty || isStreaming) {
            segmentWidgets.add(
              _buildTextSegment(context, tm, isUser, text, isStreaming),
            );
          }

        case CardSegment(:final cardType):
          segmentWidgets.add(
            Align(
              alignment: Alignment.centerLeft,
              child: AnimatedCardEntry(
                child: _buildCardWidget(context, cardType, seg),
              ),
            ),
          );

        case ProgressSegment():
          // Progress is handled by ChatScreen's pipeline UI
          break;
      }
    }

    // If there are no segments (just image), show only the image.
    if (segmentWidgets.isEmpty && msg.imageBytes == null) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        // Display image above the message
        if (msg.imageBytes != null)
          AnimatedCardEntry(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl),
                  border: Border.all(color: tm.sapphire.withValues(alpha: 0.2), width: 1),
                  boxShadow: [
                    BoxShadow(
                      color: tm.deepNavy.withValues(alpha: 0.06),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl - 1),
                  child: Image.memory(
                    msg.imageBytes!,
                    width: 200,
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            ),
          ),

        // Render segments
        ...segmentWidgets,
      ],
    );
  }

  /// Cached registry — allocated once rather than on every render call.
  static final CardRendererRegistry _registry = CardRendererRegistry.builtIn;

  /// Route a card segment to the correct widget via the [CardRendererRegistry].
  ///
  /// To add a new card type, implement [CardRenderer] and register it in
  /// [CardRendererRegistry.builtIn] — no changes needed in this widget.
  Widget _buildCardWidget(BuildContext context, String cardType, CardSegment seg) {
    final renderer = _registry.get(cardType);
    if (renderer == null) {
      return const SizedBox.shrink();
    }
    final callbacks = CardCallbacks(
      onApproveItinerary: onApproveItinerary,
      onSelectHotel: onSelectHotel,
      onSelectFlight: onSelectFlight,
      onBookingPayNow: onBookingPayNow,
      onBookingLater: onBookingLater,
      onPlanTrip: onPlanTrip,
      onModifyPreferences: onModifyPreferences,
      onStartFresh: onStartFresh,
    );
    return renderer.build(context, seg, callbacks);
  }

  /// Build a text bubble segment with an optional assistant avatar.
  Widget _buildTextSegment(
    BuildContext context,
    TourMateColors tm,
    bool isUser,
    String text,
    bool isStreaming,
  ) {
    if (isUser) {
      return Align(
        alignment: Alignment.centerRight,
        child: _buildBubble(context, tm, isUser, text, isStreaming),
      );
    }

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Padding(
          padding: const EdgeInsets.only(right: 6, bottom: 4),
          child: const AssistantAvatar(size: AssistantAvatarSize.small),
        ),
        Flexible(
          child: _buildBubble(context, tm, isUser, text, isStreaming),
        ),
      ],
    );
  }

  /// Shared bubble container used for both user and assistant messages.
  Widget _buildBubble(
    BuildContext context,
    TourMateColors tm,
    bool isUser,
    String text,
    bool isStreaming,
  ) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 4),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.72,
      ),
      decoration: BoxDecoration(
        color: isUser ? tm.deepNavy : tm.brandWhite,
        borderRadius: BorderRadius.circular(20).copyWith(
          bottomRight: isUser ? const Radius.circular(4) : null,
          bottomLeft: !isUser ? const Radius.circular(4) : null,
        ),
        border: isUser ? null : Border.all(color: tm.borderLight),
        boxShadow: isUser
            ? [
                BoxShadow(
                  color: tm.deepNavy.withValues(alpha: 0.12),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ]
            : [
                BoxShadow(
                  color: tm.deepNavy.withValues(alpha: 0.04),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (text.isNotEmpty)
            Text(
              text,
              style: GoogleFonts.inter(
                color: isUser ? tm.brandWhite : tm.textPrimary,
                fontSize: 15,
                height: 1.4,
              ),
            ),
        ],
      ),
    );
  }
}
