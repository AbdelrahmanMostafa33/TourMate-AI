import 'package:flutter/material.dart';
import '../../data/models/itinerary_data.dart';

class ItineraryCard extends StatelessWidget {
  final ItineraryData itinerary;

  const ItineraryCard({super.key, required this.itinerary});

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
          // ── Header ─────────────────────────────────────
          _buildHeader(),
          const Divider(height: 1),

          // ── Days ────────────────────────────────────────
          ...itinerary.days.map((day) => _DaySection(day: day)),

          // ── Hotels Section ───────────────────────────────
          ..._buildHotelsSection(),

          // ── Accommodation ───────────────────────────────
          if (itinerary.accommodationSuggestions.isNotEmpty) ...[
            const Divider(height: 1),
            _AccommodationSection(
              suggestions: itinerary.accommodationSuggestions,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
      decoration: const BoxDecoration(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.black,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.map_rounded, color: Colors.white, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  itinerary.destination,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Colors.black,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${itinerary.days.length} day${itinerary.days.length > 1 ? 's' : ''} • ${itinerary.totalStops} stop${itinerary.totalStops > 1 ? 's' : ''}',
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[500],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.green.shade50,
              borderRadius: BorderRadius.circular(20),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.check_circle, size: 14, color: Colors.green[600]),
                const SizedBox(width: 4),
                Text(
                  'AI Planned',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.green[700],
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

  List<Widget> _buildHotelsSection() {
    final allHotelStops = itinerary.days
        .expand((day) => day.stops)
        .where((s) => s.category.toLowerCase() == 'hotel' || s.category.toLowerCase() == 'accommodation')
        .toList();
    
    if (allHotelStops.isEmpty) return [];
    
    return [
      const SizedBox(height: 8),
      _HotelSection(hotels: allHotelStops),
    ];
  }
}

// ── Day Section ─────────────────────────────────────────────────────────────

class _DaySection extends StatelessWidget {
  final ItineraryDay day;

  const _DaySection({required this.day});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 16),

          // Day header
          Row(
            children: [
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${day.dayNumber}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Day ${day.dayNumber}',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.black,
                      ),
                    ),
                    if (day.theme.isNotEmpty)
                      Text(
                        day.theme,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[500],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                  ],
                ),
              ),
              if (day.totalTravelTimeMinutes != null && day.totalTravelTimeMinutes! > 0)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.orange.shade50,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '🚗 ${day.totalTravelTimeMinutes!.toInt()} min',
                    style: TextStyle(
                      fontSize: 11,
                      color: Colors.orange[700],
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),

          const SizedBox(height: 12),

          // Stops timeline
          ...List.generate(day.stops.length, (i) {
            final stop = day.stops[i];
            final isLast = i == day.stops.length - 1;
            return _StopTimelineItem(
              stop: stop,
              isLast: isLast,
              showTravel: !isLast &&
                  stop.travelTimeToNextMinutes != null &&
                  stop.travelTimeToNextMinutes! > 0,
            );
          }),

          const SizedBox(height: 16),
        ],
      ),
    );
  }

}

// ── Stop Timeline Item ──────────────────────────────────────────────────────

class _StopTimelineItem extends StatelessWidget {
  final ItineraryStop stop;
  final bool isLast;
  final bool showTravel;

  const _StopTimelineItem({
    required this.stop,
    required this.isLast,
    required this.showTravel,
  });

