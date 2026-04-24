import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) throw UnsupportedError('Web not configured.');
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      default:
        throw UnsupportedError('Platform not configured.');
    }
  }

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyB1-azpEy9nkCK8pzBf-MZLF3F9DTRVsm4',
    appId: '1:419367078732:android:b1da2a01c82ccc5aaa5de9',
    messagingSenderId: '419367078732',
    projectId: 'tourmate-ai-62a20',
    storageBucket: 'tourmate-ai-62a20.firebasestorage.app',
  );
}