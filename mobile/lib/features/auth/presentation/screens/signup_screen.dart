import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../../../../core/network/service_locator.dart';
import '../../data/models/register_request.dart';
import '../../data/repository/auth_repository.dart';
import '../widgets/custom_textfield.dart';
import '../../../../core/errors/auth_error_handler.dart';

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {

  final nameController = TextEditingController();
  final phoneController = TextEditingController();
  final emailController = TextEditingController();
  final homeCityController = TextEditingController();
  final passwordController = TextEditingController();
  final confirmController = TextEditingController();

  bool loading = false;

  Future<void> register() async {

    setState(() => loading = true);

    try {

      final firebase =
      locator<FirebaseAuthService>();

      final authRepo =
      locator<AuthRepository>();

      /// 1️⃣ create firebase user
      await firebase.signUp(
        emailController.text,
        passwordController.text,
      );

      /// 2️⃣ register in backend
      await authRepo.register(
        RegisterRequest(
          fullName: nameController.text,
          phoneNumber: phoneController.text,
          homeCity: homeCityController.text,
        ),
      );

      if (!mounted) return;

      Navigator.pushReplacementNamed(
        context,
        "/signin",
      );

    } catch(e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(handleAuthError(e)),    // ✅ nice
          backgroundColor: Colors.red.shade700,
        ),
      );
    }

    setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(

      body: Container(

        padding: const EdgeInsets.symmetric(horizontal: 25),

        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Color(0xff5e8b8f),
              Color(0xffdcdcdc),
            ],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),

        child: SafeArea(

          child: Column(

            mainAxisAlignment: MainAxisAlignment.center,

            children: [

              const Text(
                "Sign up to continue",
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w500,
                ),
              ),

              const SizedBox(height: 30),

              CustomTextField(
                controller: nameController,
                hint: "Full Name",
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: phoneController,
                hint: "Phone",
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: emailController,
                hint: "Email",
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: homeCityController,
                hint: "Home City",
                isPassword: true,
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: passwordController,
                hint: "Password",
                isPassword: true,
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: confirmController,
                hint: "Confirm Password",
                isPassword: true,
              ),

              const SizedBox(height: 30),

              SizedBox(
                width: double.infinity,
                height: 55,

                child: ElevatedButton(

                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.black,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                  ),

                  onPressed: loading ? null : register,

                  child: loading
                      ? const CircularProgressIndicator(
                      color: Colors.white)
                      : const Text(
                    "Sign up",
                    style: TextStyle(fontSize: 16, color: Colors.white),
                  ),
                ),
              ),

              const SizedBox(height: 20),

              RichText(
                text: TextSpan(
                  style: const TextStyle(
                    color: Colors.black,
                    fontSize: 14,
                  ),
                  children: [
                    const TextSpan(text: "Already have an account? "),
                    TextSpan(
                      text: "Sign In",
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                      ),
                      recognizer: TapGestureRecognizer()
                        ..onTap = () {
                          Navigator.pop(context);
                        },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}