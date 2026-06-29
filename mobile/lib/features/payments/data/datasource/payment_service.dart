import 'package:flutter_stripe/flutter_stripe.dart';

/// Service that wraps the Stripe Payment Sheet for use across the app.
///
/// Usage: Call `initPaymentSheet(...)` with the `client_secret` from your
/// backend, then call `presentPaymentSheet()` to show the native Stripe UI.
class PaymentService {
  /// Initialize the Stripe Payment Sheet with the given client secret.
  ///
  /// [clientSecret] comes from `POST /flights/book/initiate` on the backend.
  /// [merchantDisplayName] is shown in the sheet header (required on iOS).
  Future<void> initPaymentSheet({
    required String clientSecret,
    String merchantDisplayName = 'TourMate',
  }) async {
    await Stripe.instance.initPaymentSheet(
      paymentSheetParameters: SetupPaymentSheetParameters(
        paymentIntentClientSecret: clientSecret,
        merchantDisplayName: merchantDisplayName,
        // automatic_payment_methods is enabled on the backend side,
        // so Stripe will surface cards, Apple Pay, Google Pay, etc.
      ),
    );
  }

  /// Present the Stripe Payment Sheet to the user.
  ///
  /// Returns `true` if payment succeeded.
  ///
  /// Throws a [StripeException] if payment fails (card declined, network error, etc.).
  Future<bool> presentPaymentSheet() async {
    await Stripe.instance.presentPaymentSheet();
    return true; // Payment succeeded
  }

  /// Convenience: init + present in one call.
  ///
  /// Returns `true` on success, throws on failure.
  Future<bool> payWithStripeSheet({
    required String clientSecret,
    String merchantDisplayName = 'TourMate',
  }) async {
    await initPaymentSheet(
      clientSecret: clientSecret,
      merchantDisplayName: merchantDisplayName,
    );
    return await presentPaymentSheet();
  }
}
