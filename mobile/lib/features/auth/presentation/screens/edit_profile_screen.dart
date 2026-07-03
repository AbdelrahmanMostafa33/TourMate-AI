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
        backgroundColor: tm.brandWhite,
        surfaceTintColor: tm.brandWhite,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: tm.deepNavy),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Edit Profile',
          style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: tm.textPrimary, letterSpacing: -0.3),
        ),
        centerTitle: true,
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: Spacing.xl3, top: Spacing.md, bottom: Spacing.md),
            child: ElevatedButton(
              onPressed: _loading ? null : _save,
              style: ElevatedButton.styleFrom(
                backgroundColor: tm.deepNavy,
                foregroundColor: tm.brandWhite,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(RadiusTokens.xl),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 16),
              ),
              child: _loading
                  ? SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(
                        color: tm.sapphireLight,
                        strokeWidth: 2.5,
                      ),
                    )
                  : Text(
                      'Save',
                      style: GoogleFonts.inter(color: tm.brandWhite, fontWeight: FontWeight.w600, fontSize: 14),
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
          padding: const EdgeInsets.all(Spacing.xl5),
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
                          colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: CircleAvatar(
                        radius: 37.5,
                        backgroundColor: tm.deepNavy,
                        child: Text(
                          (widget.profile.fullName ?? 'U').isNotEmpty
                              ? (widget.profile.fullName ?? 'U')[0]
                              : 'U',
                          style: GoogleFonts.inter(
                            color: tm.sapphireLight,
                            fontSize: 32,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: Spacing.xl),
                    Text(
                      widget.profile.email,
                      style: GoogleFonts.inter(
                        fontSize: 14,
                        color: tm.textSecondary,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: Spacing.xl7),

              // ── Section header ───────────────────────────
              Row(
                children: [
                  Container(
                    width: 3,
                    height: 16,
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [tm.sapphire, tm.sapphire.withValues(alpha: 0.3)],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),                        borderRadius: BorderRadius.circular(RadiusTokens.xxs),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'PERSONAL INFORMATION',
                    style: GoogleFonts.inter(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: tm.textTertiary,
                      letterSpacing: 1.2,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: Spacing.xl3),

              _buildField(
                label: 'Full Name',
                controller: _nameController,
                icon: Icons.person_outline,
              ),
              const SizedBox(height: Spacing.xl3),
              _buildField(
                label: 'Phone Number',
                controller: _phoneController,
                icon: Icons.phone_outlined,
                keyboardType: TextInputType.phone,
              ),

              const SizedBox(height: Spacing.xl7),

              // ── Home City ────────────────────────────────
              Text(
                'HOME CITY',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: tm.textTertiary,
                  letterSpacing: 1.2,
                  height: 1.3,
                ),
              ),
              const SizedBox(height: Spacing.xl3),
              CityPicker(
                initialValue: _selectedCity,
                onCitySelected: (city) {
                  _selectedCity = city;
                },
                darkBackground: false,
              ),

              const SizedBox(height: Spacing.xl7),

              // ── Info card ────────────────────────────────
              Container(
                padding: const EdgeInsets.all(Spacing.xl3),
                decoration: BoxDecoration(
                  color: tm.sapphire.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                  border: Border.all(color: tm.sapphire.withValues(alpha: 0.12)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        borderRadius: BorderRadius.circular(RadiusTokens.sm),
                      ),
                      child: Icon(Icons.info_outline, size: 14, color: tm.sapphireLight),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Update your personal details above. Your travel preferences are learned from your chats with TourMate.',
                        style: GoogleFonts.inter(
                          fontSize: 13,
                          color: tm.textSecondary,
                          height: 1.5,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: Spacing.xl7),
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
    return _FormField(
      label: label,
      controller: controller,
      icon: icon,
      keyboardType: keyboardType,
      tm: tm,
    );
  }
}

/// A premium form field with animated focus border and shadow.
class _FormField extends StatefulWidget {
  final String label;
  final TextEditingController controller;
  final IconData icon;
  final TextInputType keyboardType;
  final TourMateColors tm;

  const _FormField({
    required this.label,
    required this.controller,
    required this.icon,
    required this.keyboardType,
    required this.tm,
  });

  @override
  State<_FormField> createState() => _FormFieldState();
}

class _FormFieldState extends State<_FormField> {
  bool _isFocused = false;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _focusNode = FocusNode();
    _focusNode.addListener(() {
      if (mounted) setState(() => _isFocused = _focusNode.hasFocus);
    });
  }

  @override
  void dispose() {
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = widget.tm;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.label,
          style: GoogleFonts.inter(
            fontSize: 13,
            fontWeight: FontWeight.w600,
            color: _isFocused ? tm.sapphire : tm.textSecondary,
            height: 1.3,
          ),
        ),
        const SizedBox(height: Spacing.sm),
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOutCubic,
          height: 56,
          decoration: BoxDecoration(
            color: tm.brandWhite,
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            border: Border.all(
              color: _isFocused ? tm.sapphire.withValues(alpha: 0.6) : tm.border,
              width: _isFocused ? 2.0 : 1.0,
            ),
            boxShadow: _isFocused
                ? [
                    BoxShadow(
                      color: tm.sapphire.withValues(alpha: 0.08),
                      blurRadius: 12,
                      offset: const Offset(0, 4),
                    ),
                  ]
                : [],
          ),
          child: TextField(
            controller: widget.controller,
            focusNode: _focusNode,
            keyboardType: widget.keyboardType,
            decoration: InputDecoration(
              prefixIcon: Padding(
                padding: const EdgeInsets.only(left: Spacing.xl3, right: Spacing.lg),
                child: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: _isFocused ? 0.12 : 0.08),
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                  ),
                  child: Icon(widget.icon, size: 18, color: _isFocused ? tm.sapphire : tm.deepRoyalBlue),
                ),
              ),
              border: InputBorder.none,
              contentPadding: const EdgeInsets.symmetric(horizontal: Spacing.xl4, vertical: Spacing.xl3),
            ),
            style: GoogleFonts.inter(fontSize: 15, color: tm.textPrimary, fontWeight: FontWeight.w500),
          ),
        ),
      ],
    );
  }
}
