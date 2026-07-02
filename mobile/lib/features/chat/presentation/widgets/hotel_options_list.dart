import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/models/hotel_option.dart';

/// Displays a list of hotel options that arrive after the user approves
/// the itinerary. Each option has a select button matching BookingCard style.
class HotelOptionsList extends StatelessWidget {
  final HotelOptionsPayload payload;
  final void Function(HotelOption hotel)? onSelectHotel;

  const HotelOptionsList({
    super.key,
    required this.payload,
    this.onSelectHotel,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.pureWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.pureBlack.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Premium Header ───────────────────────────
          Container(
            padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl4, Spacing.xl4, Spacing.xl3),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0A0A0A), Color(0xFF1A1A1A)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
                  ),
                  child: Icon(Icons.hotel_rounded, color: tm.goldLight, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Where to Stay',
                        style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
                      ),
                      Text(
                        '${payload.options.length} option${payload.options.length > 1 ? 's' : ''} available',
                        style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary, fontWeight: FontWeight.w500),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // ── Premium Hotel Option Cards ────────────────
          ...List.generate(payload.options.length, (i) {
            return _HotelOptionCard(
              hotel: payload.options[i],
              number: i + 1,
              onSelect: onSelectHotel != null
                  ? () => onSelectHotel!(payload.options[i])
                  : null,
            );
          }),

          const SizedBox(height: 12),
        ],
      ),
    );
  }
}

class _HotelOptionCard extends StatelessWidget {
  final HotelOption hotel;
  final int number;
  final VoidCallback? onSelect;

  const _HotelOptionCard({
    required this.hotel,
    required this.number,
    this.onSelect,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4),
      child: Padding(
        padding: const EdgeInsets.only(bottom: Spacing.sm),
        child: Container(
          padding: const EdgeInsets.all(Spacing.xl3),
          decoration: BoxDecoration(
            color: tm.surface,
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            border: Border.all(color: tm.borderLight),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Top row: gold badge + name + rating ──
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Gold number badge
                  Container(
                    width: 28,
                    height: 28,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF0A0A0A), Color(0xFF1A1A1A)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
                    ),
                    alignment: Alignment.center,
                    child: Text(
                      '$number',
                      style: GoogleFonts.inter(color: tm.goldLight, fontSize: 13, fontWeight: FontWeight.w800),
                    ),
                  ),
                  const SizedBox(width: 10),
                  // Name
                  Expanded(
                    child: Text(
                      hotel.name,
                      style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w700, color: tm.textPrimary),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  // Gold rating
                  if (hotel.rating != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: tm.gold.withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: tm.gold.withValues(alpha: 0.2)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.star_rounded, size: 14, color: tm.gold),
                          const SizedBox(width: 2),
                          Text(
                            hotel.rating!.toStringAsFixed(1),
                            style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700, color: tm.gold),
                          ),
                        ],
                      ),
                    ),
                ],
              ),

              const SizedBox(height: Spacing.sm),

              // ── Gold-accented Type + Price + Distance ────
              Row(
                children: [
                  if (hotel.accommodationType.isNotEmpty)
                    _goldChip(tm, hotel.accommodationType, Icons.home_outlined),
                  if (hotel.pricePerNight != null) ...[
                    const SizedBox(width: 6),
                    _goldChip(
                      tm,
                      '${_formatPrice(hotel.pricePerNight!)}${hotel.currency != null ? ' ${hotel.currency}' : ''}/night',
                      Icons.attach_money,
                    ),
                  ],
                  if (hotel.distanceFromCenter != null) ...[
                    const SizedBox(width: 6),
                    _goldChip(
                      tm,
                      '${hotel.distanceFromCenter!.toStringAsFixed(1)} km',
                      Icons.location_on_outlined,
                    ),
                  ],
                ],
              ),

              // ── Description ──────────────────────────────
              if (hotel.description.isNotEmpty) ...[
                const SizedBox(height: Spacing.sm),
                Text(
                  hotel.description,
                  style: GoogleFonts.inter(fontSize: 12, color: tm.textSecondary, height: 1.4),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],

              // ── Gold-accented Amenities ───────────────────
              if (hotel.amenities.isNotEmpty) ...[
                const SizedBox(height: Spacing.sm),
                Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  children: hotel.amenities.take(5).map((amenity) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: tm.gold.withValues(alpha: 0.06),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: tm.gold.withValues(alpha: 0.12)),
                      ),
                      child: Text(
                        amenity,
                        style: GoogleFonts.inter(fontSize: 10, color: tm.gold, fontWeight: FontWeight.w500),
                      ),
                    );
                  }).toList(),
                ),
              ],

              // ── Gold Select button ────────────────────────
              if (onSelect != null) ...[
                const SizedBox(height: Spacing.md),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: onSelect,
                    icon: Icon(Icons.check_circle_outline, size: 18, color: tm.goldLight),
                    label: Text(
                      'Select Hotel $number',
                      style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: tm.pureBlack,
                      foregroundColor: tm.pureWhite,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(RadiusTokens.md),
                        side: BorderSide(color: tm.gold.withValues(alpha: 0.3), width: 0.5),
                      ),
                      elevation: 0,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _goldChip(TourMateColors tm, String label, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: tm.gold.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: tm.gold.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: tm.gold),
          const SizedBox(width: 4),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 11, color: tm.gold, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  String _formatPrice(double price) {
    if (price == price.roundToDouble()) {
      return '\$${price.toInt()}';
    }
    return '\$${price.toStringAsFixed(2)}';
  }
}
