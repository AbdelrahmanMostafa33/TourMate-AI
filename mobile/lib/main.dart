import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_stripe/flutter_stripe.dart';
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

  // ── Initialize Stripe with publishable key ────────────────────────────
  // The publishable key is safe to include in the app; the secret key
  // stays server-side.  In production, load this from environment config.
  Stripe.publishableKey = const String.fromEnvironment(
    'STRIPE_PUBLISHABLE_KEY',
    defaultValue: 'pk_test_51Sug26AirNZX1E8p5g6fVMcFYxsTSu77v2GNSQ4fzcPwtIBdMFxdEqKAqYAsdD9ZSUFfWz65buMkngDCoCqQmlVC008tqZjMVo',
  );
  await Stripe.instance.applySettings();

  runApp(const MyApp());
}