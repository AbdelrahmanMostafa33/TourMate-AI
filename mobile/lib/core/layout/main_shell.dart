import 'package:flutter/material.dart';
import '../../features/auth/presentation/screens/profile_screen.dart';
import '../../features/chat/presentation/screens/chat_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int currentIndex = 0;

  final List<Widget> pages = [
    const ChatScreen(),
    const Placeholder(), // Trips
    const Placeholder(), // Explore
    const Placeholder(), // Saved
    const ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,

      /// ================= BODY =================
      body: IndexedStack(
        index: currentIndex,
        children: pages,
      ),

      /// ================= NAV =================
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
  }

  Widget _navItem(IconData icon, String label, int index) {
    final isActive = currentIndex == index;

    return GestureDetector(
      onTap: () {
        setState(() {
          currentIndex = index;
        });
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
  }
}