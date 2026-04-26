import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/repository/profile_repository.dart';
import '../../logic/profile_cubit.dart';
import '../../logic/profile_state.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) =>
      ProfileCubit(locator<ProfileRepository>())..fetchProfile(),
      child: const _ProfileView(),
    );
  }
}

class _ProfileView extends StatelessWidget {
  const _ProfileView();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF4F4F4),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: BlocBuilder<ProfileCubit, ProfileState>(
            builder: (context, state) {
              return state.when(
                initial: () => const SizedBox(),

                loading: () => const Center(
                  child: CircularProgressIndicator(),
                ),

                error: (message) => Center(
                  child: Text(message),
                ),

                success: (data) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      /// HEADER
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          /// AVATAR
                          CircleAvatar(
                            radius: 28,
                            backgroundColor: Colors.black,
                            child: Text(
                              data.personaName.isNotEmpty
                                  ? data.personaName[0]
                                  : "A",
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                              ),
                            ),
                          ),

                          const SizedBox(width: 12),

                          /// NAME + INFO
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                data.personaName,
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Row(
                                children: const [
                                  Icon(Icons.location_on,
                                      size: 16, color: Colors.black54),
                                  SizedBox(width: 4),
                                  Text(
                                    "Cairo,Egypt",
                                    style: TextStyle(color: Colors.black54),
                                  ),
                                ],
                              ),
                            ],
                          ),

                          const Spacer(),

                          /// MORE BUTTON
                          Container(
                            decoration: BoxDecoration(
                              color: Colors.grey.shade200,
                              shape: BoxShape.circle,
                            ),
                            child: const Padding(
                              padding: EdgeInsets.all(8),
                              child: Icon(Icons.more_vert),
                            ),
                          ),
                        ],
                      ),

                      const SizedBox(height: 20),

                      Center(
                        child:
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 8,
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                data.personaName,
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.bold,
                                ),
                              )
                            ],
                          ),
                        ),
                      ),

                      const SizedBox(height: 16),

                      /// DIVIDER
                      Container(
                        height: 1,
                        color: Colors.black26,
                      ),

                      const SizedBox(height: 16),

                      /// BIO CARD
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Colors.transparent,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: Colors.grey.shade400),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              data.personaBio,
                              style: const TextStyle(
                                height: 1.5,
                                fontSize: 14,
                              ),
                            ),
                            const SizedBox(height: 12),

                            /// RETAKE BUTTON
                            Align(
                              alignment: Alignment.bottomRight,
                              child: ElevatedButton(
                                onPressed: () {
                                  Navigator.pushReplacementNamed(
                                      context, "/quiz");
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.black,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 18,
                                    vertical: 10,
                                  ),
                                  shape: RoundedRectangleBorder(
                                    borderRadius:
                                    BorderRadius.circular(20),
                                  ),
                                ),
                                child: Text(
                                  data.quizCompleted?"Retake Quiz": "Take Quiz",
                                  style: TextStyle(color: Colors.white),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 20),

                      /// INTERESTS TITLE
                      const Text(
                        "INTERESTS",
                        style: TextStyle(
                          color: Colors.grey,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 1,
                        ),
                      ),

                      const SizedBox(height: 12),

                      /// INTERESTS CHIPS
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: data.interests.map((interest) {
                          return Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade300,
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              interest,
                              style: const TextStyle(fontSize: 13),
                            ),
                          );
                        }).toList(),
                      ),

                      const Spacer(),

                      /// BOTTOM NAV (STATIC LIKE DESIGN)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceAround,
                          children: [
                            _navItem(Icons.chat_bubble_outline, "Chat"),
                            _navItem(Icons.card_travel, "Trips"),
                            _navItem(Icons.search, "Explore"),
                            _navItem(Icons.favorite_border, "Saved"),
                            _navItem(Icons.person, "You", isActive: true),
                          ],
                        ),
                      ),
                    ],
                  );
                },
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _navItem(IconData icon, String label,
      {bool isActive = false}) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircleAvatar(
          radius: 16,
          backgroundColor: isActive ? Colors.black : Colors.transparent,
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
    );
  }
}