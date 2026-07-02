import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/widgets/city_picker.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../../app/app_theme.dart';
import '../../data/models/user_response.dart';
import '../../data/repository/profile_repository.dart';
import '../../logic/profile_cubit.dart';
import '../../logic/profile_state.dart';

class EditProfileScreen extends StatelessWidget {
  final UserResponse profile;

  const EditProfileScreen({super.key, required this.profile});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ProfileCubit(locator<ProfileRepository>()),
      child: _EditProfileView(profile: profile),
    );
  }
}

class _EditProfileView extends StatefulWidget {
  final UserResponse profile;

  const _EditProfileView({required this.profile});

  @override
  State<_EditProfileView> createState() => _EditProfileViewState();
}

class _EditProfileViewState extends State<_EditProfileView> {
  TourMateColors get tm => context.tm;
  late TextEditingController _nameController;
  late TextEditingController _phoneController;
  String _selectedCity = '';
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.profile.fullName ?? '');
    _phoneController = TextEditingController(text: widget.profile.phoneNumber ?? '');
    _selectedCity = widget.profile.homeCity ?? '';
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _loading = true);

    final cubit = context.read<ProfileCubit>();
    await cubit.updateProfile(
      fullName: _nameController.text.trim().isEmpty
          ? null
          : _nameController.text.trim(),
      phoneNumber: _phoneController.text.trim().isEmpty
          ? null
          : _phoneController.text.trim(),
      homeCity: _selectedCity.isNotEmpty
          ? _selectedCity
          : null,
    );

    if (!mounted) return;
    setState(() => _loading = false);

    // Only pop if update succeeded
    final hasError = cubit.state.maybeWhen(
      error: (_) => true,
      orElse: () => false,
    );
    if (!hasError) {
      Navigator.pop(context, true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: tm.surface,
      appBar: AppBar(
        backgroundColor: tm.pureWhite,
        surfaceTintColor: tm.pureWhite,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: tm.pureBlack),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Edit Profile',
          style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
        ),
        centerTitle: true,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16, top: 8, bottom: 8),
            child: ElevatedButton(
              onPressed: _loading ? null : _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: tm.pureBlack,
                foregroundColor: tm.pureWhite,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16),
              ),
              child: _loading
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        color: tm.goldLight,
                        strokeWidth: 2.5,
                      ),
                    )
                  : Text(
                      'Save',
                      style: GoogleFonts.inter(color: tm.pureWhite, fontWeight: FontWeight.w600, fontSize: 14),
                    ),
            ),
          ),
        ],
      ),        body: BlocListener<ProfileCubit, ProfileState>(
        listener: (context, state) {
          state.whenOrNull(
            error: (message) {
              AppSnackbar.error(context, message);
            },
          );
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(Spacing.xl4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Avatar ───────────────────────────────────
              Center(
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(2.5),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: const LinearGradient(
                          colors: [Color(0xFFC8A84E), Color(0xFFF5ECCE)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFFC8A84E).withValues(alpha: 0.3),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: CircleAvatar(
                        radius: 37.5,
                        backgroundColor: tm.pureBlack,
                        child: Text(
                          (widget.profile.fullName ?? 'U').isNotEmpty
                              ? (widget.profile.fullName ?? 'U')[0]
                              : 'U',
                          style: GoogleFonts.inter(
                            color: tm.goldLight,
                            fontSize: 32,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      widget.profile.email,
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: tm.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),

              // ── Form Fields ──────────────────────────────
              Row(
                children: [
                  Container(
                    width: 3,
                    height: 14,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFFC8A84E), Color(0xFFF5ECCE)],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'PERSONAL INFORMATION',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: tm.textTertiary,
                      letterSpacing: 1,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),

              _buildField(
                label: 'Full Name',
                controller: _nameController,
                icon: Icons.person_outline,
              ),

              const SizedBox(height: 16),

              _buildField(
                label: 'Phone Number',
                controller: _phoneController,
                icon: Icons.phone_outlined,
                keyboardType: TextInputType.phone,
              ),

              const SizedBox(height: 16),

              // ── Home City (Country + City dropdown) ──────
              Text(
                'HOME CITY',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: tm.textTertiary,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 12),
              CityPicker(
                initialValue: _selectedCity,
                onCitySelected: (city) {
                  _selectedCity = city;
                },
              ),

              const SizedBox(height: 40),

              // ── Info text ────────────────────────────────
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: tm.gold.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(RadiusTokens.xl),
                  border: Border.all(color: tm.gold.withValues(alpha: 0.15)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF0A0A0A), Color(0xFF1A1A1A)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Icon(Icons.info_outline, size: 14, color: tm.goldLight),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        'Update your personal details above. Your travel preferences are learned from your chats with TourMate.',
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: tm.textSecondary,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildField({
    required String label,
    required TextEditingController controller,
    required IconData icon,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: GoogleFonts.inter(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: tm.textSecondary,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          decoration: BoxDecoration(
            color: tm.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: tm.borderLight),
          ),
          child: TextField(
            controller: controller,
            keyboardType: keyboardType,
            decoration: InputDecoration(
              prefixIcon: Container(
                margin: const EdgeInsets.only(left: 12, right: 8),
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: tm.gold.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 18, color: tm.gold),
              ),
              border: InputBorder.none,
              contentPadding: Insets.input,
            ),
            style: GoogleFonts.inter(fontSize: 15, color: tm.textPrimary),
          ),
        ),
      ],
    );
  }
}
