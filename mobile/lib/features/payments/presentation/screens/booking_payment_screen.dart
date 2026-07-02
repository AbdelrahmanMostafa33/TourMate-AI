import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
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
  TourMateColors get tm => context.tm;
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
      backgroundColor: tm.nearWhite,
      appBar: AppBar(
        backgroundColor: tm.brandWhite,
        surfaceTintColor: tm.brandWhite,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        leading: IconButton(
          icon: Icon(Icons.arrow_back_rounded, color: tm.deepNavy),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          children: [
            Container(
              width: 3,
              height: 20,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(width: 10),
            Text(
              'Payment',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: tm.textPrimary,
                letterSpacing: -0.3,
              ),
            ),
          ],
        ),
        centerTitle: false,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: tm.divider, height: 0.5),
        ),
      ),
      body: BlocConsumer<BookingPaymentCubit, BookingPaymentState>(
        listener: (context, state) {
          if (state is BookingPaymentSuccess) {
            final navigator = Navigator.of(context);
            Future.delayed(const Duration(seconds: 2), () {
              if (mounted) navigator.pop(true);
            });
          }
        },
        builder: (context, state) {
          return Padding(
            padding: const EdgeInsets.all(Spacing.xl3),
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  // Amount display
                  Container(
                    padding: const EdgeInsets.all(Spacing.xl3),
                    decoration: BoxDecoration(
                      color: tm.brandWhite,
                      borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                      border: Border.all(color: tm.borderLight),
                      boxShadow: [
                        BoxShadow(
                          color: tm.deepNavy.withValues(alpha: 0.04),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
                    ),
                    child: Column(
                      children: [
                        Text(
                          'Total Amount',
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            color: tm.textTertiary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '\$',
                              style: GoogleFonts.inter(
                                fontSize: 24,
                                fontWeight: FontWeight.w600,
                                color: const Color(0xFF2563EB),
                              ),
                            ),
                            Text(
                              widget.amount.toStringAsFixed(0),
                              style: GoogleFonts.inter(
                                fontSize: 48,
                                fontWeight: FontWeight.w800,
                                color: tm.textPrimary,
                                letterSpacing: -2,
                              ),
                            ),
                            if (widget.amount.toStringAsFixed(2).contains('.')) ...[
                              Text(
                                widget.amount.toStringAsFixed(2).split('.')[1],
                                style: GoogleFonts.inter(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w600,
                                  color: const Color(0xFF2563EB),
                                  letterSpacing: -2,
                                ),
                              ),
                            ],
                          ],
                        ),
                        const SizedBox(height: 4),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: const Color(0xFF2563EB).withValues(alpha: 0.06),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            widget.currency,
                            style: GoogleFonts.inter(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: const Color(0xFF2563EB),
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ],
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
    return GestureDetector(
      onTap: () {
        context.read<BookingPaymentCubit>().paySingleBooking(
              PaySingleBooking(
                bookingId: widget.bookingId,
                paymentMethod: 'credit_card',
                amount: widget.amount,
                currency: widget.currency,
              ),
            );
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF2563EB).withValues(alpha: 0.3), width: 1),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF2563EB).withValues(alpha: 0.08),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.lock, size: 16, color: tm.sapphireLight),
            const SizedBox(width: 10),
            Text(
              'Pay Now',
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: tm.brandWhite,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLoadingState(String message) {
    return Column(
      children: [
        const SizedBox(
          width: 48,
          height: 48,
          child: CircularProgressIndicator(
            strokeWidth: 3,
            color: Color(0xFF2563EB),
          ),
        ),
        const SizedBox(height: 20),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF2563EB).withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: const Color(0xFF2563EB),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                message,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: const Color(0xFF2563EB),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSuccessState(BookingPaymentSuccess state) {
    return Column(
      children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF2563EB).withValues(alpha: 0.3),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: const Icon(Icons.check_rounded, color: Colors.white, size: 36),
        ),
        const SizedBox(height: 20),
        Text(
          'Payment Successful!',
          style: GoogleFonts.inter(
            fontSize: 22,
            fontWeight: FontWeight.w800,
            color: tm.textPrimary,
            letterSpacing: -0.3,
          ),
        ),
        if (state.simulated) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
            decoration: BoxDecoration(
              color: const Color(0xFF2563EB).withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFF2563EB).withValues(alpha: 0.12)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.science_outlined, size: 14, color: const Color(0xFF2563EB)),
                const SizedBox(width: 6),
                Text(
                  'Sandbox mode',
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: const Color(0xFF2563EB),
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildErrorState(BuildContext context, BookingPaymentFailure state) {
    return Column(
      children: [
        Container(
          width: 64,
          height: 64,
          decoration: BoxDecoration(
            color: tm.error.withValues(alpha: 0.08),
            shape: BoxShape.circle,
            border: Border.all(color: tm.error.withValues(alpha: 0.12)),
          ),
          child: Icon(Icons.error_outline_rounded, color: tm.error, size: 32),
        ),
        const SizedBox(height: 20),
        Text(
          'Payment Failed',
          style: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: tm.textPrimary,
            letterSpacing: -0.3,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: tm.error.withValues(alpha: 0.04),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: tm.error.withValues(alpha: 0.08)),
          ),
          child: Text(
            state.error,
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 13,
              color: tm.textSecondary,
              height: 1.4,
            ),
          ),
        ),
        const SizedBox(height: 28),
        GestureDetector(
          onTap: () => Navigator.of(context).pop(false),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
            decoration: BoxDecoration(
              color: tm.brandWhite,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: tm.borderLight),
            ),
            child: Text(
              'Go Back',
              style: GoogleFonts.inter(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: tm.textPrimary,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
