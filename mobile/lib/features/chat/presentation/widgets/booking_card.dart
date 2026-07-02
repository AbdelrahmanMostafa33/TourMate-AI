import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/booking_data.dart';

/// Displays a booking confirmation card after the user selects a hotel
/// (and optionally a flight). Shows trip summary, pricing, and action
/// buttons to proceed to payment or book later.
///
/// When [booking.isConfirmed] is true, shows a green "✅ Booking Confirmed"
/// badge and hides the Pay Now / Book Later action buttons.
class BookingCard extends StatelessWidget {
  final BookingData booking;
  final VoidCallback? onPayNow;
  final VoidCallback? onLater;

  const BookingCard({
    super.key,
    required this.booking,
    this.onPayNow,
    this.onLater,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    final isConfirmed = booking.isConfirmed;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(
          color: isConfirmed ? tm.sapphire.withValues(alpha: 0.4) : tm.borderLight,
        ),
        boxShadow: [
          BoxShadow(
            color: isConfirmed
                ? tm.sapphire.withValues(alpha: 0.08)
                : tm.deepNavy.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Premium Header ─────────────────────────────
          _buildHeader(isConfirmed, tm),
          Container(height: 1, color: tm.divider),

          // ── Trip Summary ───────────────────────────────
          _buildTripSummary(tm),
          if (isConfirmed) ...[
            Container(height: 1, color: tm.divider),
            _buildConfirmedBanner(tm),
          ] else ...[
            Container(height: 1, color: tm.divider),
            // ── Pricing Breakdown ────────────────────────
            _buildPricing(tm),
            Container(height: 1, color: tm.divider),
            // ── Premium Action Buttons ───────────────────
            _buildActions(context),
          ],
        ],
      ),
    );
  }

