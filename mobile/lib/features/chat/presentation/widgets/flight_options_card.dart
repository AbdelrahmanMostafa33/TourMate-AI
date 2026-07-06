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

  /// Build a trip info string like "Round-trip · 3 options · Jul 28 → Jul 31"
  String get _tripInfo {
    final parts = <String>[];
    if (payload.tripType != null && payload.tripType!.isNotEmpty) {
      parts.add(payload.tripType!.replaceAll('-', ' ').split(' ').map((w) => w.isNotEmpty ? '${w[0].toUpperCase()}${w.substring(1)}' : '').join(' '));
    }
    parts.add('${payload.offers.length} option${payload.offers.length > 1 ? 's' : ''} found');
    if (payload.departureDate != null && payload.departureDate!.isNotEmpty) {
      final dep = payload.departureDate!;
      if (payload.returnDate != null && payload.returnDate!.isNotEmpty) {
        parts.add('$dep → ${payload.returnDate}');
      } else {
        parts.add(dep);
      }
    }
    if (payload.cabinClass != null && payload.cabinClass!.isNotEmpty) {
      parts.add(payload.cabinClass!.replaceAll('_', ' ').split(' ').map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1).toLowerCase()}').join(' '));
    }
    if (payload.durationDays != null && payload.durationDays! > 0) {
      parts.add('${payload.durationDays} day${payload.durationDays! > 1 ? 's' : ''}');
    }
    return parts.join(' · ');
  }

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
              tripType: payload.tripType,
              onSelect: onSelectFlight != null
                  ? () => onSelectFlight!(payload.offers[i])
                  : null,
            );
          }),

          // ── Bottom padding ──────────────────────────
          const SizedBox(height: Spacing.xl),
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
            padding: const EdgeInsets.all(Spacing.md),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(RadiusTokens.xl),
              border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
            ),
            child: Icon(Icons.flight_takeoff_rounded, color: tm.sapphireLight, size: 22),
          ),
          const SizedBox(width: Spacing.xl2),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Available Flights',
                  style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
                ),
                const SizedBox(height: Spacing.xxs),
                Text(
                  _tripInfo,
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
  final String? tripType;
  final VoidCallback? onSelect;

  const _FlightOfferCard({
    required this.offer,
    required this.number,
    this.tripType,
    this.onSelect,
  });

  /// Format trip type for display ("one-way" → "One Way", "round-trip" → "Round Trip")
  String get _formattedTripType {
    if (tripType == null || tripType!.isEmpty) return '';
    return tripType!.replaceAll('-', ' ').split(' ').map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1)}').join(' ');
  }

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
                          borderRadius: BorderRadius.circular(RadiusTokens.md),
                          border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          '$number',
                          style: GoogleFonts.inter(color: tm.sapphireLight, fontSize: 13, fontWeight: FontWeight.w800),
                        ),
                      ),
                      const SizedBox(width: Spacing.lg),
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
                        padding: const EdgeInsets.symmetric(horizontal: Spacing.lg, vertical: Spacing.sm),
                        decoration: BoxDecoration(
                          color: tm.sapphire.withValues(alpha: 0.08),
                          borderRadius: BorderRadius.circular(RadiusTokens.xl4),
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
                        padding: const EdgeInsets.symmetric(horizontal: Spacing.md),
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

                  // ── Return segment (round-trip only) ────────────────────
                  if (offer.returnSegments.isNotEmpty) ...[
                    const SizedBox(height: Spacing.lg),
                    Container(height: 1, color: tm.divider.withValues(alpha: 0.5)),
                    const SizedBox(height: Spacing.lg),

                    // Return header
                    Row(
                      children: [
                        Icon(Icons.flight_land_rounded, size: 16, color: tm.sapphire),
                        const SizedBox(width: Spacing.sm),
                        Text(
                          'Return',
                          style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w700, color: tm.textSecondary, letterSpacing: 0.5),
                        ),
                      ],
                    ),
                    const SizedBox(height: Spacing.md),

                    // Return route timeline
                    ...offer.returnSegments.map((seg) {
                      final rOrigin = (seg['origin_iata'] ?? '').toString();
                      final rDest = (seg['destination_iata'] ?? '').toString();
                      final rDepTime = (seg['departure_at_formatted'] ?? '').toString();
                      final rArrTime = (seg['arrival_at_formatted'] ?? '').toString();
                      final rFlight = (seg['flight_number'] ?? '').toString();
                      final rAirline = (seg['airline_code'] ?? '').toString();
                      final rDuration = (seg['duration'] ?? '').toString();
                      return Padding(
                        padding: const EdgeInsets.only(bottom: Spacing.sm),
                        child: Row(
                          children: [
                            Expanded(
                              child: _timeStation(tm,
                                time: rDepTime,
                                iata: rOrigin,
                                label: 'Departure',
                                alignLeft: true,
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: Spacing.md),
                              child: Column(
                                children: [
                                  Icon(Icons.flight_rounded, size: 14, color: tm.sapphire.withValues(alpha: 0.7)),
                                  if (rDuration.isNotEmpty && rDuration != 'PT')
                                    Text(
                                      rDuration.replaceAll('PT', '').replaceAll('H', 'h ').replaceAll('M', 'm'),
                                      style: GoogleFonts.inter(fontSize: 10, color: tm.textTertiary),
                                    ),
                                ],
                              ),
                            ),
                            Expanded(
                              child: _timeStation(tm,
                                time: rArrTime,
                                iata: rDest,
                                label: 'Arrival',
                                alignLeft: false,
                              ),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],

                  // ── Trip type / stops / cabin info chips ────────
                  if (_formattedTripType.isNotEmpty || offer.stops != null || offer.cabin != null) ...[
                    const SizedBox(height: Spacing.sm),
                    Row(
                      children: [
                        if (_formattedTripType.isNotEmpty)
                          _infoChip(
                            _formattedTripType,
                            Icons.flight_takeoff_rounded,
                            tm.sapphire,
                          ),
                        if (offer.stops != null)
                          Padding(
                            padding: EdgeInsets.only(left: _formattedTripType.isNotEmpty ? Spacing.sm : 0),
                            child: _infoChip(
                              offer.stops == 0 ? 'Non-stop' : '${offer.stops} stop${offer.stops! > 1 ? 's' : ''}',
                              Icons.flight,
                              tm.sapphire,
                            ),
                          ),
                        if (offer.cabin != null && offer.cabin!.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(left: Spacing.sm),
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
                          padding: const EdgeInsets.symmetric(vertical: Spacing.xl),
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
        const SizedBox(height: Spacing.xxs),
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
      padding: const EdgeInsets.symmetric(horizontal: Spacing.md, vertical: Spacing.xs),
      decoration: BoxDecoration(
        color: accent.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(RadiusTokens.md),
        border: Border.all(color: accent.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: accent),
          const SizedBox(width: Spacing.xs),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 11, color: accent, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
