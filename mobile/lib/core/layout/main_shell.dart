import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../core/network/service_locator.dart';
import '../../features/chat/presentation/screens/chat_screen.dart';
import '../../features/trips/presentation/screens/trips_screen.dart';
import '../../features/trips/data/repository/trips_repository.dart';
import '../../features/trips/logic/trips_cubit.dart';
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
    return BlocProvider(
      create: (_) => TripsCubit(locator<TripsRepository>()),
      child: Builder(
        builder: (context) {
          final pages = [
            const ChatScreen(),
            const TripsScreen(),
            const Placeholder(),
            const Placeholder(),
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