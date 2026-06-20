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

                loading: () =>
                const Center(child: CircularProgressIndicator()),

                error: (message) => Center(child: Text(message)),

                success: (data) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [

                      /// ================= HEADER =================
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 28,
                            backgroundColor: Colors.black,
                            child: Text(
                              (data.fullName ?? "U").isNotEmpty
                                  ? (data.fullName ?? "U")[0]
                                  : "U",
                              style: const TextStyle(color: Colors.white),
                            ),
                          ),
                          const SizedBox(width: 12),

                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                data.fullName ?? "User",
                                style: const TextStyle(
                                  fontSize: 22,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              Text(
                                data.email,
                                style: const TextStyle(
                                  color: Colors.black54,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),

                      const SizedBox(height: 20),

                      /// ================= BASIC INFO =================
                      if (data.phoneNumber != null && data.phoneNumber!.isNotEmpty)
                        Text("Phone: ${data.phoneNumber}"),
                      if (data.homeCity != null && data.homeCity!.isNotEmpty)
                        Text("Home City: ${data.homeCity}"),
                      if (data.travelerPersona != null && data.travelerPersona!.isNotEmpty)
                        Text("Persona: ${data.travelerPersona}"),

                      const SizedBox(height: 20),

                      /// ================= TRIP PROFILE =================
                      if (data.tripProfile != null) ...[
                        const Text(
                          "Trip Profile",
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 10),
                        if (data.tripProfile!.budgetLevel != null)
                          Text("Budget: ${data.tripProfile!.budgetLevel}"),
                        if (data.tripProfile!.travelStyle != null)
                          Text("Style: ${data.tripProfile!.travelStyle}"),
                        if (data.tripProfile!.pace != null)
                          Text("Pace: ${data.tripProfile!.pace}"),
                        const SizedBox(height: 10),
                      ],

                      const SizedBox(height: 20),

                      /// ================= INTERESTS =================
                      if (data.tripProfile?.interests != null && data.tripProfile!.interests!.isNotEmpty) ...[
                        const Text(
                          "INTERESTS",
                          style: TextStyle(
                            color: Colors.grey,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 10,
                          runSpacing: 10,
                          children: data.tripProfile!.interests!.map((interest) {
                            return Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 14,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: Colors.grey.shade300,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(interest),
                            );
                          }).toList(),
                        ),
                      ],

                      const Spacer(),
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

}