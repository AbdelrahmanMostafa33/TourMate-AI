import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../data/models/trip_summary_model.dart';
import '../../logic/trips_cubit.dart';
import '../../logic/trips_state.dart';

class TripsScreen extends StatefulWidget {
  final void Function(String autoMessage)? onStartChatWithMessage;

  const TripsScreen({super.key, this.onStartChatWithMessage});

  @override
  State<TripsScreen> createState() => _TripsScreenState();
}

class _TripsScreenState extends State<TripsScreen> {
  TourMateColors get tm => context.tm;

  @override
  void initState() {
    super.initState();

    /// 👇 Initial load
    Future.microtask(() {
      if (mounted) context.read<TripsCubit>().getTrips();
    });
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider.value(
      value: locator<TripsCubit>(),
      child: _TripsBody(
        onStartChatWithMessage: widget.onStartChatWithMessage,
      ),
    );
  }
}

class _TripsBody extends StatefulWidget {
  final void Function(String autoMessage)? onStartChatWithMessage;

  const _TripsBody({this.onStartChatWithMessage});

  @override
  State<_TripsBody> createState() => _TripsBodyState();
}

class _TripsBodyState extends State<_TripsBody> {
  TourMateColors get tm => context.tm;

  @override
  void initState() {
    super.initState();

    /// 👇 Initial load
    Future.microtask(() {
      if (mounted) context.read<TripsCubit>().getTrips();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: tm.nearWhite,
      appBar: AppBar(
        backgroundColor: tm.brandWhite,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16, top: 8, bottom: 8),
            child: SizedBox(
              height: 38,
              child: ElevatedButton.icon(
                onPressed: () async {
                  final cubit = context.read<TripsCubit>();
                  final result = await Navigator.pushNamed(context, "/create-trip");
                  if (result is String && result.isNotEmpty) {
                    widget.onStartChatWithMessage?.call(result);
                  } else {
                    cubit.getTrips();
                  }
                },
                icon: Icon(Icons.add_rounded, size: 16, color: tm.sapphireLight),
                label: Text('New Trip', style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: tm.brandWhite)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: tm.deepNavy,
                  foregroundColor: tm.brandWhite,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(RadiusTokens.lg),
                    side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                  ),
                  shadowColor: Colors.transparent,
                ),
              ),
            ),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: tm.divider, height: 0.5),
        ),
      ),

      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xl, Spacing.xl3, Spacing.xl2),
            child: Row(
              children: [
                Row(
                  children: [
                    Container(
                      width: 3,
                      height: 20,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                        borderRadius: BorderRadius.circular(RadiusTokens.xxs),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Text(
                      "Your Trips",
                      style: GoogleFonts.inter(
                        fontSize: 24,
                        fontWeight: FontWeight.w700,
                        color: tm.textPrimary,
                        letterSpacing: -0.4,
                      ),
                    ),
                  ],
                ),
                const Spacer(),
                Container(
                  width: 3,
                  height: 20,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                    ),
                    borderRadius: BorderRadius.circular(RadiusTokens.xxs),
                  ),
                ),
              ],
            ),
          ),

          Expanded(
            child: BlocBuilder<TripsCubit, TripsState>(
              builder: (context, state) {
                return state.when(
                  initial: () => const SizedBox(),
                  loading: () => const TMLoadingIndicator(message: 'Loading your trips...'),
                  creating: () => const TMLoadingIndicator(message: 'Creating your trip...'),
                  created: () => const Center(child: Text("Trip Created!")),
                  error: (message) => TMErrorState(message: message, onRetry: () => context.read<TripsCubit>().getTrips()),
                  loaded: (trips) {
                    if (trips.isEmpty) {
                      return TMEmptyState(
                        icon: Icons.card_travel_outlined,
                        title: 'No trips yet',
                        subtitle: 'Start chatting with TourMate to plan your first adventure.',
                        actionLabel: 'Plan a trip',
                        onAction: () async {
                          final cubit = context.read<TripsCubit>();
                          final result = await Navigator.pushNamed(context, "/create-trip");
                          if (result is String && result.isNotEmpty) {
                            widget.onStartChatWithMessage?.call(result);
                          } else {
                            cubit.getTrips();
                          }
                        },
                      );
                    }

                    return RefreshIndicator(
                      color: tm.deepRoyalBlue,
                      onRefresh: () async {
                        context.read<TripsCubit>().getTrips();
                      },
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
                        itemCount: trips.length,
                        itemBuilder: (context, index) => _tripCard(trips[index], context),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  /// Convert a trip status string to a user-friendly label.
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
        return 'Processing Payment';
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
        // Fallback: replace underscores with spaces and capitalize words
        return status
            .replaceAll('_', ' ')
            .split(' ')
            .map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1)}')
            .join(' ');
    }
  }

  Widget _tripCard(TripSummaryModel trip, BuildContext context) {
    final tm = context.tm;
    final statusLabel = _statusLabel(trip.status);
    final statusBadge = TMStatusBadge(label: statusLabel);

    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.xl3),
      child: Material(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        elevation: 0,
        child: InkWell(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          onTap: () async {
            final cubit = context.read<TripsCubit>();
            final result = await Navigator.pushNamed(context, '/trip-detail', arguments: trip.tripId);
            if (!mounted) return;
            if (result == 'deleted') {
              // Optimistically remove from local state for instant UI update
              cubit.removeTripFromState(trip.tripId);
            } else {
              cubit.getTrips();
            }
          },
          child: Container(
            padding: const EdgeInsets.all(Spacing.xl3),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              color: tm.brandWhite,
              border: Border.all(color: tm.borderLight),
              boxShadow: [
                BoxShadow(
                  blurRadius: 10,
                  color: tm.deepNavy.withValues(alpha: 0.04),
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              children: [
                // Icon with sapphire accent
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.flight_rounded, color: tm.sapphireLight, size: 20),
                ),
                const SizedBox(width: 16),
                // Content
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        trip.destination,
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: tm.textPrimary,
                          letterSpacing: -0.2,
                        ),
                      ),
                      const SizedBox(height: Spacing.xs),
                      Row(
                        children: [
                          if (trip.durationDays > 0) ...[
                            Icon(Icons.calendar_today_outlined, size: 12, color: tm.textTertiary),
                            const SizedBox(width: 4),
                            Text(
                              "${trip.durationDays} day${trip.durationDays > 1 ? 's' : ''}",
                              style: GoogleFonts.inter(color: tm.textSecondary, fontSize: 13),
                            ),
                            const SizedBox(width: 10),
                          ],
                          statusBadge,
                        ],
                      ),
                    ],
                  ),
                ),
                Icon(Icons.chevron_right, color: tm.border, size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}