import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../core/network/service_locator.dart';
import '../../../bookings/data/repository/booking_repository.dart';
import '../../data/datasource/payment_service.dart';
import '../cubit/booking_payment_cubit.dart';

/// Full-screen page for processing a booking payment via Stripe Payment Sheet.
///
/// Usage:
/// ```dart
/// Navigator.push(
///   context,
///   MaterialPageRoute(
///     builder: (_) => BookingPaymentPage(
///       bookingId: booking.bookingId,
///       tripId: booking.tripId,
///       amount: booking.totalCost ?? 0,
///       currency: booking.currency ?? 'USD',
///     ),
///   ),
/// );
/// ```
class BookingPaymentPage extends StatelessWidget {
  final String bookingId;
  final String? tripId;
  final double amount;
  final String currency;

  const BookingPaymentPage({
    super.key,
    required this.bookingId,
    this.tripId,
    required this.amount,
    this.currency = 'USD',
  });

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => BookingPaymentCubit(
        bookingRepo: locator<BookingRepository>(),
        paymentService: locator<PaymentService>(),
      ),
      child: _BookingPaymentView(
        bookingId: bookingId,
        tripId: tripId,
        amount: amount,
        currency: currency,
      ),
    );
  }
}

class _BookingPaymentView extends StatefulWidget {
  final String bookingId;
  final String? tripId;
  final double amount;
  final String currency;

  const _BookingPaymentView({
    required this.bookingId,
    this.tripId,
    required this.amount,
    this.currency = 'USD',
  });

  @override
  State<_BookingPaymentView> createState() => _BookingPaymentViewState();
}

class _BookingPaymentViewState extends State<_BookingPaymentView> {
  @override
  void initState() {
    super.initState();
    // Start payment automatically when the page loads
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<BookingPaymentCubit>().paySingleBooking(
            PaySingleBooking(
              bookingId: widget.bookingId,
              paymentMethod: 'credit_card',
              amount: widget.amount,
              currency: widget.currency,
            ),
          );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment')),
      body: BlocConsumer<BookingPaymentCubit, BookingPaymentState>(
        listener: (context, state) {
          if (state is BookingPaymentSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  state.simulated
                      ? 'Payment successful (sandbox)'
                      : 'Payment successful!',
                ),
                backgroundColor: Colors.green,
              ),
            );
            // Pop back after a short delay
            final navigator = Navigator.of(context);
            Future.delayed(const Duration(seconds: 1), () {
              if (mounted) navigator.pop(true);
            });
          } else if (state is BookingPaymentFailure) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Payment failed: ${state.error}'),
                backgroundColor: Colors.red,
              ),
            );
          }
        },
        builder: (context, state) {
          return Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Amount display
                  Text(
                    '\$${widget.amount.toStringAsFixed(2)}',
                    style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    widget.currency,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: Colors.grey,
                        ),
                  ),
                  const SizedBox(height: 32),

                  // Status indicator
                  if (state is BookingPaymentInitial)
                    _buildPaymentButton(context),
                  if (state is BookingPaymentInitiating)
                    _buildLoadingState('Initiating payment...'),
                  if (state is BookingPaymentSheetOpen)
                    _buildLoadingState('Complete payment in the sheet...'),
                  if (state is BookingPaymentSuccess)
                    _buildSuccessState(state),
                  if (state is BookingPaymentFailure)
                    _buildErrorState(context, state),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildPaymentButton(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: () {
        context.read<BookingPaymentCubit>().paySingleBooking(
              PaySingleBooking(
                bookingId: widget.bookingId,
                paymentMethod: 'credit_card',
                amount: widget.amount,
                currency: widget.currency,
              ),
            );
      },
      icon: const Icon(Icons.lock),
      label: const Text('Pay Now'),
      style: ElevatedButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16),
      ),
    );
  }

  Widget _buildLoadingState(String message) {
    return Column(
      children: [
        const CircularProgressIndicator(),
        const SizedBox(height: 16),
        Text(message, style: const TextStyle(fontSize: 16)),
      ],
    );
  }

  Widget _buildSuccessState(BookingPaymentSuccess state) {
    return Column(
      children: [
        const Icon(Icons.check_circle, color: Colors.green, size: 64),
        const SizedBox(height: 16),
        const Text(
          'Payment Successful!',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        if (state.simulated)
          const Text(
            '(Sandbox mode)',
            style: TextStyle(color: Colors.grey),
          ),
      ],
    );
  }

  Widget _buildErrorState(BuildContext context, BookingPaymentFailure state) {
    return Column(
      children: [
        const Icon(Icons.error, color: Colors.red, size: 64),
        const SizedBox(height: 16),
        Text(
          state.error,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 14),
        ),
        const SizedBox(height: 24),
        ElevatedButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Go Back'),
        ),
      ],
    );
  }
}
