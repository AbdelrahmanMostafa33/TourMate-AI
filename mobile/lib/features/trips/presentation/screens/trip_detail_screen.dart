import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' as latlong;
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../data/models/trip_detail_model.dart';
import '../../logic/trip_detail_cubit.dart';
import '../../logic/trip_detail_state.dart';

class TripDetailScreen extends StatefulWidget {
  final String tripId;

  const TripDetailScreen({super.key, required this.tripId});

  @override
  State<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends State<TripDetailScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  int _currentTabIndex = 0;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() {
          _currentTabIndex = _tabController.index;
        });
      }
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) =>
          TripDetailCubit(locator<ApiServices>())..fetchTripDetail(widget.tripId),
      child: Scaffold(
        backgroundColor: Colors.white,
        body: BlocBuilder<TripDetailCubit, TripDetailState>(
          builder: (context, state) {
            return state.when(
              initial: () => const SizedBox(),
              loading: () => const Center(
                child: CircularProgressIndicator(color: Colors.black),
              ),
              error: (message) => _buildError(context, message),
              loaded: (trip) => _buildContent(context, trip),
            );
          },
        ),
      ),
    );
  }

  Widget _buildError(BuildContext context, String message) {
    return SafeArea(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.grey),
              const SizedBox(height: 16),
              const Text(
                'Could not load trip',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                message,
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600], fontSize: 13),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => context
                    .read<TripDetailCubit>()
                    .fetchTripDetail(widget.tripId),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 12,
                  ),
                ),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildContent(BuildContext context, TripDetailModel trip) {
    return CustomScrollView(
      slivers: [
        // ── Sliver App Bar ──────────────────────────────
        _buildSliverAppBar(trip),

        // ── Body ─────────────────────────────────────────
        SliverToBoxAdapter(
          child: Column(
            children: [
              // Trip header card
              _buildTripHeader(trip),

              // Tabs: Itinerary | Map
              if (trip.itineraries.isNotEmpty) ...[
                _buildTabBar(),
                _buildTabContent(trip),
              ] else ...[
                const SizedBox(height: 60),
                _buildEmptyItinerary(),
              ],

              const SizedBox(height: 32),
            ],
          ),
        ),
      ],
    );
  }

  // ── Sliver AppBar ─────────────────────────────────────────────────────────

  Widget _buildSliverAppBar(TripDetailModel trip) {
    return SliverAppBar(
      expandedHeight: 120,
      pinned: true,
      stretch: true,
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.white,
      systemOverlayStyle: const SystemUiOverlayStyle(
        statusBarIconBrightness: Brightness.dark,
      ),
      leading: IconButton(
        icon: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.9),
            shape: BoxShape.circle,
          ),
          child: const Icon(Icons.arrow_back_rounded, color: Colors.black),
        ),
        onPressed: () => Navigator.pop(context),
      ),
      actions: [
        IconButton(
          icon: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.9),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.share_outlined, color: Colors.black, size: 20),
          ),
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Share coming soon')),
            );
          },
        ),
        const SizedBox(width: 8),
      ],
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [
                Colors.grey.shade100,
                Colors.white,
              ],
            ),
          ),
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.only(top: 60, left: 20, right: 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    trip.tripName ?? trip.destination,
                    style: const TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                      color: Colors.black,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.location_on_outlined,
                          size: 14, color: Colors.grey[500]),
                      const SizedBox(width: 4),
                      Text(
                        trip.destination,
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ── Trip Header Card ──────────────────────────────────────────────────────

  Widget _buildTripHeader(TripDetailModel trip) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Column(
          children: [
            // First row: dates & duration
            Row(
              children: [
                _headerInfoChip(
                  Icons.calendar_today_outlined,
                  trip.durationDays > 0
                      ? '${trip.durationDays} day${trip.durationDays > 1 ? 's' : ''}'
                      : 'Flexible',
                ),
                const SizedBox(width: 12),
                if (trip.budget != null)
                  _headerInfoChip(
                    Icons.attach_money,
                    '\$${trip.budget!.toStringAsFixed(0)}',
                  ),
                const Spacer(),
                _statusBadge(trip.status),
              ],
            ),

            if (trip.startDate != null || trip.endDate != null) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  Icon(Icons.date_range_outlined,
                      size: 14, color: Colors.grey[500]),
                  const SizedBox(width: 6),
                  Text(
                    _formatDateRange(trip),
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
            ],

            if (trip.numberOfTravelers > 1) ...[
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(Icons.people_outline,
                      size: 14, color: Colors.grey[500]),
                  const SizedBox(width: 6),
                  Text(
                    '${trip.numberOfTravelers} travelers',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                  ),
                ],
              ),
            ],

            // Quick stats row
            if (trip.itineraries.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Divider(height: 1),
              const SizedBox(height: 12),
              Row(
                children: [
                  _statItem(
                    '${trip.allStops.length}',
                    'Stops',
                    Icons.flag_outlined,
                  ),
                  _statItem(
                    '${trip.durationDays}',
                    'Days',
                    Icons.wb_sunny_outlined,
                  ),
                  _statItem(
                    '${trip.itineraries.length}',
                    'Versions',
                    Icons.layers_outlined,
                  ),
                  _statItem(
                    trip.tripName != null ? 'Named' : 'Auto',
                    'Trip',
                    Icons.auto_awesome_outlined,
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _headerInfoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[600]),
          const SizedBox(width: 4),
          Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  Widget _statusBadge(String status) {
    Color bg;
    Color fg;
    String label;

    switch (status.toLowerCase()) {
      case 'planning':
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade700;
        label = 'Planning';
        break;
      case 'approved':
        bg = Colors.green.shade50;
        fg = Colors.green.shade700;
        label = 'Approved';
        break;
      case 'completed':
        bg = Colors.grey.shade100;
        fg = Colors.grey.shade700;
        label = 'Completed';
        break;
      case 'cancelled':
        bg = Colors.red.shade50;
        fg = Colors.red.shade700;
        label = 'Cancelled';
        break;
      default:
        bg = Colors.orange.shade50;
        fg = Colors.orange.shade700;
        label = status;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: fg,
        ),
      ),
    );
  }

  Widget _statItem(String value, String label, IconData icon) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, size: 18, color: Colors.grey[400]),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: Colors.black,
            ),
          ),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: Colors.grey[500],
            ),
          ),
        ],
      ),
    );
  }

  String _formatDateRange(TripDetailModel trip) {
    try {
      final start = trip.startDate != null
          ? DateTime.parse(trip.startDate!)
          : null;
      final end =
          trip.endDate != null ? DateTime.parse(trip.endDate!) : null;
      final months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ];
      if (start != null && end != null) {
        if (start.month == end.month && start.year == end.year) {
          return '${months[start.month - 1]} ${start.day} – ${end.day}, ${start.year}';
        }
        return '${months[start.month - 1]} ${start.day} – ${months[end.month - 1]} ${end.day}, ${end.year}';
      }
      if (start != null) {
        return 'Starts ${months[start.month - 1]} ${start.day}, ${start.year}';
      }
      return '';
    } catch (_) {
      return '${trip.startDate ?? ''} – ${trip.endDate ?? ''}';
    }
  }

  // ── Empty State ───────────────────────────────────────────────────────────

  Widget _buildEmptyItinerary() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.map_outlined, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          const Text(
            'No itinerary yet',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 8),
          Text(
            'Start a chat to plan this trip',
            style: TextStyle(color: Colors.grey[600]),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pushReplacementNamed(context, '/chat');
            },
            icon: const Icon(Icons.chat_bubble_outline, size: 18),
            label: const Text('Chat with TourMate'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.black,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              padding: const EdgeInsets.symmetric(
                horizontal: 20,
                vertical: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Tab Bar ───────────────────────────────────────────────────────────────

  Widget _buildTabBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(12),
        ),
        child: TabBar(
          controller: _tabController,
          indicator: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(10),
          ),
          labelColor: Colors.white,
          unselectedLabelColor: Colors.grey[600],
          labelStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
          unselectedLabelStyle: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
          indicatorSize: TabBarIndicatorSize.tab,
          dividerColor: Colors.transparent,
          padding: const EdgeInsets.all(4),
          tabs: const [
            Tab(text: '📋  Itinerary'),
            Tab(text: '🗺️  Map'),
          ],
        ),
      ),
    );
  }

  Widget _buildTabContent(TripDetailModel trip) {
    return SizedBox(
      height: _currentTabIndex == 0
          ? _calculateItineraryHeight(trip)
          : MediaQuery.of(context).size.height * 0.65,
      child: TabBarView(
        controller: _tabController,
        children: [
          _buildItineraryTab(trip),
          _buildMapTab(trip),
        ],
      ),
    );
  }

  double _calculateItineraryHeight(TripDetailModel trip) {
    // Rough estimate — enough to avoid overflow in the sliver.
    double height = 0;
    for (final itin in trip.itineraries) {
      for (final day in itin.days) {
        height += 40; // Day header
        height += day.stops.length * 120.0; // ~120 per stop card
        height += 20; // spacing
      }
    }
    return math.max(height, 400);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // ITINERARY TAB
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildItineraryTab(TripDetailModel trip) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: trip.itineraries.map((itin) {
          return _ItineraryTimeline(itinerary: itin);
        }).toList(),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // MAP TAB
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildMapTab(TripDetailModel trip) {
    final stops = trip.stopsWithCoords;

    if (stops.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.map_outlined, size: 48, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text(
              'No location data available',
              style: TextStyle(color: Colors.grey[500]),
            ),
          ],
        ),
      );
    }

    // Calculate center point
    final avgLat =
        stops.fold(0.0, (s, st) => s + st.lat!) / stops.length;
    final avgLon =
        stops.fold(0.0, (s, st) => s + st.lon!) / stops.length;
    final center = latlong.LatLng(avgLat, avgLon);

    return Column(
      children: [
        // Map
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: FlutterMap(
              options: MapOptions(
                initialCenter: center,
                initialZoom: 12,
                minZoom: 4,
                maxZoom: 18,
              ),
              children: [
                TileLayer(
                  urlTemplate:
                      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.tourmate.app',
                ),
                MarkerLayer(
                  markers: stops.asMap().entries.map((entry) {
                    final index = entry.key;
                    final stop = entry.value;
                    return Marker(
                      point: latlong.LatLng(stop.lat!, stop.lon!),
                      width: 40,
                      height: 40,
                      child: _MapMarker(
                        index: index + 1,
                        stop: stop,
                        onTap: () => _showStopInfo(context, stop),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ),

        // Legend / stop list
        Container(
          height: 120,
          width: double.infinity,
          margin: const EdgeInsets.only(top: 8),
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            itemCount: stops.length,
            itemBuilder: (context, index) {
              final stop = stops[index];
              return GestureDetector(
                onTap: () => _showStopInfo(context, stop),
                child: Container(
                  width: 140,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 20,
                            height: 20,
                            decoration: BoxDecoration(
                              color: Colors.black,
                              shape: BoxShape.circle,
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              '${index + 1}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              stop.name ?? 'Stop ${index + 1}',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      if (stop.category != null) ...[
                        const SizedBox(height: 4),
                        Text(
                          _categoryLabel(stop.category!),
                          style: TextStyle(
                            fontSize: 10,
                            color: Colors.grey[500],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  void _showStopInfo(BuildContext context, StopDetail stop) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _StopInfoSheet(stop: stop),
    );
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// ITINERARY TIMELINE
// ═════════════════════════════════════════════════════════════════════════════

class _ItineraryTimeline extends StatelessWidget {
  final ItineraryDetail itinerary;

  const _ItineraryTimeline({required this.itinerary});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Version badge
        if (itinerary.description != null && itinerary.description!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: Colors.indigo.shade50,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'v${itinerary.versionNumber}: ${itinerary.description}',
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.indigo[700],
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ),

        // Days
        ...itinerary.days.map((day) => _DayTimeline(day: day)),
      ],
    );
  }
}

// ── Day Timeline ────────────────────────────────────────────────────────────

class _DayTimeline extends StatelessWidget {
  final DayDetail day;

  const _DayTimeline({required this.day});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Day header
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${day.dayNumber}',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Day ${day.dayNumber}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Colors.black,
                      ),
                    ),
                    if (day.theme != null && day.theme!.isNotEmpty)
                      Text(
                        day.theme!,
                        style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey[500],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                  ],
                ),
              ),
              if (day.date != null)
                Text(
                  day.date!.length >= 10
                      ? day.date!.substring(5, 10)
                      : day.date!,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[400],
                    fontWeight: FontWeight.w500,
                  ),
                ),
            ],
          ),

          const SizedBox(height: 12),

          // Stop cards
          if (day.stops.isEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 52),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'No stops planned yet',
                  style: TextStyle(color: Colors.grey[400], fontSize: 13),
                ),
              ),
            )
          else
            ...List.generate(day.stops.length, (i) {
              final stop = day.stops[i];
              final isLast = i == day.stops.length - 1;
              return _StopTimelineCard(
                stop: stop,
                index: i + 1,
                isLast: isLast,
              );
            }),

          // Travel time between stops
          if (day.stops.isNotEmpty && day.stops.any((s) => s.minutesFromPrevStop != null && s.minutesFromPrevStop! > 0))
            Padding(
              padding: const EdgeInsets.only(left: 52, top: 8),
              child: Row(
                children: [
                  Icon(Icons.access_time, size: 14, color: Colors.grey[400]),
                  const SizedBox(width: 4),
                  Text(
                    'Total: ${day.stops.fold(0, (int sum, s) => sum + (s.minutesFromPrevStop ?? 0))} min travel',
                    style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── Stop Timeline Card ──────────────────────────────────────────────────────

class _StopTimelineCard extends StatelessWidget {
  final StopDetail stop;
  final int index;
  final bool isLast;

  const _StopTimelineCard({
    required this.stop,
    required this.index,
    required this.isLast,
  });

  @override
  Widget build(BuildContext context) {
    final timeColor = _timeColor(stop.timeOfDay);
    final timeEmoji = _timeEmoji(stop.timeOfDay);
    final timeLabel = _timeLabel(stop.timeOfDay);

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Timeline column
          SizedBox(
            width: 40,
            child: Column(
              children: [
                const SizedBox(height: 6),
                // Numbered circle
                Container(
                  width: 26,
                  height: 26,
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
                  alignment: Alignment.center,
                  child: Text(
                    '$index',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
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

          // Stop card
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(left: 8),
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () {
                    if (stop.placeId != null && stop.placeId!.isNotEmpty) {
                      Navigator.of(context).pushNamed(
                        '/place-detail',
                        arguments: stop.placeId,
                      );
                    }
                  },
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: Colors.grey.shade200),
                    ),
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Title row
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Text(
                                stop.name ?? 'Stop $index',
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

                        const SizedBox(height: 8),

                        // Metadata chips
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: [
                            if (stop.durationMinutes != null &&
                                stop.durationMinutes! > 0)
                              _metaChip(
                                '⏱ ${stop.durationMinutes} min',
                                Colors.blue.shade50,
                                Colors.blue.shade700,
                              ),
                            if (stop.category != null)
                              _metaChip(
                                _categoryLabel(stop.category!),
                                Colors.purple.shade50,
                                Colors.purple.shade700,
                              ),
                            if (stop.rating != null)
                              _metaChip(
                                '⭐ ${stop.rating!.toStringAsFixed(1)}',
                                Colors.amber.shade50,
                                Colors.amber.shade800,
                              ),
                            if (stop.estimatedCost != null &&
                                stop.estimatedCost! > 0)
                              _metaChip(
                                '\$${stop.estimatedCost!.toStringAsFixed(0)}',
                                Colors.green.shade50,
                                Colors.green.shade700,
                              ),
                          ],
                        ),

                        // AI notes / why recommended
                        if (stop.aiNotes != null && stop.aiNotes!.isNotEmpty) ...[
                          const SizedBox(height: 8),
                          Text(
                            stop.aiNotes!,
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                              height: 1.3,
                            ),
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],

                        // Travel mode to next stop
                        if (stop.travelMode != null &&
                            stop.minutesFromPrevStop != null &&
                            stop.minutesFromPrevStop! > 0) ...[
                          const SizedBox(height: 6),
                          Row(
                            children: [
                              Icon(
                                _travelModeIcon(stop.travelMode!),
                                size: 12,
                                color: Colors.grey[400],
                              ),
                              const SizedBox(width: 4),
                              Text(
                                '${_travelModeLabel(stop.travelMode!)} · ${stop.minutesFromPrevStop} min',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey[400],
                                ),
                              ),
                            ],
                          ),
                        ],

                        // Address
                        if (stop.address != null && stop.address!.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Icon(Icons.location_on_outlined,
                                  size: 12, color: Colors.grey[400]),
                              const SizedBox(width: 3),
                              Expanded(
                                child: Text(
                                  stop.address!,
                                  style: TextStyle(
                                      fontSize: 11, color: Colors.grey[400]),
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
          ),
        ],
      ),
    );
  }

  Widget _metaChip(String label, Color bg, Color fg) {
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

  Color _timeColor(String? tod) {
    if (tod == null) return Colors.grey;
    switch (tod.toLowerCase()) {
      case 'morning':
        return const Color(0xFFFFB74D);
      case 'afternoon':
        return const Color(0xFFFF8A65);
      case 'evening':
        return const Color(0xFF7E57C2);
      case 'night':
        return const Color(0xFF37474F);
      default:
        return Colors.grey;
    }
  }

  String _timeEmoji(String? tod) {
    if (tod == null) return '📍';
    switch (tod.toLowerCase()) {
      case 'morning':
        return '🌅';
      case 'afternoon':
        return '☀️';
      case 'evening':
        return '🌙';
      case 'night':
        return '🌃';
      default:
        return '📍';
    }
  }

  String _timeLabel(String? tod) {
    if (tod == null) return '';
    switch (tod.toLowerCase()) {
      case 'morning':
        return 'AM';
      case 'afternoon':
        return 'PM';
      case 'evening':
        return 'Eve';
      case 'night':
        return 'Night';
      default:
        return '';
    }
  }

  IconData _travelModeIcon(String mode) {
    switch (mode.toLowerCase()) {
      case 'walking':
        return Icons.directions_walk;
      case 'driving':
        return Icons.directions_car;
      case 'transit':
        return Icons.directions_bus;
      case 'cycling':
        return Icons.directions_bike;
      default:
        return Icons.directions;
    }
  }

  String _travelModeLabel(String mode) {
    switch (mode.toLowerCase()) {
      case 'walking':
        return 'Walk';
      case 'driving':
        return 'Drive';
      case 'transit':
        return 'Transit';
      case 'cycling':
        return 'Cycle';
      default:
        return mode;
    }
  }
}

String _categoryLabel(String category) {
  switch (category.toLowerCase()) {
    case 'hotel':
      return 'Hotel';
    case 'restaurant':
      return 'Restaurant';
    case 'attraction':
      return 'Attraction';
    case 'cafe':
      return 'Café';
    default:
      return category.isEmpty ? 'Place' : category;
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// MAP MARKER
// ═════════════════════════════════════════════════════════════════════════════

class _MapMarker extends StatelessWidget {
  final int index;
  final StopDetail stop;
  final VoidCallback onTap;

  const _MapMarker({
    required this.index,
    required this.stop,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Marker circle
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: _markerColor(stop.category),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 2),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Text(
              '$index',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          // Pointer arrow
          Container(
            width: 0,
            height: 0,
            decoration: BoxDecoration(
              border: Border(
                top: BorderSide(
                  color: _markerColor(stop.category),
                  width: 6,
                ),
                left: const BorderSide(color: Colors.transparent, width: 5),
                right: const BorderSide(color: Colors.transparent, width: 5),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Color _markerColor(String? category) {
    if (category == null) return Colors.black;
    switch (category.toLowerCase()) {
      case 'hotel':
        return const Color(0xFF2D3436);
      case 'restaurant':
        return const Color(0xFFE17055);
      case 'attraction':
        return const Color(0xFF0984E3);
      case 'cafe':
        return const Color(0xFF00B894);
      default:
        return Colors.black;
    }
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// STOP INFO BOTTOM SHEET
// ═════════════════════════════════════════════════════════════════════════════

class _StopInfoSheet extends StatelessWidget {
  final StopDetail stop;

  const _StopInfoSheet({required this.stop});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey.shade300,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Name + category
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      stop.name ?? 'Stop',
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    if (stop.category != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        _categoryLabel(stop.category!),
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (stop.rating != null)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.amber.shade50,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.star_rounded,
                          size: 16, color: Colors.amber[700]),
                      const SizedBox(width: 4),
                      Text(
                        stop.rating!.toStringAsFixed(1),
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: Colors.amber[800],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),

          const SizedBox(height: 16),

          // Info chips
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              if (stop.durationMinutes != null && stop.durationMinutes! > 0)
                _sheetChip(Icons.timer_outlined, '${stop.durationMinutes} min'),
              if (stop.timeOfDay != null)
                _sheetChip(
                  Icons.schedule_outlined,
                  stop.timeOfDay!.substring(0, 1).toUpperCase() +
                      stop.timeOfDay!.substring(1),
                ),
              if (stop.estimatedCost != null && stop.estimatedCost! > 0)
                _sheetChip(
                  Icons.attach_money,
                  '\$${stop.estimatedCost!.toStringAsFixed(0)}',
                ),
              if (stop.travelMode != null)
                _sheetChip(
                  Icons.directions,
                  stop.travelMode!.substring(0, 1).toUpperCase() +
                      stop.travelMode!.substring(1),
                ),
            ],
          ),

          // AI notes
          if (stop.aiNotes != null && stop.aiNotes!.isNotEmpty) ...[
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.indigo.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.indigo.shade100),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.auto_awesome, size: 16, color: Colors.indigo[400]),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      stop.aiNotes!,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.indigo[700],
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          // Address
          if (stop.address != null && stop.address!.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.location_on_outlined,
                    size: 16, color: Colors.grey[500]),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    stop.address!,
                    style: TextStyle(color: Colors.grey[600], fontSize: 13),
                  ),
                ),
              ],
            ),
          ],

          const SizedBox(height: 20),

          // View details button
          if (stop.placeId != null && stop.placeId!.isNotEmpty)
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.of(context).pushNamed(
                    '/place-detail',
                    arguments: stop.placeId,
                  );
                },
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('View Place Details'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _sheetChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.grey[600]),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(fontSize: 12, color: Colors.grey[700]),
          ),
        ],
      ),
    );
  }
}
