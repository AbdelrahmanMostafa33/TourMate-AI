import 'package:firebase_auth/firebase_auth.dart';

class FirebaseAuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;

  /// Email Signup
  Future<void> signUp(String email, String password) async {
    await _auth.createUserWithEmailAndPassword(
      email: email,
      password: password,
    );
  }

  /// Email Login
  Future<void> signIn(String email, String password) async {
    await _auth.signInWithEmailAndPassword(
      email: email,
      password: password,
    );
  }

  /// Get Firebase token
  Future<String?> getToken() async {
    return await _auth.currentUser?.getIdToken(true);
  }

  /// Sign out
  Future<void> signOut() async {
    await _auth.signOut();
  }
}
