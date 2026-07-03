import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/errors/api_result.dart';
import '../../data/repository/auth_repository.dart';
import '../../data/repository/profile_repository.dart';
import '../widgets/custom_textfield.dart';
import '../../../../core/errors/auth_error_handler.dart';
import '../../../../core/widgets/app_snackbar.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  TourMateColors get tm => context.tm;

  final emailController = TextEditingController();
  final passwordController = TextEditingController();

  bool loading = false;
  Future<void> login() async {
    setState(() => loading = true);

    try {
      final firebase = locator<FirebaseAuthService>();
      final profileRepo = locator<ProfileRepository>();
      final authRepo = locator<AuthRepository>();

      await firebase.signIn(emailController.text, passwordController.text);

      await authRepo.login();
      final profile = await profileRepo.getProfile();
      if (!mounted) return;

      AppSnackbar.success(context, 'Welcome back! ✨');

      if (profile is Success) {
        Navigator.pushReplacementNamed(context, "/home");
      } else if (profile is Failure) {
        AppSnackbar.error(context, (profile as Failure).message);
      }
    } catch (e) {
      AppSnackbar.error(context, handleAuthError(e));
    }

    setState(() => loading = false);
  }

  @override
  void dispose() {
    emailController.dispose();
    passwordController.dispose();
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
                    width: 120,
                    height: 120,
                    fit: BoxFit.contain,
                  ),
                ),
                const SizedBox(height: Spacing.xl5),

                // ── Title ─────────────────────────────────────────────
                Text(
                  "Welcome Back",
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
                  "Sign in to continue your journey",
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
                        controller: emailController,
                        hint: "Email address",
                      ),
                      const SizedBox(height: Spacing.xl3),
                      CustomTextField(
                        controller: passwordController,
                        hint: "Password",
                        isPassword: true,
                        prefixIcon: Icons.lock_outline,
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
                          onPressed: loading ? null : login,
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
                                  "Sign In",
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

                // ── Sign Up Link ──────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      "New to TourMate? ",
                      style: GoogleFonts.inter(
                        color: tm.textTertiary,
                        fontSize: 14,
                        fontWeight: FontWeight.w400,
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        Navigator.pushNamed(context, "/signup");
                      },
                      child: Text(
                        "Create account",
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