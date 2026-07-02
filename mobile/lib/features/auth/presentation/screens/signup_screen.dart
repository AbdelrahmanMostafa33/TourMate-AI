import 'package:flutter/gestures.dart';
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
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: Spacing.xl7),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // ── Logo ─────────────────────────────────────
                  Container(
                    padding: const EdgeInsets.all(Spacing.xl5),
                    decoration: BoxDecoration(
                      color: tm.sapphire.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(RadiusTokens.xl5),
                      border: Border.all(
                        color: tm.sapphire.withValues(alpha: 0.3),
                        width: 1.5,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: tm.sapphire.withValues(alpha: 0.12),
                          blurRadius: 24,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Icon(
                      Icons.travel_explore_rounded,
                      size: 40,
                      color: tm.sapphire,
                    ),
                  ),
                  const SizedBox(height: Spacing.xl5),
                  // ── Title ────────────────────────────────────
                  Text(
                    "Create Account",
                    style: GoogleFonts.inter(
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                      color: tm.brandWhite,
                      letterSpacing: -0.8,
                      height: 1.1,
                    ),
                  ),
                  const SizedBox(height: Spacing.md),
                  Text(
                    "Start your travel journey",
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: tm.brandWhite.withValues(alpha: 0.6),
                      letterSpacing: 0.5,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                  const SizedBox(height: Spacing.xl7),
                  // ── Form Fields ──────────────────────────────
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
                  const SizedBox(height: Spacing.xl3),
                  CustomTextField(
                    controller: emailController,
                    hint: "Email address",
                    prefixIcon: Icons.email_outlined,
                  ),
                  const SizedBox(height: Spacing.xl3),
                  _buildLabel("Home City"),
                  const SizedBox(height: Spacing.md),
                  CityPicker(
                    initialValue: _selectedCity,
                    onCitySelected: (city) {
                      _selectedCity = city;
                    },
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
                  const SizedBox(height: Spacing.xl7),
                  // ── CTA Button ──────────────────────────
                  SizedBox(
                    width: double.infinity,
                    height: 54,
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
                              width: 22,
                              height: 22,
                              child:                              CircularProgressIndicator(
                                color: tm.brandWhite,
                                strokeWidth: 2.5,
                              ),
                            )
                          : Text(
                              "Create Account",
                              style: GoogleFonts.inter(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: Spacing.xl7),
                  // ── Sign In Link ─────────────────────────────
                  RichText(
                    text: TextSpan(
                      style: GoogleFonts.inter(
                        color: tm.brandWhite.withValues(alpha: 0.7),
                        fontSize: 14,
                      ),
                      children: [
                        TextSpan(text: "Already have an account? "),
                        TextSpan(
                          text: "Sign In",
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.w700,
                            color: tm.sapphireLight,
                            decoration: TextDecoration.underline,
                          ),
                          recognizer: TapGestureRecognizer()
                            ..onTap = () {
                              Navigator.pop(context);
                            },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: Spacing.xl5),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Padding(
      padding: const EdgeInsets.only(left: 4),
      child: Text(
        text,
        style: GoogleFonts.inter(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: tm.brandWhite,
          letterSpacing: 0.3,
        ),
      ),
    );
  }
}