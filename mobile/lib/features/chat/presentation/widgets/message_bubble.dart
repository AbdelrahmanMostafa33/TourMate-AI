import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/chat_message.dart';
import 'itinerary_card.dart';
import 'hotel_options_list.dart';
import 'booking_card.dart';
import 'flight_options_card.dart';
import 'assistant_avatar.dart';
import 'animated_card_entry.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage msg;
  final VoidCallback? onApproveItinerary;
  final void Function(dynamic)? onSelectHotel;
  final void Function(dynamic)? onSelectFlight;
  final VoidCallback? onBookingPayNow;
  final VoidCallback? onBookingLater;

  const MessageBubble({
    super.key,
    required this.msg,
    this.onApproveItinerary,
    this.onSelectHotel,
    this.onSelectFlight,
    this.onBookingPayNow,
    this.onBookingLater,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    // ── Booking Card (Pay Now / Do It Later) ─────────────────────
    if (msg.bookingData != null) {
      return Align(
        alignment: Alignment.centerLeft,
        child: AnimatedCardEntry(
          child: BookingCard(
            booking: msg.bookingData!,
            onPayNow: onBookingPayNow,
            onLater: onBookingLater,
          ),
        ),
      );
    }

    // ── Flight Options Card ──────────────────────────────────────
    if (msg.flightOptions != null) {
      return Align(
        alignment: Alignment.centerLeft,
        child: AnimatedCardEntry(
          child: FlightOptionsCard(
            payload: msg.flightOptions!,
            onSelectFlight: onSelectFlight,
          ),
        ),
      );
    }

    // ── Hotel Options Card ───────────────────────────────────────
    if (msg.hotelOptions != null) {
      return Align(
        alignment: Alignment.centerLeft,
        child: AnimatedCardEntry(
          child: HotelOptionsList(
            payload: msg.hotelOptions!,
            onSelectHotel: onSelectHotel,
          ),
        ),
      );
    }

    // ── Itinerary Card ───────────────────────────────────────────
    if (msg.itinerary != null) {
      return Align(
        alignment: Alignment.centerLeft,
        child: AnimatedCardEntry(
          child: ItineraryCard(
            itinerary: msg.itinerary!,
            onApprove: !msg.isUser ? onApproveItinerary : null,
          ),
        ),
      );
    }

    final isUser = msg.isUser;

    return Column(
      crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        // Display image above the message bubble
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
        // Premium message bubble with assistant avatar (bot only)
        if (msg.text.isNotEmpty || msg.isStreaming)
          isUser
              ? Align(
                  alignment: Alignment.centerRight,
                  child: _buildBubble(context, tm, isUser),
                )
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(right: 6, bottom: 4),
                      child: const AssistantAvatar(
                        size: AssistantAvatarSize.small,
                      ),
                    ),
                    Flexible(
                      child: _buildBubble(context, tm, isUser),
                    ),
                  ],
                ),
      ],
    );
  }

  /// Shared bubble container used for both user and assistant messages.
  Widget _buildBubble(BuildContext context, TourMateColors tm, bool isUser) {
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
          if (msg.text.isNotEmpty)
            Text(
              msg.text,
              style: GoogleFonts.inter(
                color: isUser ? tm.brandWhite : tm.textPrimary,
                fontSize: 15,
                height: 1.4,
              ),
            ),
          if (msg.isStreaming)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: tm.deepRoyalBlue,
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    'Thinking',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      color: tm.deepRoyalBlue,
                      fontWeight: FontWeight.w500,
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