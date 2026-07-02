import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../core/network/service_locator.dart';
import '../../core/theme/design_tokens.dart';
import '../../features/chat/presentation/screens/chat_screen.dart';
import '../../features/trips/presentation/screens/trips_screen.dart';
import '../../features/trips/logic/trips_cubit.dart';
import '../../features/explore/presentation/screens/explore_screen.dart';
import '../../features/saved/presentation/screens/saved_screen.dart';
import '../../features/auth/presentation/screens/profile_screen.dart';
import '../../app/app_theme.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int currentIndex = 0;
  String? _pendingAutoMessage;

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;

    return Scaffold(
      backgroundColor: tm.nearWhite,

      /// BODY — only build the active tab so off-screen widgets
      /// (and their Cubits/WebSockets) are disposed.
      body: _buildActivePage(context),

      /// NAVBAR — Premium sapphire-accented bottom bar
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: tm.pureWhite,
          border: Border(
            top: BorderSide(color: tm.borderLight, width: 0.5),
          ),
          boxShadow: [
            BoxShadow(
              color: tm.pureBlack.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).padding.bottom + 6,
          top: 6,
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          children: [
            _navItem(tm, Icons.chat_bubble_outline, "Chat", 0),
            _navItem(tm, Icons.card_travel_outlined, "Trips", 1),
            _navItem(tm, Icons.search, "Explore", 2),
            _navItem(tm, Icons.favorite_border, "Saved", 3),
            _navItem(tm, Icons.person_outline, "You", 4),
          ],
        ),
      ),
    );
  }

  /// Returns only the active tab's widget. Unlike [IndexedStack], this
  /// disposes off-screen widgets so their Cubits (and any open WebSockets)
  /// are properly cleaned up when the user switches tabs.
  Widget _buildActivePage(BuildContext context) {
    // Read route arguments to check if we need to pass an initialTripId to ChatScreen
    final routeArgs = ModalRoute.of(context)?.settings.arguments;
    final String? initialTripId;
    if (routeArgs is Map<String, dynamic>) {
      initialTripId = routeArgs['trip_id'] as String?;
    } else {
      initialTripId = null;
    }

    switch (currentIndex) {
      case 0:
        final autoMsg = _pendingAutoMessage;
        _pendingAutoMessage = null; // consume it — only send once
        return ChatScreen(
          initialTripId: initialTripId,
          autoMessage: autoMsg,
          onTripCreated: () {
            locator<TripsCubit>().getTrips();
          },
        );
      case 1:
        return TripsScreen(
          onStartChatWithMessage: (msg) {
            setState(() {
              _pendingAutoMessage = msg;
              currentIndex = 0;
            });
          },
        );
      case 2:
        return const ExploreScreen();
      case 3:
        return const SavedScreen();
      case 4:
        return const ProfileScreen();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _navItem(TourMateColors tm, IconData icon, String label, int index) {
    final isActive = currentIndex == index;

    return Builder(
      builder: (context) {
        return GestureDetector(
          onTap: () {
            setState(() {
              currentIndex = index;
            });
            if (index == 1) {
              locator<TripsCubit>().getTrips();
            }
          },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            curve: Curves.easeOutCubic,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              color: isActive ? tm.pureBlack : Colors.transparent,
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              border: isActive
                  ? Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5)
                  : null,
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  icon,
                  size: 20,
                  color: isActive ? tm.pureWhite : tm.navInactive,
                ),
                if (isActive) ...[
                  const SizedBox(width: 6),
                  Text(
                    label,
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: tm.pureWhite,
                      letterSpacing: 0.3,
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}