  Widget _buildHeader(bool isConfirmed, TourMateColors tm) {
    return Hero(
      tag: 'booking-summary-${booking.tripId ?? "unknown"}',
      child: Container(
        padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl4, Spacing.xl4, Spacing.xl3),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
              ),
              child: Icon(Icons.check_circle_rounded, color: tm.sapphireLight, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isConfirmed ? 'Booking Confirmed!' : 'Trip Confirmed!',
                    style: GoogleFonts.inter(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: tm.textPrimary,
                      letterSpacing: -0.3,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    booking.tripSummary?.destination ?? 'Your trip',
                    style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
            if (booking.pricing != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: tm.sapphire.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
                ),
                child: Text(
                  _formatPrice(booking.pricing!.totalEstimated, booking.pricing!.currency),
                  style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700, color: tm.sapphire),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTripSummary(TourMateColors tm) {
    final summary = booking.tripSummary;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Trip Summary',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: tm.textPrimary,
            ),
          ),
          const SizedBox(height: 12),

          // Premium Flight info
          if (booking.flight != null && booking.hasFlight) ...[
            _summaryRow(tm,
              icon: Icons.flight_takeoff_rounded,
              title: 'Flight',
              subtitle: '${booking.flight!.airline ?? ''} ${booking.flight!.flightNumber ?? ''}'
                  '${booking.flight!.originIata != null ? ' · ${booking.flight!.originIata} → ${booking.flight!.destinationIata}' : ''}',
              trailing: booking.flight!.price > 0
                  ? _formatPrice(booking.flight!.price, booking.flight!.currency)
                  : null,
            ),
            const SizedBox(height: 10),
          ],

          // Premium Hotel info
          if (booking.hotel != null && booking.hasHotel) ...[
            _summaryRow(tm,
              icon: Icons.hotel_rounded,
              title: 'Hotel',
              subtitle: booking.hotel!.name ?? 'Selected hotel',
              subtitle2: booking.hotel!.nightlyRate > 0
                  ? '${_formatPrice(booking.hotel!.nightlyRate, booking.hotel!.currency)} / night'
                  : null,
              trailing: booking.hotel!.totalCost > 0
                  ? _formatPrice(booking.hotel!.totalCost, booking.hotel!.currency)
                  : null,
            ),
            const SizedBox(height: 10),
          ],

          // Duration & travelers
          _summaryRow(tm,
            icon: Icons.calendar_today_outlined,
            title: 'Duration',
            subtitle: '${summary?.durationDays ?? '?'} day${(summary?.durationDays ?? 0) != 1 ? 's' : ''}',
            trailing: summary?.travelers != null && summary!.travelers > 1
                ? '${summary.travelers} traveler${summary.travelers > 1 ? 's' : ''}'
                : null,
          ),
        ],
      ),
    );
  }

  Widget _summaryRow(TourMateColors tm, {
    required IconData icon,
    required String title,
    required String subtitle,
    String? subtitle2,
    String? trailing,
  }) {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 18, color: tm.sapphireLight),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: tm.textPrimary,
                ),
              ),
              Text(
                subtitle,
                style: GoogleFonts.inter(
                  fontSize: 12,
                  color: tm.textSecondary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (subtitle2 != null)
                Text(
                  subtitle2,
                  style: GoogleFonts.inter(
                    fontSize: 11,
                    color: tm.textTertiary,
                  ),
                ),
            ],
          ),
        ),
        if (trailing != null)
          Text(
            trailing,
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: tm.textPrimary,
              letterSpacing: -0.2,
            ),
          ),
      ],
    );
  }

  Widget _buildPricing(TourMateColors tm) {
    final pricing = booking.pricing;
    if (pricing == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.all(Spacing.xl4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Price Breakdown',
            style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700, color: tm.textPrimary),
          ),
          const SizedBox(height: Spacing.md),
          if (pricing.flightCost > 0)
            _pricingRow(tm, 'Flight', pricing.flightCost, pricing.currency),
          if (pricing.hotelCost > 0)
            _pricingRow(tm, 'Hotel (total)', pricing.hotelCost, pricing.currency),
          Container(
            height: 1,
            margin: const EdgeInsets.symmetric(vertical: Spacing.sm),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [tm.divider.withValues(alpha: 0), tm.divider, tm.divider.withValues(alpha: 0)],
              ),
            ),
          ),
          _pricingRow(tm,
            'Total Estimated',
            pricing.totalEstimated,
            pricing.currency,
            bold: true,
          ),
        ],
      ),
    );
  }

  Widget _pricingRow(TourMateColors tm, String label, double amount, String currency, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: bold ? 14 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
              color: bold ? tm.textPrimary : tm.textSecondary,
            ),
          ),
          Text(
            _formatPrice(amount, currency),
            style: GoogleFonts.inter(
              fontSize: bold ? 15 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.w600,
              color: bold ? tm.sapphire : tm.textPrimary,
              letterSpacing: bold ? -0.2 : 0,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, Spacing.xl4),
      child: Column(
        children: [
          // Premium Pay Now button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onPayNow,
              icon: Icon(Icons.lock_rounded, size: 18, color: tm.sapphireLight),
              label: Text(
                'Pay Now',
                style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w700),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: tm.deepNavy,
                foregroundColor: tm.brandWhite,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                  side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                ),
                elevation: 0,
              ),
            ),
          ),
          // Debug: Show if onPayNow is null
          if (onPayNow == null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(
                'DEBUG: onPayNow is null',
                style: GoogleFonts.inter(color: tm.error, fontSize: 10),
              ),
            ),
          const SizedBox(height: 10),
          // Premium Book Later button
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: onLater,
              icon: Icon(Icons.access_time_rounded, size: 18, color: tm.sapphire),
              label: Text(
                'Book Later',
                style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w600),
              ),
              style: OutlinedButton.styleFrom(
                foregroundColor: tm.textSecondary,
                side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3)),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfirmedBanner(TourMateColors tm) {
    return Container(
      padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl3, Spacing.xl4, Spacing.xl4),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(Icons.check_circle, color: tm.sapphireLight, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Booking Confirmed',
                  style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700, color: tm.textPrimary),
                ),
                const SizedBox(height: 2),
                Text(
                  'Your payment was successful and your trip is all set!',
                  style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatPrice(double amount, String currency) {
    final symbol = currency == 'USD' ? '\$' : (currency == 'EUR' ? '€' : '$currency ');
    if (amount == amount.roundToDouble()) {
      return '$symbol${amount.toInt()}';
    }
    return '$symbol${amount.toStringAsFixed(2)}';
  }
}
