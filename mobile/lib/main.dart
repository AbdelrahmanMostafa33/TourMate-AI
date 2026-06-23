import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:tourmate/firebase_options.dart';
import 'app/app.dart';
import 'core/network/api_config.dart';
import 'core/network/service_locator.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Load persisted API URL override so Dio starts with the correct base URL.
  await ApiConfig.init();

  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  await setupLocator();

  runApp(const MyApp());
}