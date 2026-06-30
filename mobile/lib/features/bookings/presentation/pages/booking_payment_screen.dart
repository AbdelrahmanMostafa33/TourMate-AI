import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../data/repository/booking_repository.dart';
import '../cubit/booking_payment_cubit.dart';

/// A full-page payment screen that auto-starts the Stripe Payment Sheet flow.
///
/// Wraps the body in [BlocProvider] so the cubit is available via
/// [context.read] inside the payment body.
class BookingPaymentPage extends StatefulWidget {
  final String bookingId;
  final String paymentMethod;
  final String? currency;
  final BookingRepository repository;

  const BookingPaymentPage({
    super.key,
    required this.bookingId,
    required this.paymentMethod,
    this.currency,
    required this.repository,
  });

  @override
  State<BookingPaymentPage> createState() => _BookingPaymentPageState();
}

class _BookingPaymentPageState extends State<BookingPaymentPage> {
  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => BookingPaymentCubit(widget.repository),
      child: _BookingPaymentBody(
        bookingId: widget.bookingId,
        paymentMethod: widget.paymentMethod,
        currency: widget.currency,
      ),
    );
  }
}

/// The actual payment UI — placed inside [BlocProvider] so the cubit is
/// accessible via [context.read].  Auto-starts the payment when the widget
/// is first inserted into the tree.
class _BookingPaymentBody extends StatefulWidget {
  final String bookingId;
  final String paymentMethod;
  final String? currency;

  const _BookingPaymentBody({
    required this.bookingId,
    required this.paymentMethod,
    this.currency,
  });

  @override
  State<_BookingPaymentBody> createState() => _BookingPaymentBodyState();
}

class _BookingPaymentBodyState extends State<_BookingPaymentBody> {
  @override
  void initState() {
    super.initState();
    // Auto-start payment after first frame (once cubit is available)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<BookingPaymentCubit>().startPayment(
          bookingId: widget.bookingId,
          paymentMethod: widget.paymentMethod,
          currency: widget.currency,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Payment'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => Navigator.of(context).pop(false),
        ),
      ),
      body: BlocListener<BookingPaymentCubit, BookingPaymentState>(
        listener: (context, state) {
          if (state.status == BookingPaymentStatus.success) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.message ?? 'Payment successful!'),
                backgroundColor: Colors.green,
              ),
            );
            Navigator.of(context).pop(true);
          } else if (state.status == BookingPaymentStatus.failure) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(state.error ?? 'Payment failed.'),
                backgroundColor: Colors.red,
              ),
            );
          }
        },
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: BlocBuilder<BookingPaymentCubit, BookingPaymentState>(
              builder: (context, state) {
                switch (state.status) {
                  case BookingPaymentStatus.initial:
                    return const SizedBox.shrink();

                  case BookingPaymentStatus.initiating:
                    return _buildInitiating();

                  case BookingPaymentStatus.sheetOpen:
                    return _buildSheetOpen(context, state);

                  case BookingPaymentStatus.polling:
                    return _buildPolling(state);

                  case BookingPaymentStatus.success:
                    return _buildSuccess(state);

                  case BookingPaymentStatus.failure:
                    return _buildFailure(context, state);
                }
              },
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInitiating() {
    return const Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        CircularProgressIndicator(),
        SizedBox(height: 24),
        Text(
          'Initiating payment...',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        SizedBox(height: 12),
        Text(
          'Connecting to payment gateway',
          style: TextStyle(color: Colors.grey),
        ),
      ],
    );
  }

  Widget _buildSheetOpen(BuildContext context, BookingPaymentState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.credit_card, size: 64, color: Theme.of(context).primaryColor),
        const SizedBox(height: 24),
        const Text(
          'Complete payment in the\nStripe Payment Sheet',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        SizedBox(height: 12),
        if (state.clientSecret != null && state.clientSecret!.isNotEmpty)
          Text(
            'Client secret received',
            style: TextStyle(color: Colors.green[600]),
          ),
        if (state.simulated)
          const Padding(
            padding: EdgeInsets.only(top: 16),
            child: Chip(
              avatar: Icon(Icons.info_outline, size: 18),
              label: Text('Simulated payment'),
              backgroundColor: Colors.amberAccent,
            ),
          ),
        const SizedBox(height: 24),
        const CircularProgressIndicator(),
      ],
    );
  }

  Widget _buildPolling(BookingPaymentState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const CircularProgressIndicator(),
        const SizedBox(height: 24),
        const Text(
          'Waiting for payment confirmation...',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: 12),
        Text(
          'Polling attempt ${state.pollAttempts} of 15',
          style: const TextStyle(color: Colors.grey),
        ),
        const SizedBox(height: 8),
        LinearProgressIndicator(
          value: state.pollAttempts / 15.0,
        ),
      ],
    );
  }

  Widget _buildSuccess(BookingPaymentState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.check_circle, size: 80, color: Colors.green),
        const SizedBox(height: 24),
        const Text(
          'Payment Successful!',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        Text(
          state.message ?? 'Your booking is confirmed.',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 16, color: Colors.grey),
        ),
      ],
    );
  }

  Widget _buildFailure(BuildContext context, BookingPaymentState state) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.error_outline, size: 80, color: Colors.red),
        const SizedBox(height: 24),
        const Text(
          'Payment Failed',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 12),
        Text(
          state.error ?? 'An unknown error occurred.',
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 14, color: Colors.red),
        ),
        const SizedBox(height: 24),
        ElevatedButton.icon(
          onPressed: () => context.read<BookingPaymentCubit>().startPayment(
            bookingId: widget.bookingId,
            paymentMethod: widget.paymentMethod,
            currency: widget.currency,
          ),
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
      ],
    );
  }
}
