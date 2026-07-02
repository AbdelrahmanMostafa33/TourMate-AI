import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../data/models/user_response.dart';
import '../../data/repository/profile_repository.dart';
import '../../logic/profile_cubit.dart';
import '../../logic/profile_state.dart';
import '../widgets/persona_card.dart';
import 'edit_profile_screen.dart';
import '../../../../core/widgets/app_snackbar.dart';

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
    final tm = context.tm;
    return Scaffold(
      backgroundColor: tm.nearWhite,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: BlocBuilder<ProfileCubit, ProfileState>(
            builder: (context, state) {
              return state.when(
                initial: () => const SizedBox(),

                loading: () =>
                const Center(child: TMLoadingIndicator(message: 'Loading profile...')),

                error: (message) => TMErrorState(message: message, onRetry: () => context.read<ProfileCubit>().fetchProfile()),

                success: (data) => _buildProfileContent(context, tm, data),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildProfileContent(BuildContext context, TourMateColors tm, UserResponse data) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
        const SizedBox(height: 16),

        /// ================= HEADER =================
        Row(
          children: [
            Container(
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: CircleAvatar(
                radius: 30,
                backgroundColor: tm.pureBlack,
                child: Text(
                  (data.fullName ?? "U").isNotEmpty
                      ? (data.fullName ?? "U")[0]
                      : "U",
                  style: GoogleFonts.inter(color: tm.sapphireLight, fontSize: 24, fontWeight: FontWeight.w600),
                ),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    data.fullName ?? "User",style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: tm.textPrimary,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    data.email,
                    style: TextStyle(color: tm.textSecondary),
                  ),
                ],
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        /// ================= INFO CARDS =================
        if (data.phoneNumber != null && data.phoneNumber!.isNotEmpty)
          _infoTile(tm, Icons.phone_outlined, data.phoneNumber!),
        if (data.homeCity != null && data.homeCity!.isNotEmpty)
          _infoTile(tm, Icons.location_city_outlined, data.homeCity!),

        const SizedBox(height: 20),

        /// ================= TRAVELER PERSONA =================
        PersonaCard(profile: data),

        const SizedBox(height: 24),

        const SizedBox(height: 24),

        /// ================= SETTINGS =================
        _sectionHeader(tm, "Settings"),
        const SizedBox(height: 12),

        // Edit Profile
        _settingsTile(
          context, tm,
          icon: Icons.edit_outlined,
          title: "Edit Profile",
          subtitle: "Update your personal information",
          onTap: () async {
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

        const SizedBox(height: 8),

        // Sign Out
        _settingsTile(
          context, tm,
          icon: Icons.logout_rounded,
          title: "Sign Out",
          subtitle: "Log out of your account",
          iconColor: Colors.red,
          titleColor: Colors.red,
          onTap: () => _showLogoutDialog(context),
        ),

        const SizedBox(height: 32),
      ],
    ),
  );
  }

  Widget _infoTile(TourMateColors tm, IconData icon, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.sm),
      child: Container(
        padding: const EdgeInsets.all(Spacing.xl3),
        decoration: BoxDecoration(
          color: tm.pureWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          border: Border.all(color: tm.borderLight),
          boxShadow: [
            BoxShadow(
              color: tm.pureBlack.withValues(alpha: 0.03),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
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
              child: Icon(icon, size: 18, color: tm.sapphireLight),
            ),
            const SizedBox(width: 12),
            Text(
              text,
              style: GoogleFonts.inter(fontSize: 14, color: tm.textPrimary, fontWeight: FontWeight.w500),
            ),
          ],
        ),
      ),
    );
  }

  Widget _settingsTile(
    BuildContext context, TourMateColors tm, {
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    Color? iconColor,
    Color? titleColor,
  }) {
    final effectiveColor = iconColor ?? tm.deepRoyalBlue;
    return Material(
      color: tm.pureWhite,
      borderRadius: BorderRadius.circular(RadiusTokens.xl3),
      child: InkWell(
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.all(Spacing.xl3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            border: Border.all(color: tm.borderLight),
            boxShadow: [
              BoxShadow(
                color: tm.pureBlack.withValues(alpha: 0.03),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: effectiveColor.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: effectiveColor.withValues(alpha: 0.15)),
                ),
                child: Icon(icon, size: 20, color: effectiveColor),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: titleColor ?? tm.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(
                  color: effectiveColor.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(Icons.chevron_right, size: 16, color: effectiveColor),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionHeader(TourMateColors tm, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.xs),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 16,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            title,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: tm.textTertiary,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }

  void _showLogoutDialog(BuildContext context) {
    final tm = context.tm;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        ),
        backgroundColor: tm.pureWhite,
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
              child: Icon(Icons.logout_rounded, size: 18, color: tm.error),
            ),
            const SizedBox(width: 10),
            Text(
              'Sign Out',
              style: GoogleFonts.inter(fontWeight: FontWeight.w700, fontSize: 17, color: tm.textPrimary, letterSpacing: -0.2),
            ),
          ],
        ),
        content: Text(
          'Are you sure you want to sign out?',
          style: GoogleFonts.inter(fontSize: 14, color: tm.textSecondary, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            style: TextButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('Cancel', style: GoogleFonts.inter(color: tm.textTertiary, fontWeight: FontWeight.w600, fontSize: 14)),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await _performLogout(context);
            },
            style: TextButton.styleFrom(
              backgroundColor: tm.error.withValues(alpha: 0.08),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text('Sign Out', style: GoogleFonts.inter(color: tm.error, fontWeight: FontWeight.w700, fontSize: 14)),
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
        AppSnackbar.error(context, "Failed to sign out: $e");
    }
  }
}