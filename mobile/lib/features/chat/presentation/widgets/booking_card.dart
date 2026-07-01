import 'package:flutter/material.dart';
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
    final isConfirmed = booking.isConfirmed;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isConfirmed ? Colors.green.shade300 : Colors.grey.shade200,
        ),
        boxShadow: [
          BoxShadow(
            color: isConfirmed
                ? Colors.green.withValues(alpha: 0.08)
                : Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ─────────────────────────────────────
          _buildHeader(isConfirmed),
          const Divider(height: 1),

          // ── Trip Summary ───────────────────────────────
          _buildTripSummary(),
          if (isConfirmed) ...[
            const Divider(height: 1),
            _buildConfirmedBanner(),
          ] else ...[
            const Divider(height: 1),
            // ── Pricing Breakdown ────────────────────────
            _buildPricing(),
            const Divider(height: 1),
            // ── Action Buttons ───────────────────────────
            _buildActions(context),
          ],
        ],
      ),
    );
  }

  Widget _buildHeader(bool isConfirmed) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF22C55E), Color(0xFF16A34A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.check_circle_rounded, color: Colors.white, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isConfirmed ? '✅ Booking Confirmed!' : 'Trip Confirmed!',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Colors.black,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  booking.tripSummary?.destination ?? 'Your trip',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[500],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          if (booking.pricing != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.green.shade50,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                _formatPrice(booking.pricing!.totalEstimated, booking.pricing!.currency),
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: Colors.green[700],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildTripSummary() {
    final summary = booking.tripSummary;
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Trip Summary',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: Colors.black,
            ),
          ),
          const SizedBox(height: 12),

          // Flight info
          if (booking.flight != null && booking.hasFlight) ...[
            _summaryRow(
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

          // Hotel info
          if (booking.hotel != null && booking.hasHotel) ...[
            _summaryRow(
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
          _summaryRow(
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

  Widget _summaryRow({
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
            color: Colors.grey.shade100,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 18, color: Colors.grey[700]),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.black,
                ),
              ),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[600],
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              if (subtitle2 != null)
                Text(
                  subtitle2,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[400],
                  ),
                ),
            ],
          ),
        ),
        if (trailing != null)
          Text(
            trailing,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: Colors.black,
            ),
          ),
      ],
    );
  }

  Widget _buildPricing() {
    final pricing = booking.pricing;
    if (pricing == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Price Breakdown',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: Colors.black,
            ),
          ),
          const SizedBox(height: 12),
          if (pricing.flightCost > 0)
            _pricingRow('Flight', pricing.flightCost, pricing.currency),
          if (pricing.hotelCost > 0)
            _pricingRow('Hotel (total)', pricing.hotelCost, pricing.currency),
          const Divider(height: 16),
          _pricingRow(
            'Total Estimated',
            pricing.totalEstimated,
            pricing.currency,
            bold: true,
          ),
        ],
      ),
    );
  }

  Widget _pricingRow(String label, double amount, String currency, {bool bold = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: bold ? 14 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.w500,
              color: bold ? Colors.black : Colors.grey[700],
            ),
          ),
          Text(
            _formatPrice(amount, currency),
            style: TextStyle(
              fontSize: bold ? 15 : 13,
              fontWeight: bold ? FontWeight.w700 : FontWeight.w600,
              color: bold ? Colors.black : Colors.grey[800],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActions(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
      child: Column(
        children: [
          // Pay Now button
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onPayNow,
              icon: const Icon(Icons.lock_rounded, size: 18),
              label: const Text(
                'Pay Now',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                ),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.black,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
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
                style: TextStyle(color: Colors.red, fontSize: 10),
              ),
            ),
          const SizedBox(height: 10),
          // Do it Later button
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: onLater,
              icon: const Icon(Icons.access_time_rounded, size: 18),
              label: const Text(
                'Book Later',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.grey[700],
                side: BorderSide(color: Colors.grey.shade300),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfirmedBanner() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(Icons.check_circle, color: Colors.green[600], size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Booking Confirmed',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Colors.green[800],
                  ),
                ),
                const SizedBox(height: 1),
                Text(
                  'Your payment was successful and your trip is all set!',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.green[600],
                  ),
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
      return '${symbol}${amount.toInt()}';
    }
    return '$symbol${amount.toStringAsFixed(2)}';
  }
}
