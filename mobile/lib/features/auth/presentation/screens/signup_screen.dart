import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/widgets/city_picker.dart';
import '../../data/models/register_request.dart';
import '../../data/repository/auth_repository.dart';
import '../widgets/custom_textfield.dart';
import '../../../../core/errors/auth_error_handler.dart';
import '../../../../core/widgets/app_snackbar.dart';

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final nameController = TextEditingController();
  final phoneController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmController = TextEditingController();

  bool loading = false;
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
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
            colors: [Color(0xff5e8b8f), Color(0xffdcdcdc)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 28),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(18),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: const Icon(
                      Icons.travel_explore_rounded,
                      size: 40,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    "Create Account",
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                      letterSpacing: -0.5,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    "Start your travel journey",
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.white.withValues(alpha: 0.8),
                    ),
                  ),
                  const SizedBox(height: 28),
                  CustomTextField(
                    controller: nameController,
                    hint: "Full Name",
                  ),
                  const SizedBox(height: 14),
                  CustomTextField(
                    controller: phoneController,
                    hint: "Phone (optional)",
                  ),
                  const SizedBox(height: 14),
                  CustomTextField(
                    controller: emailController,
                    hint: "Email address",
                  ),
                  const SizedBox(height: 14),
                  _buildLabel("Home City"),
                  const SizedBox(height: 6),
                  CityPicker(
                    initialValue: _selectedCity,
                    onCitySelected: (city) {
                      _selectedCity = city;
                    },
                  ),
                  const SizedBox(height: 14),
                  _buildPasswordField(
                    controller: passwordController,
                    hint: "Password",
                    obscure: _obscurePassword,
                    onToggle: () =>
                        setState(() => _obscurePassword = !_obscurePassword),
                  ),
                  const SizedBox(height: 14),
                  _buildPasswordField(
                    controller: confirmController,
                    hint: "Confirm Password",
                    obscure: _obscureConfirm,
                    onToggle: () =>
                        setState(() => _obscureConfirm = !_obscureConfirm),
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    width: double.infinity,
                    height: 54,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      onPressed: loading ? null : register,
                      child: loading
                          ? const SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(
                                color: Colors.white,
                                strokeWidth: 2.5,
                              ),
                            )
                          : const Text(
                              "Create Account",
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  RichText(
                    text: TextSpan(
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.8),
                        fontSize: 14,
                      ),
                      children: [
                        const TextSpan(text: "Already have an account? "),
                        TextSpan(
                          text: "Sign In",
                          style: TextStyle(
                            fontWeight: FontWeight.w700,
                            color: Colors.white.withValues(alpha: 0.95),
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
                  const SizedBox(height: 24),
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
        style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),
    );
  }

  Widget _buildPasswordField({
    required TextEditingController controller,
    required String hint,
    required bool obscure,
    required VoidCallback onToggle,
  }) {
    return Container(
      height: 55,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: TextField(
        controller: controller,
        obscureText: obscure,
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(color: Colors.grey.shade400),
          border: InputBorder.none,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          suffixIcon: IconButton(
            icon: Icon(
              obscure
                  ? Icons.visibility_off_outlined
                  : Icons.visibility_outlined,
              color: Colors.grey.shade500,
              size: 22,
            ),
            onPressed: onToggle,
          ),
        ),
      ),
    );
  }
}