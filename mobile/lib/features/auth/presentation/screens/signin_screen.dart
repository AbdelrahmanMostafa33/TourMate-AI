import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
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
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF0A0A0A), Color(0xFF141414)],
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
                  // Logo
                  Container(
                    padding: const EdgeInsets.all(Spacing.xl5),
                    decoration: BoxDecoration(
                      color: tm.gold.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(RadiusTokens.xl5),
                      border: Border.all(
                        color: tm.gold.withValues(alpha: 0.3),
                        width: 1.5,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: tm.gold.withValues(alpha: 0.12),
                          blurRadius: 24,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Icon(
                      Icons.travel_explore_rounded,
                      size: 40,
                      color: tm.gold,
                    ),
                  ),
                  const SizedBox(height: Spacing.xl7),
                  Text(
                    "Welcome Back",
                    style: GoogleFonts.inter(
                      fontSize: 30,
                      fontWeight: FontWeight.w700,
                      color: tm.pureWhite,
                      letterSpacing: -0.8,
                      height: 1.1,
                    ),
                  ),
                  const SizedBox(height: Spacing.md),
                  Text(
                    "Sign in to continue your journey",
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: tm.pureWhite.withValues(alpha: 0.6),
                      letterSpacing: 0.5,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                  const SizedBox(height: Spacing.xl8),
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
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: tm.gold,
                        foregroundColor: tm.pureBlack,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
                        ),
                        shadowColor: Colors.transparent,
                      ),
                      onPressed: loading ? null : login,
                      child: loading
                          ? SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                color: tm.pureBlack,
                                strokeWidth: 2.5,
                              ),
                            )
                          : Text(
                              "Sign In",
                              style: GoogleFonts.inter(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.5,
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: Spacing.xl7),
                  RichText(
                    text: TextSpan(
                      style: GoogleFonts.inter(
                        color: tm.pureWhite.withValues(alpha: 0.7),
                        fontSize: 14,
                      ),
                      children: [
                        TextSpan(text: "New to TourMate? "),
                        TextSpan(
                          text: "Create account",
                          style: GoogleFonts.inter(
                            fontWeight: FontWeight.w700,
                            color: tm.goldLight,
                            decoration: TextDecoration.underline,
                          ),
                          recognizer: TapGestureRecognizer()
                            ..onTap = () {
                              Navigator.pushNamed(context, "/signup");
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


}