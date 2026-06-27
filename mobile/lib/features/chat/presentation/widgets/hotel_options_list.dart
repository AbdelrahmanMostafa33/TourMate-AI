import 'package:flutter/material.dart';
import '../../data/models/hotel_option.dart';

/// Displays a list of hotel options that arrive after the user approves
/// the itinerary. Each option can be tapped to start booking.
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
          Container(
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
                  child: const Icon(Icons.hotel_rounded, color: Colors.white, size: 20),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Hotel Options',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: Colors.black,
                        ),
                      ),
                      Text(
                        '${payload.options.length} option${payload.options.length > 1 ? 's' : ''} available',
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
          ),

          if (payload.message != null && payload.message!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(
                payload.message!,
                style: TextStyle(
                  fontSize: 13,
                  color: Colors.grey[600],
                  height: 1.4,
                ),
              ),
            ),

          const SizedBox(height: 8),

          // ── Hotel Cards ─────────────────────────────
          ...payload.options.map((hotel) => _HotelOptionCard(
                hotel: hotel,
                onSelect: onSelectHotel != null ? () => onSelectHotel!(hotel) : null,
              )),

          const SizedBox(height: 12),
        ],
      ),
    );
  }
}

class _HotelOptionCard extends StatelessWidget {
  final HotelOption hotel;
  final VoidCallback? onSelect;

  const _HotelOptionCard({
    required this.hotel,
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
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Thumbnail / Icon ──────────────
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [Colors.green.shade400, Colors.teal.shade400],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    alignment: Alignment.center,
                    child: const Icon(
                      Icons.bed_rounded,
                      color: Colors.white,
                      size: 26,
                    ),
                  ),
                  const SizedBox(width: 14),

                  // ── Details ────────────────────────
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          hotel.name,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: Colors.black,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 4),
                        if (hotel.accommodationType.isNotEmpty)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.green.shade100,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              hotel.accommodationType,
                              style: TextStyle(
                                fontSize: 10,
                                color: Colors.green.shade800,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            if (hotel.rating != null) ...[
                              const Icon(Icons.star_rounded, size: 14, color: Colors.amber),
                              const SizedBox(width: 2),
                              Text(
                                hotel.rating!.toStringAsFixed(1),
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.amber[800],
                                ),
                              ),
                              const SizedBox(width: 10),
                            ],
                            if (hotel.pricePerNight != null) ...[
                              Icon(Icons.attach_money, size: 14, color: Colors.grey[600]),
                              Text(
                                '${_formatPrice(hotel.pricePerNight!)}${hotel.currency != null ? ' ${hotel.currency}' : ''}/night',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[600],
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                            if (hotel.distanceFromCenter != null) ...[
                              const SizedBox(width: 10),
                              Icon(Icons.near_me, size: 14, color: Colors.grey[400]),
                              Text(
                                '${hotel.distanceFromCenter!.toStringAsFixed(1)} km',
                                style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                              ),
                            ],
                          ],
                        ),
                        if (hotel.description.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            hotel.description,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                              height: 1.3,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                        if (hotel.amenities.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 4,
                            runSpacing: 4,
                            children: hotel.amenities.take(4).map((amenity) {
                              return Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.grey.shade200,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  amenity,
                                  style: TextStyle(
                                    fontSize: 9,
                                    color: Colors.grey[700],
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              );
                            }).toList(),
                          ),
                        ],
                      ],
                    ),
                  ),

                  // ── Select chevron ──────────────────
                  if (onSelect != null)
                    Container(
                      margin: const EdgeInsets.only(left: 4),
                      child: Icon(Icons.chevron_right, color: Colors.grey[300], size: 20),
                    ),
                ],
              ),
            ),
          ),
        ),
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
