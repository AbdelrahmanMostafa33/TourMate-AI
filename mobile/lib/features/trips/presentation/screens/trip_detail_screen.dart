import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart' as latlong;
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../chat/presentation/screens/chat_screen.dart';
import '../../data/models/trip_detail_model.dart';
import '../../data/models/trip_profile_data.dart';
import '../../logic/trip_detail_cubit.dart';
import '../../logic/trip_detail_state.dart';
import '../../../bookings/data/repository/booking_repository.dart';
import '../../../payments/data/datasource/payment_service.dart';
import '../../../payments/presentation/cubit/booking_payment_cubit.dart';

class TripDetailScreen extends StatefulWidget {
  final String tripId;

  /// When true, automatically triggers the "Book My Trip" flow
  /// (create bookings → initiate Stripe Payment Sheet) immediately
  /// on load, skipping the intermediate button click.
  final bool shouldAutoBook;

  const TripDetailScreen({super.key, required this.tripId, this.shouldAutoBook = false});

  @override
  State<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends State<TripDetailScreen> {
  // Map popup state
  final MapController _mapController = MapController();
  int? _selectedStopIndex;
  StopDetail? _selectedStop;
  bool _showPopupAnimation = false;

  @override
  void initState() {
    super.initState();
    if (widget.shouldAutoBook) {
      _triggerAutoBook();
    }
  }

  /// Auto-trigger "Book My Trip" flow when navigated from Pay Now.
  void _triggerAutoBook() {
    // Wait a frame for the widget tree & providers to be fully built,
    // then wait another moment for the trip detail to finish loading.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final tripId = widget.tripId;
      // The cubit is loading — poll until loaded, then book & pay
      _pollForLoadAndAutoBook(tripId);
    });
  }

  void _pollForLoadAndAutoBook(String tripId) {
    // Check every 200ms up to 10s for the trip to load
    int attempts = 0;
    const maxAttempts = 50;

    void check() {
      if (!mounted) return;
      final state = context.read<TripDetailCubit>().state;
      state.maybeWhen(
        loaded: (trip, _) {
          _bookAndPay(context, tripId);
        },
        orElse: () {
          attempts++;
          if (attempts < maxAttempts) {
            Future.delayed(const Duration(milliseconds: 200), check);
          }
        },
      );
    }

    Future.delayed(const Duration(milliseconds: 200), check);
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (_) =>
              TripDetailCubit(locator<ApiServices>())..fetchTripDetail(widget.tripId),
        ),
        BlocProvider(
          create: (_) => BookingPaymentCubit(
            bookingRepo: locator<BookingRepository>(),
            paymentService: locator<PaymentService>(),
          ),
        ),
      ],
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
              loaded: (trip, profile) => _buildContent(context, trip, profile),
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

  Widget _buildContent(BuildContext context, TripDetailModel trip, TripProfileData? profile) {
    return Column(
      children: [
        // ── Header ─────────────────────────────────────
        _buildHeader(context, trip),

        // ── Trip header card ─────────────────────────────
        _buildTripHeader(trip),

        // ── Payment section ───────────────────────────────
        _buildPaymentSection(context, trip),

        // ── Trip Preferences ─────────────────────────────
        _buildTripPreferences(profile),

        // ── Tabs: Itinerary | Map ────────────────────────
        if (trip.itineraries.isNotEmpty) ...[
          Expanded(
            child: DefaultTabController(
              length: 2,
              child: Column(
                children: [
                  _buildTabBar(),
                  Expanded(child: _buildTabContent(trip)),
                ],
              ),
            ),
          ),
        ] else ...[
          Expanded(child: _buildEmptyItinerary()),
        ],
      ],
    );
  }

  // ── Header with back button, trip name, destination ────────────────────

  Widget _buildHeader(BuildContext context, TripDetailModel trip) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        left: 8,
        right: 8,
        bottom: 4,
      ),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_rounded, color: Colors.black),
            onPressed: () => Navigator.pop(context),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  trip.tripName ?? trip.destination,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: Colors.black,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Row(
                  children: [
                    Icon(Icons.location_on_outlined,
                        size: 13, color: Colors.grey[500]),
                    const SizedBox(width: 3),
                    Text(
                      trip.destination,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Continue Chat button
          IconButton(
            icon: const Icon(Icons.chat_bubble_outline,
                color: Colors.black, size: 20),
            tooltip: 'Continue chat',
            onPressed: () => _continueChat(context, trip),
          ),
          // Delete button
          IconButton(
            icon: const Icon(Icons.delete_outline,
                color: Colors.red, size: 20),
            tooltip: 'Delete trip',
            onPressed: () => _confirmDelete(context, trip),
          ),
        ],
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
      case 'itinerary_draft':
        bg = Colors.indigo.shade50;
        fg = Colors.indigo.shade700;
        label = 'Draft';
        break;
      case 'awaiting_booking':
        bg = Colors.teal.shade50;
        fg = Colors.teal.shade700;
        label = 'Ready to Book';
        break;
      case 'booking_pending':
        bg = Colors.orange.shade50;
        fg = Colors.orange.shade700;
        label = 'Payment Pending';
        break;
      case 'payment_processing':
        bg = Colors.blue.shade50;
        fg = Colors.blue.shade700;
        label = 'Processing Payment';
        break;
      case 'payment_failed':
        bg = Colors.red.shade50;
        fg = Colors.red.shade700;
        label = 'Payment Failed';
        break;
      case 'booking_confirmed':
        bg = Colors.green.shade50;
        fg = Colors.green.shade700;
        label = 'Confirmed';
        break;
      case 'active':
        bg = Colors.green.shade50;
        fg = Colors.green.shade700;
        label = 'Active';
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
        label = status.replaceAll('_', ' ');
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

  // ── Trip Preferences ────────────────────────────────────────────────────────

  Widget _buildTripPreferences(TripProfileData? profile) {
    final chips = <Widget>[];

    if (profile != null) {
      if (profile.budgetLevel != null) {
        chips.add(_prefChip(
          Icons.monetization_on_outlined,
          _capitalize(profile.budgetLevel!),
          const Color(0xFF2E7D32),
          Colors.green.shade50,
        ));
      }

      if (profile.travelStyle != null) {
        chips.add(_prefChip(
          Icons.map_outlined,
          _capitalize(profile.travelStyle!),
          const Color(0xFF1565C0),
          Colors.blue.shade50,
        ));
      }

      if (profile.pace != null) {
        chips.add(_prefChip(
          Icons.speed_outlined,
          _capitalize(profile.pace!),
          const Color(0xFF6A1B9A),
          Colors.purple.shade50,
        ));
      }

      if (profile.interests != null && profile.interests!.isNotEmpty) {
        for (final interest in profile.interests!) {
          chips.add(_prefChip(
            Icons.favorite_outline,
            _capitalize(interest),
            const Color(0xFFC62828),
            Colors.red.shade50,
          ));
        }
      }

      if (profile.foodPreferences != null && profile.foodPreferences!.isNotEmpty) {
        for (final food in profile.foodPreferences!) {
          chips.add(_prefChip(
            Icons.restaurant_outlined,
            _capitalize(food),
            const Color(0xFFE65100),
            Colors.orange.shade50,
          ));
        }
      }

      if (profile.accommodationPreferences != null && profile.accommodationPreferences!.isNotEmpty) {
        for (final acc in profile.accommodationPreferences!) {
          chips.add(_prefChip(
            Icons.bed_outlined,
            _capitalize(acc),
            const Color(0xFF4E342E),
            Colors.brown.shade50,
          ));
        }
      }
    }

    final bool hasChips = chips.isNotEmpty;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.grey.shade50, Colors.white],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.black,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    Icons.tune_outlined,
                    size: 14,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 10),
                const Text(
                  'Trip Preferences',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: Colors.black,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            hasChips
                ? Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: chips,
                  )
                : Row(
                    children: [
                      Icon(Icons.info_outline, size: 14, color: Colors.grey[400]),
                      const SizedBox(width: 8),
                      Text(
                        profile == null
                            ? 'Chat with TourMate to generate preferences'
                            : 'No preferences set yet',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[500],
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ],
                  ),
          ],
        ),
      ),
    );
  }

  Widget _prefChip(IconData icon, String label, Color color, Color bgColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  String _capitalize(String s) {
    if (s.isEmpty) return s;
    return s[0].toUpperCase() + s.substring(1);
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
              Navigator.pushNamedAndRemoveUntil(
                context,
                '/home',
                (route) => false,
              );
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
    return TabBarView(
      physics: const BouncingScrollPhysics(),
      children: [
        _buildItineraryTab(trip),
        _buildMapTab(trip),
      ],
    );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // ITINERARY TAB
  // ═══════════════════════════════════════════════════════════════════════════

  Widget _buildItineraryTab(TripDetailModel trip) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: trip.itineraries.map((itin) {
        return _ItineraryTimeline(itinerary: itin);
      }).toList(),
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
        // Map with popup overlay
        Expanded(
          child: Stack(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: FlutterMap(
                  mapController: _mapController,
                  options: MapOptions(
                    initialCenter: center,
                    initialZoom: 12,
                    minZoom: 4,
                    maxZoom: 18,
                    onTap: (tapPos, latLng) => _hidePopup(),
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
                        final isSelected = _selectedStopIndex == index;
                        return Marker(
                          point: latlong.LatLng(stop.lat!, stop.lon!),
                          width: isSelected ? 48 : 40,
                          height: isSelected ? 56 : 48,
                          child: GestureDetector(
                            onTap: () => _showPopup(index, stop),
                            child: _MapMarker(
                              index: index + 1,
                              stop: stop,
                              isSelected: isSelected,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],
                ),
              ),

              // Inline popup card
              if (_selectedStopIndex != null && _selectedStop != null)
                _buildMapPopup(stops),
            ],
          ),
        ),

        // Legend / stop list
        Container(
          height: 110,
          width: double.infinity,
          margin: const EdgeInsets.only(top: 8),
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 4),
            itemCount: stops.length,
            itemBuilder: (context, index) {
              final stop = stops[index];
              final isSelected = _selectedStopIndex == index;
              return GestureDetector(
                onTap: () => _showPopup(index, stop),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 140,
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: isSelected ? Colors.black : Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: isSelected ? Colors.black : Colors.grey.shade200,
                    ),
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
                              color: isSelected ? Colors.white : Colors.black,
                              shape: BoxShape.circle,
                            ),
                            alignment: Alignment.center,
                            child: Text(
                              '${index + 1}',
                              style: TextStyle(
                                color: isSelected ? Colors.black : Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              stop.name ?? 'Stop ${index + 1}',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: isSelected ? Colors.white : Colors.black,
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
                            color: isSelected ? Colors.grey[300] : Colors.grey[500],
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

  Widget _buildMapPopup(List<StopDetail> stops) {
    final stop = _selectedStop!;
    final index = _selectedStopIndex!;

    return Positioned(
      left: 16,
      right: 16,
      bottom: 12,
      child: GestureDetector(
        onTap: () {
          if (stop.placeId != null && stop.placeId!.isNotEmpty) {
            Navigator.of(context).pushNamed('/place-detail', arguments: stop.placeId);
          }
        },
        child: AnimatedOpacity(
          opacity: _showPopupAnimation ? 1.0 : 0.0,
          duration: const Duration(milliseconds: 200),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.15),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Row(
              children: [
                // Stop number badge
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: _markerColor(stop.category),
                    shape: BoxShape.circle,
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '${index + 1}',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        stop.name ?? 'Stop ${index + 1}',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: Colors.black,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Row(
                        children: [
                          if (stop.category != null) ...[
                            Text(
                              _categoryLabel(stop.category!),
                              style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (stop.rating != null) ...[
                            Icon(Icons.star_rounded, size: 12, color: Colors.amber[700]),
                            const SizedBox(width: 2),
                            Text(
                              stop.rating!.toStringAsFixed(1),
                              style: TextStyle(
                                fontSize: 11,
                                color: Colors.grey[600],
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                          const SizedBox(width: 8),
                          if (stop.durationMinutes != null && stop.durationMinutes! > 0)
                            Text(
                              '${stop.durationMinutes} min',
                              style: TextStyle(fontSize: 11, color: Colors.grey[500]),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                // Arrow icon
                Icon(Icons.chevron_right_rounded, color: Colors.grey[400]),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showPopup(int index, StopDetail stop) {
    setState(() {
      _selectedStopIndex = index;
      _selectedStop = stop;
      _showPopupAnimation = false;
    });
    // Trigger fade-in after one frame
    Future.delayed(const Duration(milliseconds: 50), () {
      if (mounted) setState(() => _showPopupAnimation = true);
    });
  }

  void _hidePopup() {
    setState(() {
      _showPopupAnimation = false;
    });
    Future.delayed(const Duration(milliseconds: 200), () {
      if (mounted) {
        setState(() {
          _selectedStopIndex = null;
          _selectedStop = null;
        });
      }
    });
  }
  /// Navigate to the chat screen connected to this trip.
  /// Pushes a new ChatScreen directly so the trip_id is always passed
  /// correctly, regardless of route argument forwarding.
  void _continueChat(BuildContext context, TripDetailModel trip) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ChatScreen(initialTripId: trip.tripId),
      ),
    );
  }

  /// Show confirmation dialog before deleting the trip.
  Future<void> _confirmDelete(BuildContext context, TripDetailModel trip) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: const Text("Delete Trip"),
        content: Text(
          'Are you sure you want to delete your trip to ${trip.destination}?\n\nThis action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text("Cancel", style: TextStyle(color: Colors.grey)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text(
              "Delete",
              style: TextStyle(
                color: Colors.red,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );

    if (confirmed != true) return;
    if (!context.mounted) return;

    final cubit = context.read<TripDetailCubit>();
    String? error;
    try {
      await cubit.deleteTrip(trip.tripId);
    } catch (e) {
      error = e.toString();
    }

    if (!context.mounted) return;

    if (error != null) {
      AppSnackbar.error(context, error);
    } else {
      AppSnackbar.info(context, 'Trip deleted');
      Navigator.pop(context);
    }
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
    // Filter out hotel/accommodation stops — they are rendered
    // separately and should not appear as regular day stops.
    final filteredStops = day.stops.where((s) {
      final cat = (s.category ?? '').toLowerCase();
      return cat != 'hotel' && cat != 'accommodation';
    }).toList();

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
          if (filteredStops.isEmpty)
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
            ...List.generate(filteredStops.length, (i) {
              final stop = filteredStops[i];
              final isLast = i == filteredStops.length - 1;
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
      child: Stack(
        children: [
          // Connecting line (positioned below the circle)
          if (!isLast)
            Positioned(
              left: 20, // center of the 40px timeline
              top: 50, // 6px padding + 26px circle + 18px buffer
              bottom: 0,
              child: Container(
                width: 2,
                color: Colors.grey.shade200,
              ),
            ),
          // Content row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Timeline circle
              SizedBox(
                width: 40,
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Center(
                    child: Container(
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
                  ),
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

// ═════════════════════════════════════════════════════════════════════════════
// PAYMENT SECTION — Top-level functions
// ═════════════════════════════════════════════════════════════════════════════

Widget _buildProcessingBanner() {
  return Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    child: Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blue.shade50,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.blue.shade200),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: Colors.blue.shade700,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Finalizing your booking…',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.blue.shade800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Your trip is being approved. This should take just a moment.',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.blue.shade600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

/// Payment section — Pay All button + state feedback.
/// Always renders the BlocConsumer so it can listen for state changes
/// regardless of trip status (fixes the bug where the Stripe Payment
/// Sheet state was never shown when the trip was still 'planning').
Widget _buildPaymentSection(BuildContext context, TripDetailModel trip) {
  final paymentRelevant = ['awaiting_booking', 'booking_pending', 'payment_failed'].contains(trip.status);
  final isPlanning = trip.status == 'planning';
  final isAwaitingBooking = trip.status == 'awaiting_booking';

  return Column(
    children: [
      // Processing banner (shown during planning / before status update)
      if (isPlanning)
        _buildProcessingBanner(),

      // Payment flow — always rendered so the BlocConsumer can listen for
      // state changes from _bookAndPay / _payAll, even when the trip is
      // still 'planning' (e.g., during auto-book flow).
      // The builder hides the UI when not payment-relevant.
      BlocConsumer<BookingPaymentCubit, BookingPaymentState>(
        listenWhen: (previous, current) =>
            current is BookingPaymentSuccess || current is BookingPaymentFailure,
        listener: (context, state) {
          if (state is BookingPaymentSuccess) {
            final msg = state.message ??
                (state.simulated == true
                    ? 'Bookings marked as completed (simulated mode)'
                    : 'Payment successful!');
            AppSnackbar.success(context, msg);
            context
                .read<TripDetailCubit>()
                .fetchTripDetail(trip.tripId);
          } else if (state is BookingPaymentFailure) {
            AppSnackbar.error(context, state.error);
            context
                .read<TripDetailCubit>()
                .fetchTripDetail(trip.tripId);
          }
        },
        builder: (context, state) {
          // If state indicates an active payment flow, show it even if
          // the trip is still planning (auto-book flow is in progress).
          final hasActivePayment = state is BookingPaymentInitiating ||
              state is BookingPaymentSheetOpen ||
              state is BookingPaymentPolling ||
              state is BookingPaymentSuccess ||
              state is BookingPaymentFailure;

          if (hasActivePayment) {
            if (state is BookingPaymentInitiating) {
              return _buildPaymentButton(
                context: context,
                isLoading: true,
                label: 'Processing…',
                icon: Icons.hourglass_top,
              );
            }
            if (state is BookingPaymentSheetOpen) {
              return _buildPaymentButton(
                context: context,
                isLoading: true,
                label: 'Complete payment in the sheet…',
                icon: Icons.credit_card,
              );
            }
            if (state is BookingPaymentPolling) {
              return _buildPaymentButton(
                context: context,
                isLoading: true,
                label: 'Confirming payment (${state.secondsElapsed}s)…',
                icon: Icons.sync,
              );
            }
            if (state is BookingPaymentSuccess) {
              return _buildPaymentButton(
                context: context,
                isLoading: false,
                label: 'Payment Complete',
                icon: Icons.check_circle,
                color: Colors.green,
              );
            }
            if (state is BookingPaymentFailure) {
              return _buildPaymentButton(
                context: context,
                isLoading: false,
                label: 'Retry Payment',
                icon: Icons.error_outline,
                color: Colors.red.shade400,
                onTap: () => _payAll(context, trip.tripId),
              );
            }
          }

          // No active payment flow — hide the buttons if not payment-relevant
          if (!paymentRelevant) return const SizedBox.shrink();

          // Idle state — show action button
          final count = trip.pendingBookingsCount;
          if (isAwaitingBooking) {
            return Stack(
              clipBehavior: Clip.none,
              children: [
                _buildPaymentButton(
                  context: context,
                  isLoading: false,
                  label: 'Book My Trip',
                  icon: Icons.book_online,
                  onTap: () => _bookAndPay(context, trip.tripId),
                ),
              ],
            );
          }

          final label = count > 0
              ? 'Pay All ($count pending)'
              : 'Pay All Bookings';
          return Stack(
            clipBehavior: Clip.none,
            children: [
              _buildPaymentButton(
                context: context,
                isLoading: false,
                label: label,
                icon: Icons.payment,
                onTap: () => _payAll(context, trip.tripId),
              ),
              if (count > 0)
                Positioned(
                  right: 12,
                  top: -6,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.red.shade600,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      '$count',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    ],
  );
}

/// Book the trip package (all stops) then proceed to payment.
Future<void> _bookAndPay(BuildContext context, String tripId) async {
  // Step 1: Create bookings from the itinerary via the booking repository
  String? error;
  try {
    final bookingRepo = locator<BookingRepository>();
    await bookingRepo.bookTripPackage(tripId);
  } catch (e) {
    error = e.toString();
    debugPrint('[TripDetail] Failed to book trip package: $e');
  }

  // Show feedback if booking creation failed
  if (error != null) {
    if (!context.mounted) return;
    AppSnackbar.error(context,
        'Could not create bookings: $error. Please try again or continue in chat.');
    return;
  }

  // Step 2: Proceed with payment initiation (async Stripe flow)
  if (!context.mounted) return;
  context.read<BookingPaymentCubit>().initiatePayAllBookings(
    PayAllBookings(
      tripId: tripId,
      paymentMethod: 'credit_card',
      currency: 'usd',
    ),
  );
}

/// Triggers the Pay All flow via the BookingPaymentCubit.
void _payAll(BuildContext context, String tripId) {
  context.read<BookingPaymentCubit>().initiatePayAllBookings(
    PayAllBookings(
      tripId: tripId,
      paymentMethod: 'credit_card',
      currency: 'usd',
    ),
  );
}

/// Internal button widget for the payment section.
Widget _buildPaymentButton({
  required BuildContext context,
  required bool isLoading,
  required String label,
  required IconData icon,
  Color? color,
  VoidCallback? onTap,
}) {
  final btnColor = color ?? Theme.of(context).primaryColor;
  return Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
    child: SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: isLoading ? null : onTap,
        icon: isLoading
            ? const SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : Icon(icon, color: Colors.white),
        label: Text(label),
        style: ElevatedButton.styleFrom(
          backgroundColor: btnColor,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          elevation: 0,
        ),
      ),
    ),
  );
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

// ═════════════════════════════════════════════════════════════════════════════
// MAP MARKER
// ═════════════════════════════════════════════════════════════════════════════

class _MapMarker extends StatelessWidget {
  final int index;
  final StopDetail stop;
  final bool isSelected;

  const _MapMarker({
    required this.index,
    required this.stop,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final color = _markerColor(stop.category);
    final size = isSelected ? 14.0 : 11.0;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Marker circle
        AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: EdgeInsets.all(isSelected ? 8 : 6),
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(
              color: isSelected ? Colors.amber : Colors.white,
              width: isSelected ? 3 : 2,
            ),
            boxShadow: [
              BoxShadow(
                color: (isSelected ? color.withValues(alpha: 0.5) : Colors.black.withValues(alpha: 0.2)),
                blurRadius: isSelected ? 10 : 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Text(
            '$index',
            style: TextStyle(
              color: Colors.white,
              fontSize: size,
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
                color: color,
                width: isSelected ? 8 : 6,
              ),
              left: const BorderSide(color: Colors.transparent, width: 5),
              right: const BorderSide(color: Colors.transparent, width: 5),
            ),
          ),
        ),
      ],
    );
  }
}
