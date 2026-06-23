import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/network/service_locator.dart';
import '../../features/chat/presentation/screens/chat_screen.dart';
import '../../features/trips/presentation/screens/trips_screen.dart';
import '../../features/trips/data/repository/trips_repository.dart';
import '../../features/trips/logic/trips_cubit.dart';
import '../../features/explore/presentation/screens/explore_screen.dart';
import '../../features/explore/data/repository/explore_repository.dart';
import '../../features/explore/logic/explore_cubit.dart';
import '../../features/saved/presentation/screens/saved_screen.dart';
import '../../features/auth/presentation/screens/profile_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => TripsCubit(locator<TripsRepository>())),
        BlocProvider(create: (_) => ExploreCubit(locator<ExploreRepository>())),
      ],
      child: Builder(
        builder: (context) {
          return Scaffold(
            backgroundColor: Colors.white,

            /// BODY — only build the active tab so off-screen widgets
            /// (and their Cubits/WebSockets) are disposed.
            body: _buildActivePage(context),

            /// NAVBAR
            bottomNavigationBar: Padding(
              padding: const EdgeInsets.only(bottom: 10, top: 5),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _navItem(Icons.chat_bubble_outline, "Chat", 0),
                  _navItem(Icons.card_travel, "Trips", 1),
                  _navItem(Icons.search, "Explore", 2),
                  _navItem(Icons.favorite_border, "Saved", 3),
                  _navItem(Icons.person, "You", 4),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  /// Returns only the active tab's widget. Unlike [IndexedStack], this
  /// disposes off-screen widgets so their Cubits (and any open WebSockets)
  /// are properly cleaned up when the user switches tabs.
  Widget _buildActivePage(BuildContext context) {
    switch (currentIndex) {
      case 0:
        return ChatScreen(
          onTripCreated: () {
            context.read<TripsCubit>().getTrips();
          },
        );
      case 1:
        return const TripsScreen();
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

  Widget _navItem(IconData icon, String label, int index) {
    final isActive = currentIndex == index;

    return Builder(
      builder: (context) {
        return GestureDetector(
          onTap: () {
            setState(() {
              currentIndex = index;
            });

            /// 🔥 Refresh trips when opening Trips tab
            if (index == 1) {
              context.read<TripsCubit>().getTrips();
            }
            /// 🔥 Refresh explore when opening Explore tab
            if (index == 2) {
              context.read<ExploreCubit>().init();
            }
          },
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircleAvatar(
                radius: 16,
                backgroundColor:
                isActive ? Colors.black : Colors.transparent,
                child: Icon(
                  icon,
                  size: 18,
                  color: isActive ? Colors.white : Colors.grey,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  color: isActive ? Colors.black : Colors.grey,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}