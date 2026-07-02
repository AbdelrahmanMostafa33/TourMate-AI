import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:latlong2/latlong.dart' as latlong;
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../../chat/presentation/screens/chat_screen.dart';
import '../../data/models/trip_detail_model.dart';
import '../../data/models/trip_profile_data.dart';
import '../../logic/trip_detail_cubit.dart';
import '../../logic/trip_detail_state.dart';


class TripDetailScreen extends StatefulWidget {
  final String tripId;

  const TripDetailScreen({super.key, required this.tripId});

  @override
  State<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends State<TripDetailScreen> {
  TourMateColors get tm => context.tm;

  // Map popup state
  final MapController _mapController = MapController();
  int? _selectedStopIndex;
  StopDetail? _selectedStop;
  bool _showPopupAnimation = false;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => TripDetailCubit(locator<ApiServices>())..fetchTripDetail(widget.tripId),
      child: Scaffold(
        backgroundColor: tm.brandWhite,
        body: BlocBuilder<TripDetailCubit, TripDetailState>(
          builder: (context, state) {
            return state.when(
              initial: () => const SizedBox(),
              loading: () => const Center(
                child: TMLoadingIndicator(message: 'Loading trip...'),
              ),
              error: (message) => TMErrorState(
                message: message,
                onRetry: () => context.read<TripDetailCubit>().fetchTripDetail(widget.tripId),
              ),
              loaded: (trip, profile) => _buildContent(context, trip, profile),
            );
          },
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

  // ── Premium Header ────────────────────────────────────────────────────────

  Widget _buildHeader(BuildContext context, TripDetailModel trip) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        left: 4,
        right: 4,
        bottom: 4,
      ),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        border: Border(bottom: BorderSide(color: tm.divider, width: 0.5)),
      ),
      child: Row(
        children: [
          // Back button with sapphire accent on press
          IconButton(
            icon: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: tm.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: tm.borderLight),
              ),
              child: Icon(Icons.arrow_back_rounded, color: tm.textPrimary, size: 18),
            ),
            onPressed: () => Navigator.pop(context),
          ),
          const SizedBox(width: 4),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  trip.tripName ?? trip.destination,
                  style: GoogleFonts.inter(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.3,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Row(
                  children: [
                    Icon(Icons.location_on_outlined, size: 12, color: tm.sapphire),
                    const SizedBox(width: 3),
                    Text(
                      trip.destination,
                      style: GoogleFonts.inter(fontSize: 12, color: tm.textSecondary),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Continue Chat button — sapphire accent
          Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _continueChat(context, trip),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: tm.sapphire.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.chat_bubble_outline, color: tm.deepRoyalBlue, size: 18),
              ),
            ),
          ),
          const SizedBox(width: 4),
          // Delete button
          Material(
            color: Colors.transparent,
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => _confirmDelete(context, trip),
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: tm.error.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(Icons.delete_outline, color: tm.error, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Premium Trip Header Card ──────────────────────────────────────────────

  Widget _buildTripHeader(TripDetailModel trip) {
    return Hero(
      tag: 'booking-summary-${widget.tripId}',
      child: Padding(
        padding: const EdgeInsets.fromLTRB(Spacing.xl3, 4, Spacing.xl3, Spacing.xl3),
      child: Container(
        padding: const EdgeInsets.all(Spacing.xl3),
        decoration: BoxDecoration(
          color: tm.brandWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          border: Border.all(color: tm.borderLight),
          boxShadow: [
            BoxShadow(
              color: tm.deepNavy.withValues(alpha: 0.04),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          children: [
            // First row: dates & duration + sapphire-accented status
            Row(
              children: [
                _headerInfoChip(
                  Icons.calendar_today_outlined,
                  trip.durationDays > 0
                      ? '${trip.durationDays} day${trip.durationDays > 1 ? 's' : ''}'
                      : 'Flexible',
                ),
                const Spacer(),
                TMStatusBadge(label: _statusLabel(trip.status)),
              ],
            ),

            if (trip.startDate != null || trip.endDate != null) ...[
              const SizedBox(height: Spacing.sm),
              Row(
                children: [
                  Icon(Icons.date_range_outlined, size: 14, color: tm.sapphireLight),
                  const SizedBox(width: 6),
                  Text(
                    _formatDateRange(trip),
                    style: GoogleFonts.inter(fontSize: 13, color: tm.textSecondary),
                  ),
                ],
              ),
            ],

            if (trip.numberOfTravelers > 1) ...[
              const SizedBox(height: Spacing.sm),
              Row(
                children: [
                  Icon(Icons.people_outline, size: 14, color: tm.sapphireLight),
                  const SizedBox(width: 6),
                  Text(
                    '${trip.numberOfTravelers} travelers',
                    style: GoogleFonts.inter(fontSize: 13, color: tm.textSecondary),
                  ),
                ],
              ),
            ],

            // Premium stats row
            if (trip.itineraries.isNotEmpty) ...[
              const SizedBox(height: Spacing.xl3),
              Container(
                height: 1,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [tm.divider.withValues(alpha: 0), tm.divider, tm.divider.withValues(alpha: 0)],
                  ),
                ),
              ),
              const SizedBox(height: Spacing.xl3),
              Row(
                children: [
                  _statItem('${trip.allStops.length}', 'Stops', Icons.flag_outlined),
                  _statItem('${trip.durationDays}', 'Days', Icons.wb_sunny_outlined),
                  _statItem('${trip.itineraries.length}', 'Versions', Icons.layers_outlined),
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
      ),
    );
  }

  String _statusLabel(String status) {
    switch (status.toLowerCase()) {
      case 'planning':
        return 'Planning';
      case 'itinerary_draft':
        return 'Draft';
      case 'awaiting_booking':
        return 'Ready to Book';
      case 'booking_pending':
        return 'Payment Pending';
      case 'payment_processing':
        return 'Processing';
      case 'payment_failed':
        return 'Payment Failed';
      case 'booking_confirmed':
        return 'Confirmed';
      case 'active':
        return 'Active';
      case 'completed':
        return 'Completed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status
            .replaceAll('_', ' ')
            .split(' ')
            .map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1)}')
            .join(' ');
    }
  }

  Widget _headerInfoChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: tm.borderLight),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: tm.sapphireLight),
          const SizedBox(width: 5),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 12, fontWeight: FontWeight.w600, color: tm.textPrimary),
          ),
        ],
      ),
    );
  }

  Widget _statItem(String value, String label, IconData icon) {
    return Expanded(
      child: Column(
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
            child: Icon(icon, size: 16, color: tm.sapphireLight),
          ),
          const SizedBox(height: 8),
          Text(
            value,
            style: GoogleFonts.inter(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: tm.textPrimary,
              letterSpacing: -0.3,
            ),
          ),
          Text(
            label,
            style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary, letterSpacing: 0.2),
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

  // ── Trip Preferences — sapphire-accented Premium Chips ─────────────────────────

  Widget _buildTripPreferences(TripProfileData? profile) {
    final chips = <Widget>[];

    if (profile != null) {
      if (profile.budgetLevel != null) {
        chips.add(_prefChip(
          Icons.monetization_on_outlined,
          _capitalize(profile.budgetLevel!),
          tm.sapphire,
        ));
      }

      if (profile.travelStyle != null) {
        chips.add(_prefChip(
          Icons.map_outlined,
          _capitalize(profile.travelStyle!),
          tm.sapphire,
        ));
      }

      if (profile.pace != null) {
        chips.add(_prefChip(
          Icons.speed_outlined,
          _capitalize(profile.pace!),
          tm.sapphire,
        ));
      }

      if (profile.interests != null && profile.interests!.isNotEmpty) {
        for (final interest in profile.interests!) {
          chips.add(_prefChip(
            Icons.favorite_outline,
            _capitalize(interest),
            tm.sapphire,
          ));
        }
      }

      if (profile.foodPreferences != null && profile.foodPreferences!.isNotEmpty) {
        for (final food in profile.foodPreferences!) {
          chips.add(_prefChip(
            Icons.restaurant_outlined,
            _capitalize(food),
            tm.sapphire,
          ));
        }
      }

      if (profile.accommodationPreferences != null && profile.accommodationPreferences!.isNotEmpty) {
        for (final acc in profile.accommodationPreferences!) {
          chips.add(_prefChip(
            Icons.bed_outlined,
            _capitalize(acc),
            tm.sapphire,
          ));
        }
      }
    }

    final bool hasChips = chips.isNotEmpty;

    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.md),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(Spacing.xl3),
        decoration: BoxDecoration(
          color: tm.brandWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          border: Border.all(color: tm.borderLight),
          boxShadow: [
            BoxShadow(
              color: tm.deepNavy.withValues(alpha: 0.04),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
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
                  child: Icon(Icons.tune_outlined, size: 14, color: tm.sapphireLight),
                ),
                const SizedBox(width: 10),
                Text(
                  'Trip Preferences',
                  style: GoogleFonts.inter(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.2,
                  ),
                ),
              ],
            ),
            const SizedBox(height: Spacing.md),
            hasChips
                ? Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: chips,
                  )
                : Row(
                    children: [
                      Icon(Icons.info_outline, size: 14, color: tm.textTertiary),
                      const SizedBox(width: 8),
                      Text(
                        profile == null
                            ? 'Chat with TourMate to generate preferences'
                            : 'No preferences set yet',
                        style: GoogleFonts.inter(
                          fontSize: 12,
                          color: tm.textTertiary,
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

  Widget _prefChip(IconData icon, String label, Color color) {
    final adjustedColor = color;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: adjustedColor),
          const SizedBox(width: 5),
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: adjustedColor,
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

  // ── Premium Empty State ───────────────────────────────────────────────────

  Widget _buildEmptyItinerary() {
    return TMEmptyState(
      icon: Icons.map_outlined,
      title: 'No itinerary yet',
      subtitle: 'Start a chat with TourMate to plan this trip',
      actionLabel: 'Chat with TourMate',
      onAction: () {
        Navigator.pushNamedAndRemoveUntil(
          context,
          '/home',
          (route) => false,
        );
      },
    );
  }

  // ── Premium Tab Bar ───────────────────────────────────────────────────────

  Widget _buildTabBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3),
      child: Container(
        decoration: BoxDecoration(
          color: tm.surface,
          borderRadius: BorderRadius.circular(RadiusTokens.md),
          border: Border.all(color: tm.borderLight),
        ),
        child: TabBar(
          indicator: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(RadiusTokens.sm),
          ),
          labelColor: tm.sapphireLight,
          unselectedLabelColor: tm.textSecondary,
          labelStyle: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: -0.2),
          unselectedLabelStyle: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w500),
          indicatorSize: TabBarIndicatorSize.tab,
          dividerColor: Colors.transparent,
          padding: const EdgeInsets.all(4),
          tabs: [
            Tab(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.explore_outlined, size: 16),
                  const SizedBox(width: 6),
                  const Text('Itinerary'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.map_outlined, size: 16),
                  const SizedBox(width: 6),
                  const Text('Map'),
                ],
              ),
            ),
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
            Icon(Icons.map_outlined, size: 48, color: tm.textTertiary),
            const SizedBox(height: 12),
            Text(
              'No location data available',
              style: TextStyle(color: tm.textTertiary),
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

        // Premium legend / stop list with sapphire accent on selected
        Container(
          height: 100,
          width: double.infinity,
          padding: const EdgeInsets.only(left: Spacing.xl3, right: Spacing.xl3, top: Spacing.sm),
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: stops.length,
            itemBuilder: (context, index) {
              final stop = stops[index];
              final isSelected = _selectedStopIndex == index;
              return GestureDetector(
                onTap: () => _showPopup(index, stop),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: 150,
                  margin: const EdgeInsets.only(right: Spacing.sm),
                  padding: const EdgeInsets.all(Spacing.md),
                  decoration: BoxDecoration(
                    color: isSelected ? tm.deepNavy : tm.brandWhite,
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                    border: Border.all(
                      color: isSelected ? tm.sapphire.withValues(alpha: 0.5) : tm.borderLight,
                      width: isSelected ? 1.5 : 1,
                    ),
                    boxShadow: isSelected ? [
                      BoxShadow(
                        color: tm.sapphire.withValues(alpha: 0.15),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ] : [],
                  ),
                  child: Row(
                    children: [
                      // Premium circle badge
                      Container(
                        width: 22,
                        height: 22,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: isSelected
                                ? [tm.sapphireLight, tm.sapphire]
                                : [const Color(0xFF0A0A0A), const Color(0xFF1A1A1A)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          shape: BoxShape.circle,
                        ),
                        alignment: Alignment.center,
                        child: Text(
                          '${index + 1}',
                          style: GoogleFonts.inter(
                            color: isSelected ? tm.deepNavy : tm.brandWhite,
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              stop.name ?? 'Stop ${index + 1}',
                              style: GoogleFonts.inter(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: isSelected ? tm.brandWhite : tm.textPrimary,
                                letterSpacing: -0.1,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                            if (stop.category != null) ...[
                              const SizedBox(height: 2),
                              Text(
                                _categoryLabel(stop.category!),
                                style: GoogleFonts.inter(
                                  fontSize: 10,
                                  color: isSelected ? tm.sapphireLight : tm.textTertiary,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
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
      left: Spacing.xl3,
      right: Spacing.xl3,
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
            padding: const EdgeInsets.all(Spacing.md),
            decoration: BoxDecoration(
              color: tm.brandWhite,
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              border: Border.all(color: tm.borderLight),
              boxShadow: [
                BoxShadow(
                  color: tm.deepNavy.withValues(alpha: 0.12),
                  blurRadius: 16,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Row(
              children: [
                // Premium stop number badge with sapphire gradient
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    shape: BoxShape.circle,
                    border: Border.all(color: tm.sapphire.withValues(alpha: 0.4), width: 1.5),
                    boxShadow: [
                      BoxShadow(
                        color: tm.sapphire.withValues(alpha: 0.2),
                        blurRadius: 6,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: Text(
                    '${index + 1}',
                    style: GoogleFonts.inter(
                      color: tm.sapphireLight,
                      fontSize: 14,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: Spacing.md),
                // Info
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        stop.name ?? 'Stop ${index + 1}',
                        style: GoogleFonts.inter(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: tm.textPrimary,
                          letterSpacing: -0.1,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          if (stop.category != null) ...[
                            Icon(Icons.explore_outlined, size: 11, color: tm.sapphireLight),
                            const SizedBox(width: 3),
                            Text(
                              _categoryLabel(stop.category!),
                              style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (stop.rating != null) ...[
                            Icon(Icons.star_rounded, size: 12, color: tm.sapphire),
                            const SizedBox(width: 2),
                            Text(
                              stop.rating!.toStringAsFixed(1),
                              style: GoogleFonts.inter(
                                fontSize: 11,
                                color: tm.sapphire,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                          if (stop.durationMinutes != null && stop.durationMinutes! > 0) ...[
                            const SizedBox(width: 8),
                            Icon(Icons.timer_outlined, size: 11, color: tm.textTertiary),
                            const SizedBox(width: 2),
                            Text(
                              '${stop.durationMinutes} min',
                              style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
                            ),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                // Premium arrow
                Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(Icons.chevron_right_rounded, size: 18, color: tm.deepRoyalBlue),
                ),
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

  /// Show premium confirmation dialog before deleting the trip.
  Future<void> _confirmDelete(BuildContext context, TripDetailModel trip) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        ),
        backgroundColor: tm.brandWhite,
        titlePadding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xl3, Spacing.xl3, 0),
        contentPadding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.md, Spacing.xl3, 0),
        actionsPadding: const EdgeInsets.fromLTRB(Spacing.sm, Spacing.sm, Spacing.sm, Spacing.sm),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: tm.error.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.delete_outline, size: 18, color: tm.error),
            ),
            const SizedBox(width: 10),
            Text(
              "Delete Trip",
              style: GoogleFonts.inter(
                fontWeight: FontWeight.w700,
                fontSize: 17,
                color: tm.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
          ],
        ),
        content: Text(
          'Are you sure you want to delete your trip to ${trip.destination}? This action cannot be undone.',
          style: GoogleFonts.inter(
            fontSize: 14,
            color: tm.textSecondary,
            height: 1.5,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: Text(
              "Cancel",
              style: GoogleFonts.inter(color: tm.textTertiary, fontWeight: FontWeight.w600, fontSize: 14),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(
              backgroundColor: tm.error.withValues(alpha: 0.08),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
            child: Text(
              "Delete",
              style: GoogleFonts.inter(
                color: tm.error,
                fontWeight: FontWeight.w700,
                fontSize: 14,
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
      AppSnackbar.success(context, 'Trip deleted successfully');
      // Pop with 'deleted' result so TripsScreen can react accordingly
      Navigator.pop(context, 'deleted');
    }
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// PREMIUM ITINERARY TIMELINE
// ═════════════════════════════════════════════════════════════════════════════

class _ItineraryTimeline extends StatelessWidget {
  final ItineraryDetail itinerary;

  const _ItineraryTimeline({required this.itinerary});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Premium version badge
        if (itinerary.description != null && itinerary.description!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: Spacing.md),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: tm.sapphire.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: tm.sapphire.withValues(alpha: 0.2)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.auto_awesome, size: 12, color: tm.sapphire),
                  const SizedBox(width: 6),
                  Text(
                    'v${itinerary.versionNumber}: ${itinerary.description}',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      color: tm.sapphire,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.1,
                    ),
                  ),
                ],
              ),
            ),
          ),

        // Days
        ...itinerary.days.map((day) => _DayTimeline(day: day)),
      ],
    );
  }
}

// ── Premium Day Timeline ───────────────────────────────────────────────────

class _DayTimeline extends StatelessWidget {
  final DayDetail day;

  const _DayTimeline({required this.day});

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    // Filter out hotel/accommodation stops
    final filteredStops = day.stops.where((s) {
      final cat = (s.category ?? '').toLowerCase();
      return cat != 'hotel' && cat != 'accommodation';
    }).toList();

    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.xl3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Premium day header with sapphire accent
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
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
                  '${day.dayNumber}',
                  style: GoogleFonts.inter(
                    color: tm.sapphireLight,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.5,
                  ),
                ),
              ),
              const SizedBox(width: Spacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Day ${day.dayNumber}',
                      style: GoogleFonts.inter(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: tm.textPrimary,
                        letterSpacing: -0.2,
                      ),
                    ),
                    if (day.theme != null && day.theme!.isNotEmpty)
                      Text(
                        day.theme!,
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: tm.textTertiary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                  ],
                ),
              ),
              if (day.date != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    day.date!.length >= 10
                        ? day.date!.substring(5, 10)
                        : day.date!,
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: tm.sapphire,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),

          const SizedBox(height: Spacing.md),

          // Stop cards with premium timeline
          if (filteredStops.isEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 52),
              child: Container(
                padding: const EdgeInsets.all(Spacing.md),
                decoration: BoxDecoration(
                  color: tm.surface,
                  borderRadius: BorderRadius.circular(RadiusTokens.md),
                ),
                child: Text(
                  'No stops planned yet',
                  style: GoogleFonts.inter(color: tm.textTertiary, fontSize: 13),
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

          // Travel time
          if (day.stops.isNotEmpty && day.stops.any((s) => s.minutesFromPrevStop != null && s.minutesFromPrevStop! > 0))
            Padding(
              padding: const EdgeInsets.only(left: 52, top: Spacing.sm),
              child: Row(
                children: [
                  Icon(Icons.access_time, size: 14, color: tm.sapphireLight),
                  const SizedBox(width: 4),
                  Text(
                    'Total: ${day.stops.fold(0, (int sum, s) => sum + (s.minutesFromPrevStop ?? 0))} min travel',
                    style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── Premium Stop Timeline Card ─────────────────────────────────────────────

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
    final tm = context.tm;
    final timeColor = _timeColor(stop.timeOfDay);
    final timeLabel = _timeLabel(stop.timeOfDay);

    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.sm),
      child: Stack(
        children: [
          // Gold connecting line
          if (!isLast)
            Positioned(
              left: 20,
              top: 50,
              bottom: 0,
              child: Container(
                width: 1.5,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [tm.sapphire.withValues(alpha: 0.4), tm.sapphire.withValues(alpha: 0.1)],
                  ),
                ),
              ),
            ),
          // Content row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Premium timeline circle
              SizedBox(
                width: 40,
                child: Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Center(
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 28,
                      height: 28,
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: [timeColor, timeColor.withValues(alpha: 0.8)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        shape: BoxShape.circle,
                        border: Border.all(color: tm.brandWhite, width: 2.5),
                        boxShadow: [
                          BoxShadow(
                            color: timeColor.withValues(alpha: 0.35),
                            blurRadius: 6,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        '$index',
                        style: GoogleFonts.inter(
                          color: Colors.white,
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
              // Premium stop card
              Expanded(
                child: Container(
                  margin: const EdgeInsets.only(left: 8),
                  child: Material(
                    color: tm.brandWhite,
                    borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                    child: InkWell(
                      borderRadius: BorderRadius.circular(RadiusTokens.xl3),
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
                          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                          border: Border.all(color: tm.borderLight),
                          boxShadow: [
                            BoxShadow(
                              color: tm.deepNavy.withValues(alpha: 0.03),
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                        padding: const EdgeInsets.all(Spacing.md),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Title row with sapphire accent time badge
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Text(
                                    stop.name ?? 'Stop $index',
                                    style: GoogleFonts.inter(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w600,
                                      color: tm.textPrimary,
                                      letterSpacing: -0.1,
                                    ),
                                  ),
                                ),
                                if (timeLabel.isNotEmpty)
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 8,
                                      vertical: 3,
                                    ),
                                    decoration: BoxDecoration(
                                      color: timeColor.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(color: timeColor.withValues(alpha: 0.2)),
                                    ),
                                    child: Text(
                                      timeLabel,
                                      style: GoogleFonts.inter(
                                        fontSize: 10,
                                        color: timeColor,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                              ],
                            ),

                            const SizedBox(height: Spacing.sm),

                            // sapphire-accented metadata chips
                            Wrap(
                              spacing: 6,
                              runSpacing: 4,
                              children: [
                                if (stop.durationMinutes != null &&
                                    stop.durationMinutes! > 0)
                                  _metaChip(
                                    '${stop.durationMinutes} min',
                                    Icons.timer_outlined,
                                    tm.sapphire,
                                  ),
                                if (stop.category != null)
                                  _metaChip(
                                    _categoryLabel(stop.category!),
                                    Icons.category_outlined,
                                    tm.sapphire,
                                  ),
                                if (stop.rating != null)
                                  _metaChip(
                                    stop.rating!.toStringAsFixed(1),
                                    Icons.star_rounded,
                                    tm.sapphire,
                                  ),
                                if (stop.estimatedCost != null &&
                                    stop.estimatedCost! > 0)
                                  _metaChip(
                                    '\$${stop.estimatedCost!.toStringAsFixed(0)}',
                                    Icons.attach_money,
                                    tm.sapphire,
                                  ),
                              ],
                            ),

                            // AI notes
                            if (stop.aiNotes != null && stop.aiNotes!.isNotEmpty) ...[
                              const SizedBox(height: Spacing.sm),
                              Text(
                                stop.aiNotes!,
                                style: GoogleFonts.inter(
                                  fontSize: 12,
                                  color: tm.textSecondary,
                                  height: 1.4,
                                ),
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],

                            // Travel mode
                            if (stop.travelMode != null &&
                                stop.minutesFromPrevStop != null &&
                                stop.minutesFromPrevStop! > 0) ...[
                              const SizedBox(height: 6),
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(3),
                                    decoration: BoxDecoration(
                                      color: tm.sapphire.withValues(alpha: 0.08),
                                      borderRadius: BorderRadius.circular(6),
                                    ),
                                    child: Icon(
                                      _travelModeIcon(stop.travelMode!),
                                      size: 12,
                                      color: tm.sapphire,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    '${_travelModeLabel(stop.travelMode!)} · ${stop.minutesFromPrevStop} min',
                                    style: GoogleFonts.inter(
                                      fontSize: 11,
                                      color: tm.textTertiary,
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
                                      size: 12, color: tm.sapphireLight),
                                  const SizedBox(width: 3),
                                  Expanded(
                                    child: Text(
                                      stop.address!,
                                      style: GoogleFonts.inter(fontSize: 11, color: tm.textTertiary),
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

  Widget _metaChip(String label, IconData icon, Color accentColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: accentColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: accentColor.withValues(alpha: 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 11, color: accentColor),
          const SizedBox(width: 4),
          Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 10,
              color: accentColor,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Color _timeColor(String? tod) {
    const sapphireColor = Color(0xFF2563EB);
    if (tod == null) return sapphireColor;
    switch (tod.toLowerCase()) {
      case 'morning':
        return const Color(0xFF3B82F6);
      case 'afternoon':
        return const Color(0xFF2563EB);
      case 'evening':
        return const Color(0xFF1D4ED8);
      case 'night':
        return const Color(0xFF1E3A8A);
      default:
        return sapphireColor;
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
// PREMIUM MAP MARKER
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
    final tm = context.tm;
    final color = _markerColor(stop.category);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Premium marker circle with sapphire accent when selected
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutCubic,
          width: isSelected ? 36 : 30,
          height: isSelected ? 36 : 30,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
            border: Border.all(
          color: isSelected ? tm.deepRoyalBlue : tm.brandWhite,
          width: isSelected ? 3 : 2,
        ),
        boxShadow: [
          BoxShadow(
            color: (isSelected ? tm.deepRoyalBlue.withValues(alpha: 0.4) : tm.deepNavy.withValues(alpha: 0.2)),
                blurRadius: isSelected ? 10 : 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Text(
            '$index',
            style: GoogleFonts.inter(
              color: Colors.white,
              fontSize: isSelected ? 13 : 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
        // Pointer arrow
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          width: 0,
          height: 0,
          decoration: BoxDecoration(
            border: Border(
              top: BorderSide(
                color: isSelected ? tm.deepRoyalBlue : color,
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
