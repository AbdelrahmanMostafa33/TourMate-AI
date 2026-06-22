import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';

class FirebaseAuthService {

  final FirebaseAuth _auth = FirebaseAuth.instance;

  /// Email Signup
  Future<void> signUp(String email,String password) async {

    await _auth.createUserWithEmailAndPassword(
      email: email,
      password: password,
    );
  }

  /// Email Login
  Future<void> signIn(String email,String password) async {

    await _auth.signInWithEmailAndPassword(
      email: email,
      password: password,
    );
  }

  /// Google Login
  Future<void> signInWithGoogle() async {

    final GoogleSignInAccount? googleUser =
        await GoogleSignIn().signIn();

    if (googleUser == null) return;

    final GoogleSignInAuthentication googleAuth =
        await googleUser.authentication;

    final credential = GoogleAuthProvider.credential(
      accessToken: googleAuth.accessToken,
      idToken: googleAuth.idToken,
    );

    await _auth.signInWithCredential(credential);
  }

  /// Get Firebase token
  Future<String?> getToken() async {
    return await _auth.currentUser?.getIdToken(true);
  }

  /// Sign out
  Future<void> signOut() async {
    await GoogleSignIn().signOut();
    await _auth.signOut();
  }
}