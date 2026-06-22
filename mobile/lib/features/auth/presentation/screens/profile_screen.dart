import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../data/models/full_profile_response.dart';
import '../../data/repository/profile_repository.dart';
import '../../logic/profile_cubit.dart';
import '../../logic/profile_state.dart';
import 'edit_profile_screen.dart';

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

                success: (data) => _buildProfileContent(context, data),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildProfileContent(BuildContext context, FullProfileResponse data) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 16),

        /// ================= HEADER =================
        Row(
          children: [
            CircleAvatar(
              radius: 32,
              backgroundColor: Colors.black,
              child: Text(
                (data.fullName ?? "U").isNotEmpty
                    ? (data.fullName ?? "U")[0]
                    : "U",
                style: const TextStyle(color: Colors.white, fontSize: 24),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    data.fullName ?? "User",
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    data.email,
                    style: const TextStyle(color: Colors.black54),
                  ),
                ],
              ),
            ),
            // Edit button
            IconButton(
              icon: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.black,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(Icons.edit_outlined,
                    color: Colors.white, size: 18),
              ),
              onPressed: () async {
                final cubit = context.read<ProfileCubit>();
                final result = await Navigator.push<bool>(
                  context,
                  MaterialPageRoute(
                    builder: (_) => EditProfileScreen(profile: data),
                  ),
                );
                if (result == true) {
                  cubit.fetchProfile();
                }
              },
            ),
          ],
        ),

        const SizedBox(height: 24),

        /// ================= INFO CARDS =================
        if (data.phoneNumber != null && data.phoneNumber!.isNotEmpty)
          _infoTile(Icons.phone_outlined, data.phoneNumber!),
        if (data.homeCity != null && data.homeCity!.isNotEmpty)
          _infoTile(Icons.location_city_outlined, data.homeCity!),
        if (data.travelerPersona != null && data.travelerPersona!.isNotEmpty)
          _infoTile(Icons.psychology_outlined, data.travelerPersona!),

        const SizedBox(height: 24),

        /// ================= TRIP PROFILE =================
        if (data.tripProfile != null) ...[
          _sectionHeader("Trip Preferences"),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  blurRadius: 10,
                  color: Colors.black.withValues(alpha: 0.04),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (data.tripProfile!.budgetLevel != null)
                  _prefRow(
                    Icons.attach_money,
                    "Budget",
                    data.tripProfile!.budgetLevel!,
                  ),
                if (data.tripProfile!.travelStyle != null)
                  _prefRow(
                    Icons.explore_outlined,
                    "Style",
                    data.tripProfile!.travelStyle!,
                  ),
                if (data.tripProfile!.pace != null)
                  _prefRow(
                    Icons.speed_outlined,
                    "Pace",
                    data.tripProfile!.pace!,
                  ),
              ],
            ),
          ),
        ],

        const SizedBox(height: 24),

        /// ================= INTERESTS =================
        if (data.tripProfile?.interests != null &&
            data.tripProfile!.interests!.isNotEmpty) ...[
          _sectionHeader("Interests"),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: data.tripProfile!.interests!.map((interest) {
              return Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Text(
                  interest,
                  style: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[700],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              );
            }).toList(),
          ),
        ],

        const Spacer(),

        /// ================= SETTINGS =================
        _sectionHeader("Settings"),
        const SizedBox(height: 12),

        // Retake Quiz
        _settingsTile(
          context,
          icon: Icons.quiz_outlined,
          title: "Retake Onboarding Quiz",
          subtitle: "Update your travel preferences",
          onTap: () {
            Navigator.pushNamed(context, "/quiz");
          },
        ),

        const SizedBox(height: 8),

        // Logout
        _settingsTile(
          context,
          icon: Icons.logout_rounded,
          title: "Sign Out",
          subtitle: "Log out of your account",
          iconColor: Colors.red,
          titleColor: Colors.red,
          onTap: () => _showLogoutDialog(context),
        ),

        const SizedBox(height: 32),
      ],
    );
  }

  Widget _infoTile(IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, size: 18, color: Colors.grey[600]),
          ),
          const SizedBox(width: 12),
          Text(
            text,
            style: const TextStyle(fontSize: 14, color: Colors.black87),
          ),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) {
    return Text(
      title.toUpperCase(),
      style: const TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        color: Colors.grey,
        letterSpacing: 1,
      ),
    );
  }

  Widget _prefRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Icon(icon, size: 16, color: Colors.grey[500]),
          const SizedBox(width: 10),
          Text(
            "$label: ",
            style: TextStyle(
              fontSize: 13,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
          Text(
            _capitalize(value),
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: Colors.black87,
            ),
          ),
        ],
      ),
    );
  }

  Widget _settingsTile(
    BuildContext context, {
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    Color? iconColor,
    Color? titleColor,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.grey.shade100),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: (iconColor ?? Colors.grey).withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  icon,
                  size: 20,
                  color: iconColor ?? Colors.grey[700],
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: titleColor ?? Colors.black87,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[500],
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: Colors.grey[300], size: 20),
            ],
          ),
        ),
      ),
    );
  }

  String _capitalize(String text) {
    if (text.isEmpty) return text;
    return text[0].toUpperCase() + text.substring(1).toLowerCase();
  }

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
        title: const Text("Sign Out"),
        content: const Text("Are you sure you want to sign out?"),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text(
              "Cancel",
              style: TextStyle(color: Colors.grey),
            ),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await _performLogout(context);
            },
            child: const Text(
              "Sign Out",
              style: TextStyle(
                color: Colors.red,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _performLogout(BuildContext context) async {
    try {
      await locator<FirebaseAuthService>().signOut();
      if (!context.mounted) return;
      Navigator.pushNamedAndRemoveUntil(
        context,
        "/signin",
        (route) => false,
      );
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Failed to sign out: $e"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }
}