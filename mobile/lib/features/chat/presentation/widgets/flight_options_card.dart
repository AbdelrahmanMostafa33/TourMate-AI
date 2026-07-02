import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../flights/data/models/flight_offer.dart';
import '../../data/models/flight_options_payload.dart';

/// Displays a list of flight options with airline, route, times, and pricing.
/// Each option has a "Select" button so the user can pick a flight.
class FlightOptionsCard extends StatelessWidget {
  final FlightOptionsPayload payload;
  final void Function(FlightOffer offer)? onSelectFlight;

  const FlightOptionsCard({
    super.key,
    required this.payload,
    this.onSelectFlight,
  });

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl4),
        border: Border.all(color: tm.borderLight),
        boxShadow: [
          BoxShadow(
            color: tm.deepNavy.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Premium Header ──────────────────────────
          _buildHeader(tm),
          Container(height: 1, color: tm.divider),

          // ── Flight Offers ───────────────────────────
          ...List.generate(payload.offers.length, (i) {
            return _FlightOfferCard(
              offer: payload.offers[i],
              number: i + 1,
              onSelect: onSelectFlight != null
                  ? () => onSelectFlight!(payload.offers[i])
                  : null,
            );
          }),

          // ── Bottom padding ──────────────────────────
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildHeader(TourMateColors tm) {
    return Container(
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
            child: Icon(Icons.flight_takeoff_rounded, color: tm.sapphireLight, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Available Flights',
                  style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
                ),
                const SizedBox(height: 2),
                Text(
                  '${payload.offers.length} option${payload.offers.length > 1 ? 's' : ''} found',
                  style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary, fontWeight: FontWeight.w500),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Single Flight Offer Card ─────────────────────────────────────────────

class _FlightOfferCard extends StatelessWidget {
  final FlightOffer offer;
  final int number;
  final VoidCallback? onSelect;

  const _FlightOfferCard({
    required this.offer,
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
        child: Material(
          color: tm.surface,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          child: InkWell(
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            onTap: onSelect,
            child: Container(
              padding: const EdgeInsets.all(Spacing.xl3),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                border: Border.all(color: tm.borderLight),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Top row: badge + airline + price ──
                  Row(
                    children: [
                      // Gold number badge
                      Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          '$number',
                          style: GoogleFonts.inter(color: tm.sapphireLight, fontSize: 13, fontWeight: FontWeight.w800),
                        ),
                      ),
                      const SizedBox(width: 10),
                      // Airline + flight number
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              offer.airline,
                              style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700, color: tm.textPrimary),
                            ),
                            if (offer.flightNumber.isNotEmpty)
                              Text(
                                'Flight ${offer.flightNumber}',
                                style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
                              ),
                          ],
                        ),
                      ),
                      // Gold price
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: tm.sapphire.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
                        ),
                        child: Text(
                          offer.priceFormatted,
                          style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w700, color: tm.sapphire),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: Spacing.md),

                  // ── Route timeline ──────────────────────────
                  Row(
                    children: [
                      // Departure
                      Expanded(
                        child: _timeStation(tm,
                          time: offer.departureAtFormatted,
                          iata: offer.originIata,
                          label: 'Departure',
                          alignLeft: true,
                        ),
                      ),

                      // Gold flight line
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        child: Column(
                          children: [
                            Icon(Icons.flight_rounded, size: 16, color: tm.sapphire),
                            if (offer.duration != null)
                              Text(
                                offer.duration!,
                                style: GoogleFonts.inter(fontSize: 10, color: tm.textTertiary),
                              ),
                          ],
                        ),
                      ),

                      // Arrival
                      Expanded(
                        child: _timeStation(tm,
                          time: offer.arrivalAtFormatted,
                          iata: offer.destinationIata,
                          label: 'Arrival',
                          alignLeft: false,
                        ),
                      ),
                    ],
                  ),

                  // ── sapphire-accented stops / cabin info ────────
                  if (offer.stops != null || offer.cabin != null) ...[
                    const SizedBox(height: Spacing.sm),
                    Row(
                      children: [
                        if (offer.stops != null)
                          _infoChip(
                            offer.stops == 0 ? 'Non-stop' : '${offer.stops} stop${offer.stops! > 1 ? 's' : ''}',
                            Icons.flight,
                            tm.sapphire,
                          ),
                        if (offer.cabin != null && offer.cabin!.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(left: 6),
                            child: _infoChip(
                              offer.cabin!,
                              Icons.airline_seat_recline_normal,
                              tm.sapphire,
                            ),
                          ),
                      ],
                    ),
                  ],

                  // ── Gold Select button ───────────────────────
                  if (onSelect != null) ...[
                    const SizedBox(height: Spacing.md),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: onSelect,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: tm.deepNavy,
                          foregroundColor: tm.brandWhite,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(RadiusTokens.md),
                            side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                          ),
                          elevation: 0,
                        ),
                        child: Text(
                          'Select Flight $number',
                          style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _timeStation(TourMateColors tm, {
    required String time,
    required String iata,
    required String label,
    required bool alignLeft,
  }) {
    return Column(
      crossAxisAlignment: alignLeft ? CrossAxisAlignment.start : CrossAxisAlignment.end,
      children: [
        Text(
          time.isNotEmpty ? time : '--:--',
          style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w700, color: tm.textPrimary),
        ),
        const SizedBox(height: 2),
        Text(
          iata.isNotEmpty ? iata : '---',
          style: GoogleFonts.inter(fontSize: 12, color: tm.textSecondary, fontWeight: FontWeight.w600),
        ),
        Text(
          label,
          style: GoogleFonts.inter(fontSize: 10, color: tm.textTertiary),
        ),
      ],
    );
  }

  Widget _infoChip(String label, IconData icon, Color accent) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accent.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: accent),
          const SizedBox(width: 4),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 11, color: accent, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
