import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import '../../../../core/errors/api_result.dart';
import '../../data/datasource/firebase_auth_service.dart';
import '../../../../core/network/service_locator.dart';
import '../../../quiz/data/repository/quiz_repository.dart';
import '../../data/repository/auth_repository.dart';
import '../../data/repository/profile_repository.dart';
import '../widgets/custom_textfield.dart';
import '../../../../core/errors/auth_error_handler.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {

  final emailController = TextEditingController();
  final passwordController = TextEditingController();

  bool loading = false;

  Future<void> login() async {
    setState(() => loading = true);

    try {
      final firebase = locator<FirebaseAuthService>();
      final profileRepo = locator<ProfileRepository>();
      final authRepo = locator<AuthRepository>();
      /// 1. Firebase login
      await firebase.signIn(
        emailController.text,
        passwordController.text,
      );

      /// 2. Backend login (GET USER DATA)
      await authRepo.login();
      final profile = await profileRepo.getProfile();
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Login successful")),
      );

      /// 3. NAVIGATION LOGIC 🔥
      profile.when(
        success: (profile) {
          if (profile.quizCompleted) {
            Navigator.pushReplacementNamed(context, "/home");
          } else {
            Navigator.pushReplacementNamed(context, "/quiz-decision");
          }
        },
        failure: (message) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(message),
              backgroundColor: Colors.red,
            ),
          );
        },
      );

    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(handleAuthError(e)),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }

    setState(() => loading = false);
  }

  Future<void> googleLogin() async {

    setState(() => loading = true);

    try {

      final firebase = locator<FirebaseAuthService>();
      final repo = locator<AuthRepository>();
      final profileRepo = locator<ProfileRepository>();
      final quizRepo = locator<QuizRepository>();

      await firebase.signInWithGoogle();

      await repo.login();

      if(!mounted) return;

      final result = await profileRepo.getProfile();

      await result.when(
        success: (profile) async {
          /// Profile exists → do nothing
        },
        failure: (message) async {
          /// If profile NOT found → create default profile
          if (message.contains("not found") || message.contains("404")) {
            await quizRepo.skipQuiz();
          } else {
            throw Exception(message); // real error
          }
        },
      );

      /// Fetch profile again AFTER ensuring it exists
      final profile = await profileRepo.getProfile();

      /// 3. NAVIGATION LOGIC 🔥
      profile.when(
        success: (profile) {
          if (profile.quizCompleted) {
            Navigator.pushReplacementNamed(context, "/profile");
          } else {
            Navigator.pushReplacementNamed(context, "/quiz-decision");
          }
        },
        failure: (message) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(message),
              backgroundColor: Colors.red,
            ),
          );
        },
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
                "Sign In",
                style: TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w500,
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
                    const TextSpan(text: "New to TourMate? "),
                    TextSpan(
                      text: "Sign up",
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                      ),
                      recognizer: TapGestureRecognizer()
                        ..onTap = () {
                          Navigator.pushNamed(context, "/signup");
                        },
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 30),

              CustomTextField(
                controller: emailController,
                hint: "Email",
              ),

              const SizedBox(height: 15),

              CustomTextField(
                controller: passwordController,
                hint: "Password",
                isPassword: true,
              ),

              const SizedBox(height: 25),

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

                  onPressed: loading ? null : login,

                  child: loading
                      ? const CircularProgressIndicator(
                      color: Colors.white)
                      : const Text("Continue",
                      style: TextStyle(fontSize: 16, color: Colors.white)
                  ),
                ),
              ),

              const SizedBox(height: 30),

              /// Google Login Button
              GestureDetector(
                onTap: googleLogin,
                child: Container(
                  height: 55,
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(30),
                    border: Border.all(color: Colors.grey.shade300),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Image.asset('assets/images/google.png', height: 24, width: 24),
                      const SizedBox(width: 10),
                      const Text("Continue with Google"),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 15),
            ],
          ),
        ),
      ),
    );
  }

  Widget socialButton({
    required IconData icon,
    required String text,
    required VoidCallback onTap,
  }) {

    return GestureDetector(

      onTap: onTap,

      child: Container(

        height: 55,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(30),
        ),

        child: Row(

          mainAxisAlignment: MainAxisAlignment.center,

          children: [

            Icon(icon),

            const SizedBox(width: 10),

            Text(text),
          ],
        ),
      ),
    );
  }
}