  @override
  Widget build(BuildContext context) {
    final timeColor = _timeColor(stop.suggestedTimeOfDay);
    final timeEmoji = _timeEmoji(stop.suggestedTimeOfDay);
    final timeLabel = _timeLabel(stop.suggestedTimeOfDay);

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Timeline column ──────────────────────────
          SizedBox(
            width: 28,
            child: Column(
              children: [
                const SizedBox(height: 4),
                // Dot
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: timeColor,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 2),
                    boxShadow: [
                      BoxShadow(
                        color: timeColor.withValues(alpha: 0.3),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                ),
                // Connecting line
                if (!isLast)
                  Expanded(
                    child: Container(
                      width: 2,
                      color: Colors.grey.shade200,
                    ),
                  ),
              ],
            ),
          ),

          // ── Stop content ─────────────────────────────
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 8),
              child: GestureDetector(
                onTap: () {
                  if (stop.id.isNotEmpty) {
                    Navigator.of(context).pushNamed(
                      '/place-detail',
                      arguments: stop.id,
                    );
                  }
                },
                child: Container(
                  margin: const EdgeInsets.only(left: 8, bottom: 4),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Name + time
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              stop.name,
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: Colors.black,
                              ),
                            ),
                          ),
                          if (timeLabel.isNotEmpty)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: timeColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(
                                '$timeEmoji $timeLabel',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: timeColor,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                        ],
                      ),

                      const SizedBox(height: 6),

                      // Metadata row
                      Wrap(
                        spacing: 6,
                        runSpacing: 4,
                        children: [
                          if (stop.estimatedDurationMinutes > 0)
                            _metadataChip(
                              '⏱ ${stop.estimatedDurationMinutes} min',
                              Colors.blue.shade50,
                              Colors.blue.shade700,
                            ),
                          if (stop.category.isNotEmpty)
                            _metadataChip(
                              stop.category,
                              Colors.purple.shade50,
                              Colors.purple.shade700,
                            ),
                          if (stop.rating != null)
                            _metadataChip(
                              '⭐ ${stop.rating!.toStringAsFixed(1)}',
                              Colors.amber.shade50,
                              Colors.amber.shade800,
                            ),
                        ],
                      ),

                      // Why recommended
                      if (stop.whyRecommended.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Text(
                          stop.whyRecommended,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                            height: 1.3,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],

                      // Address
                      if (stop.address != null && stop.address!.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(
                              Icons.location_on_outlined,
                              size: 12,
                              color: Colors.grey[400],
                            ),
                            const SizedBox(width: 3),
                            Expanded(
                              child: Text(
                                stop.address!,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey[400],
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _metadataChip(String label, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 10,
          color: fg,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Color _timeColor(String tod) {
    switch (tod.toLowerCase()) {
      case 'morning':
        return const Color(0xFFFFB74D); // amber
      case 'afternoon':
        return const Color(0xFFFF8A65); // deep orange
      case 'evening':
        return const Color(0xFF7E57C2); // deep purple
      default:
        return Colors.grey;
    }
  }

  String _timeEmoji(String tod) {
    switch (tod.toLowerCase()) {
      case 'morning':
        return '🌅';
      case 'afternoon':
        return '☀️';
      case 'evening':
        return '🌙';
      default:
        return '📍';
    }
  }

  String _timeLabel(String tod) {
    switch (tod.toLowerCase()) {
      case 'morning':
        return 'Morning';
      case 'afternoon':
        return 'Afternoon';
      case 'evening':
        return 'Evening';
      default:
        return '';
    }
  }
}

// ── Hotel Section ────────────────────────────────────────────────────────

class _HotelSection extends StatelessWidget {
  final List<ItineraryStop> hotels;

  const _HotelSection({required this.hotels});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.indigo.shade50, Colors.purple.shade50],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.indigo.shade200, width: 1.5),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.indigo.withValues(alpha: 0.1),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Icon(Icons.hotel_rounded, size: 18, color: Colors.indigo.shade700),
                ),
                const SizedBox(width: 10),
                Text(
                  'Where You\'ll Stay',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Colors.indigo.shade900,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ...hotels.map((hotel) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: GestureDetector(
                    onTap: () {
                      if (hotel.id.isNotEmpty) {
                        Navigator.of(context).pushNamed(
                          '/place-detail',
                          arguments: hotel.id,
                        );
                      }
                    },
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.04),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Row(
                        children: [
                          Container(
                            width: 44,
                            height: 44,
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [Colors.indigo.shade400, Colors.purple.shade400],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            alignment: Alignment.center,
                            child: const Icon(
                              Icons.bed_rounded,
                              color: Colors.white,
                              size: 22,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  hotel.name,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.black,
                                  ),
                                ),
                                const SizedBox(height: 3),
                                Row(
                                  children: [
                                    if (hotel.subCategory.isNotEmpty)
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.indigo.shade100,
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Text(
                                          hotel.subCategory,
                                          style: TextStyle(
                                            fontSize: 10,
                                            color: Colors.indigo.shade700,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                    if (hotel.rating != null) ...[
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                        decoration: BoxDecoration(
                                          color: Colors.amber.shade50,
                                          borderRadius: BorderRadius.circular(6),
                                        ),
                                        child: Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Text(
                                              '⭐',
                                              style: TextStyle(
                                                fontSize: 9,
                                                color: Colors.amber[700],
                                              ),
                                            ),
                                            const SizedBox(width: 2),
                                            Text(
                                              hotel.rating!.toStringAsFixed(1),
                                              style: TextStyle(
                                                fontSize: 10,
                                                color: Colors.amber[800],
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ],
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: Colors.indigo.shade50,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(
                              Icons.chevron_right,
                              color: Colors.indigo.shade400,
                              size: 20,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                )),
          ],
        ),
      ),
    );
  }
}

// ── Accommodation Section ───────────────────────────────────────────────────

class _AccommodationSection extends StatelessWidget {
  final List<AccommodationSuggestion> suggestions;

  const _AccommodationSection({required this.suggestions});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.bed_outlined, size: 18, color: Colors.black),
              const SizedBox(width: 8),
              const Text(
                'Accommodation',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: Colors.black,
                ),
              ),
              const Spacer(),
              Text(
                '${suggestions.length} option${suggestions.length > 1 ? 's' : ''}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.grey[500],
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...suggestions.map((hotel) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.indigo.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.indigo.shade100),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 40,
                        height: 40,
                        decoration: BoxDecoration(
                          color: Colors.indigo.shade100,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        alignment: Alignment.center,
                        child: const Icon(
                          Icons.bed_outlined,
                          color: Colors.indigo,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              hotel.name,
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: Colors.black,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Row(
                              children: [
                                if (hotel.accommodationType.isNotEmpty)
                                  Text(
                                    hotel.accommodationType,
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.grey[600],
                                    ),
                                  ),
                                if (hotel.rating != null) ...[
                                  const SizedBox(width: 6),
                                  Text(
                                    '⭐ ${hotel.rating!.toStringAsFixed(1)}',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.amber[800],
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ),
                      ),
                      Icon(
                        Icons.chevron_right,
                        color: Colors.grey[400],
                        size: 18,
                      ),
                    ],
                  ),
                ),
              )),
        ],
      ),
    );
  }
}

// ── Helper extension ─────────────────────────────────────────────────────────

extension ItineraryDataStats on ItineraryData {
  int get totalStops {
    return days.fold(0, (sum, day) => sum + day.stops.length);
  }
}
