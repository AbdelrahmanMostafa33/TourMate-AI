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

  /// Full async payment flow for a single booking:
  /// 1. Calls the backend to initiate payment (gets client_secret)
  /// 2. Opens the Stripe Payment Sheet for card entry
  /// 3. Handles success/failure
  ///
  /// [payFuture] is a function that calls the backend and returns the payment
  ///   result map (must contain 'client_secret' and 'stripe_payment_intent_id').
  /// [merchantDisplayName] is shown in the sheet header (iOS).
  ///
  /// Returns a [BookingPaymentResult] with the outcome.
  Future<BookingPaymentResult> processBookingPayment({
    required Future<Map<String, dynamic>> Function() payFuture,
    required String bookingId,
    String merchantDisplayName = 'TourMate',
  }) async {
    try {
      // Step 1: Call the backend to initiate payment
      final result = await payFuture();

      final clientSecret = result['client_secret'] as String?;
      final isSimulated = result['simulated'] == true;
      final paymentId = result['payment_id'] as String?;
      final stripePiId = result['stripe_payment_intent_id'] as String?;

      // Step 2: If real Stripe and we have a client_secret, open the Payment Sheet
      // Skip the sheet for simulated payments (no real Stripe API)
      if (!isSimulated && clientSecret != null && clientSecret.isNotEmpty) {
        final sheetResult = await payWithStripeSheet(
          clientSecret: clientSecret,
          merchantDisplayName: merchantDisplayName,
        );
        if (!sheetResult) {
          return BookingPaymentResult(
            success: false,
            bookingId: bookingId,
            error: 'Payment was cancelled or failed in the sheet.',
          );
        }
      }

      // Step 3: Payment succeeded (or was simulated)
      return BookingPaymentResult(
        success: true,
        bookingId: bookingId,
        paymentId: paymentId,
        stripePaymentIntentId: stripePiId,
        clientSecret: clientSecret,
        simulated: isSimulated,
        message: result['message'] as String?,
      );
    } catch (e) {
      return BookingPaymentResult(
        success: false,
        bookingId: bookingId,
        error: e.toString(),
      );
    }
  }
}

/// Result of a Booking payment flow.
class BookingPaymentResult {
  final bool success;
  final String bookingId;
  final String? paymentId;
  final String? stripePaymentIntentId;
  final String? clientSecret;
  final bool simulated;
  final String? message;
  final String? error;

  const BookingPaymentResult({
    required this.success,
    required this.bookingId,
    this.paymentId,
    this.stripePaymentIntentId,
    this.clientSecret,
    this.simulated = false,
    this.message,
    this.error,
  });
}
