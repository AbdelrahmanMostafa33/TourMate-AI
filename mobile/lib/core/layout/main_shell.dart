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
  int _savedTabCounter = 0;

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => TripsCubit(locator<TripsRepository>())),
        BlocProvider(create: (_) => ExploreCubit(locator<ExploreRepository>())),
      ],
      child: Builder(
        builder: (context) {
          final pages = [
            const ChatScreen(),
            const TripsScreen(),
            const ExploreScreen(),
            SavedScreen(key: ValueKey(_savedTabCounter)),
            const ProfileScreen(),
          ];

          return Scaffold(
            backgroundColor: Colors.white,

            /// BODY
            body: IndexedStack(
              index: currentIndex,
              children: pages,
            ),

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
            /// 🔥 Refresh saved places when opening Saved tab
            if (index == 3) {
              _savedTabCounter++;
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