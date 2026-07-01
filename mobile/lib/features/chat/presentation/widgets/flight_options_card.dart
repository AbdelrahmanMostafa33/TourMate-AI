import 'package:flutter/material.dart';
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
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.grey.shade200),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────
          _buildHeader(),
          const Divider(height: 1),

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

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF3B82F6), Color(0xFF2563EB)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.flight_takeoff_rounded,
                color: Colors.white, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Available Flights',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Colors.black,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${payload.offers.length} option${payload.offers.length > 1 ? 's' : ''} found',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[500],
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
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Material(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(14),
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: onSelect,
            child: Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Top row: number badge + airline + price ──
                  Row(
                    children: [
                      // Number badge
                      Container(
                        width: 28,
                        height: 28,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF3B82F6), Color(0xFF2563EB)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          '$number',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                          ),
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
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w700,
                                color: Colors.black,
                              ),
                            ),
                            if (offer.flightNumber.isNotEmpty)
                              Text(
                                'Flight ${offer.flightNumber}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey[500],
                                ),
                              ),
                          ],
                        ),
                      ),
                      // Price
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: Colors.blue.shade50,
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          offer.priceFormatted,
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: Colors.blue[700],
                          ),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: 12),

                  // ── Route timeline ──────────────────────────
                  Row(
                    children: [
                      // Departure
                      Expanded(
                        child: _timeStation(
                          time: offer.departureAtFormatted,
                          iata: offer.originIata,
                          label: 'Departure',
                          alignLeft: true,
                        ),
                      ),

                      // Flight line
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        child: Column(
                          children: [
                            Icon(Icons.flight_rounded,
                                size: 16, color: Colors.blue[400]),
                            if (offer.duration != null)
                              Text(
                                offer.duration!,
                                style: TextStyle(
                                  fontSize: 10,
                                  color: Colors.grey[500],
                                ),
                              ),
                          ],
                        ),
                      ),

                      // Arrival
                      Expanded(
                        child: _timeStation(
                          time: offer.arrivalAtFormatted,
                          iata: offer.destinationIata,
                          label: 'Arrival',
                          alignLeft: false,
                        ),
                      ),
                    ],
                  ),

                  // ── Stops / cabin info ───────────────────────
                  if (offer.stops != null || offer.cabin != null) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        if (offer.stops != null)
                          _infoChip(
                            offer.stops == 0
                                ? '✈️ Non-stop'
                                : '🔄 ${offer.stops} stop${offer.stops! > 1 ? 's' : ''}',
                            Colors.green.shade50,
                            Colors.green.shade700,
                          ),
                        if (offer.cabin != null && offer.cabin!.isNotEmpty)
                          Padding(
                            padding:
                                const EdgeInsets.only(left: 6),
                            child: _infoChip(
                              offer.cabin!,
                              Colors.orange.shade50,
                              Colors.orange.shade700,
                            ),
                          ),
                      ],
                    ),
                  ],

                  // ── Select button ────────────────────────────
                  if (onSelect != null) ...[
                    const SizedBox(height: 12),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: onSelect,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF3B82F6),
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12),
                          ),
                          elevation: 0,
                        ),
                        child: Text(
                          'Select Flight $number',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                          ),
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

  Widget _timeStation({
    required String time,
    required String iata,
    required String label,
    required bool alignLeft,
  }) {
    return Column(
      crossAxisAlignment:
          alignLeft ? CrossAxisAlignment.start : CrossAxisAlignment.end,
      children: [
        Text(
          time.isNotEmpty ? time : '--:--',
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w700,
            color: Colors.black,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          iata.isNotEmpty ? iata : '---',
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[600],
            fontWeight: FontWeight.w600,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontSize: 10,
            color: Colors.grey[400],
          ),
        ),
      ],
    );
  }

  Widget _infoChip(String label, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          color: fg,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
