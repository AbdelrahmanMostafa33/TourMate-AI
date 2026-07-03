import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/widgets/city_picker.dart';
import '../../data/models/register_request.dart';
import '../../data/repository/auth_repository.dart';
import '../widgets/custom_textfield.dart';
import '../../../../core/errors/auth_error_handler.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  TourMateColors get tm => context.tm;
  final nameController = TextEditingController();
  final phoneController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmController = TextEditingController();

  bool loading = false;
  String _selectedCity = '';

  Future<void> register() async {
    setState(() => loading = true);

    // Basic validation
    if (nameController.text.trim().isEmpty) {
      _showError("Please enter your full name");
      setState(() => loading = false);
      return;
    }
    if (emailController.text.trim().isEmpty) {
      _showError("Please enter your email");
      setState(() => loading = false);
      return;
    }
    if (passwordController.text.length < 6) {
      _showError("Password must be at least 6 characters");
      setState(() => loading = false);
      return;
    }
    if (passwordController.text != confirmController.text) {
      _showError("Passwords do not match");
      setState(() => loading = false);
      return;
    }

    try {
      final firebase = locator<FirebaseAuthService>();
      final authRepo = locator<AuthRepository>();

      /// 1️⃣ Create Firebase user
      await firebase.signUp(
        emailController.text,
        passwordController.text,
      );

      /// 2️⃣ Register in backend
      await authRepo.register(
        RegisterRequest(
          fullName: nameController.text.trim(),
          phoneNumber: phoneController.text.trim(),
          homeCity:
              _selectedCity.isNotEmpty ? _selectedCity : null,
        ),
      );

      if (!mounted) return;

      AppSnackbar.success(context, 'Account created! Sign in to continue.');

      Navigator.pushReplacementNamed(context, "/signin");
    } catch (e) {
      _showError(handleAuthError(e));
    }

    setState(() => loading = false);
  }

  void _showError(String message) {
    if (!mounted) return;
    AppSnackbar.error(context, message);
  }

  @override
  void dispose() {
    nameController.dispose();
    phoneController.dispose();
    emailController.dispose();
    passwordController.dispose();
    confirmController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: tm.nearWhite,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl5),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // ── Logo ──────────────────────────────────────────────
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: Spacing.xl3),
                  child: Image.asset(
                    'assets/images/logo.png',
                    width: 100,
                    height: 100,
                    fit: BoxFit.contain,
                  ),
                ),
                const SizedBox(height: Spacing.xl5),

                // ── Title ─────────────────────────────────────────────
                Text(
                  "Create Account",
                  style: GoogleFonts.inter(
                    fontSize: 26,
                    fontWeight: FontWeight.w700,
                    color: tm.textPrimary,
                    letterSpacing: -0.5,
                    height: 1.1,
                  ),
                ),
                const SizedBox(height: Spacing.xs),
                Text(
                  "Start your travel journey",
                  style: GoogleFonts.inter(
                    fontSize: 14,
                    color: tm.textSecondary,
                    letterSpacing: 0.1,
                    fontWeight: FontWeight.w400,
                    height: 1.3,
                  ),
                ),

                const SizedBox(height: Spacing.xl7),

                // ── Card ──────────────────────────────────────────────
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(Spacing.xl5),
                  decoration: BoxDecoration(
                    color: tm.brandWhite,
                    borderRadius: BorderRadius.circular(RadiusTokens.xl4),
                    border: Border.all(color: tm.borderLight),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.02),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      // ── Form Fields ─────────────────────────────────
                      CustomTextField(
                        controller: nameController,
                        hint: "Full Name",
                        prefixIcon: Icons.person_outline,
                      ),
                      const SizedBox(height: Spacing.xl3),
                      CustomTextField(
                        controller: phoneController,
                        hint: "Phone (optional)",
                        prefixIcon: Icons.phone_outlined,
                      ),

                      const SizedBox(height: Spacing.xl5),

                      CustomTextField(
                        controller: emailController,
                        hint: "Email address",
                        prefixIcon: Icons.email_outlined,
                      ),
                      const SizedBox(height: Spacing.xl3),
                      CustomTextField(
                        controller: passwordController,
                        hint: "Password",
                        isPassword: true,
                        prefixIcon: Icons.lock_outline,
                      ),
                      const SizedBox(height: Spacing.xl3),
                      CustomTextField(
                        controller: confirmController,
                        hint: "Confirm Password",
                        isPassword: true,
                        prefixIcon: Icons.lock_outline,
                      ),
                      const SizedBox(height: Spacing.xl5),
                      CityPicker(
                        initialValue: _selectedCity,
                        onCitySelected: (city) {
                          _selectedCity = city;
                        },
                        darkBackground: false,
                      ),

                      const SizedBox(height: Spacing.xl7),

                      // ── CTA Button ──────────────────────────────────
                      SizedBox(
                        width: double.infinity,
                        height: 52,
                        child: ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: tm.deepRoyalBlue,
                            foregroundColor: tm.brandWhite,
                            elevation: 0,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(RadiusTokens.xl2),
                            ),
                            shadowColor: Colors.transparent,
                          ),
                          onPressed: loading ? null : register,
                          child: loading
                              ? SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                    color: tm.brandWhite,
                                    strokeWidth: 2.5,
                                  ),
                                )
                              : Text(
                                  "Create Account",
                                  style: GoogleFonts.inter(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: Spacing.xl5),

                // ── Sign In Link ──────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      "Already have an account? ",
                      style: GoogleFonts.inter(
                        color: tm.textTertiary,
                        fontSize: 14,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        Navigator.pop(context);
                      },
                      child: Text(
                        "Sign In",
                        style: GoogleFonts.inter(
                          fontWeight: FontWeight.w600,
                          color: tm.sapphire,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: Spacing.xl5),
              ],
            ),
          ),
        ),
      ),
    );
  }

}