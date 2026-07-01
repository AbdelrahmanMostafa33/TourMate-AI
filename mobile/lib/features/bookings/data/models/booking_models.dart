import 'package:equatable/equatable.dart';

/// Wrapper around a raw JSON map response for Retrofit compatibility.
/// Retrofit's generator cannot handle `Map<String, dynamic>` return types
/// directly — it tries to call `dynamic.fromJson()`.  This class provides
/// a proper `fromJson` factory that just returns the raw map as-is.
class JsonMap extends Equatable {
  final Map<String, dynamic> data;

  const JsonMap(this.data);

  factory JsonMap.fromJson(Map<String, dynamic> json) => JsonMap(json);

  @override
  List<Object?> get props => [data];
}

/// Matches the backend PaymentResponse schema.
class PaymentResponse extends Equatable {
  final String paymentId;
  final String bookingId;
  final double amount;
  final String? currency;
  final String paymentMethod;
  final String? provider;
  final String? stripePaymentIntentId;
  final String status;
  final String? transactionReference;
  final String? paidAt;
  final String? createdAt;

  const PaymentResponse({
    required this.paymentId,
    required this.bookingId,
    required this.amount,
    this.currency,
    required this.paymentMethod,
    this.provider,
    this.stripePaymentIntentId,
    required this.status,
    this.transactionReference,
    this.paidAt,
    this.createdAt,
  });

  factory PaymentResponse.fromJson(Map<String, dynamic> json) {
    return PaymentResponse(
      paymentId: json['payment_id'] as String? ?? '',
      bookingId: json['booking_id'] as String? ?? '',
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String?,
      paymentMethod: json['payment_method'] as String? ?? '',
      provider: json['provider'] as String?,
      stripePaymentIntentId: json['stripe_payment_intent_id'] as String?,
      status: json['status'] as String? ?? '',
      transactionReference: json['transaction_reference'] as String?,
      paidAt: json['paid_at'] as String?,
      createdAt: json['created_at'] as String?,
    );
  }

  @override
  List<Object?> get props => [
        paymentId, bookingId, amount, currency, paymentMethod,
        provider, stripePaymentIntentId, status,
        transactionReference, paidAt, createdAt,
      ];
}

/// Matches the backend BookingResponse schema.
class BookingResponse extends Equatable {
  final String bookingId;
  final String tripId;
  final String userId;
  final String? placeId;
  final String bookingType;
  final String? provider;
  final String? confirmationNumber;
  final String? bookingDate;
  final String? startDatetime;
  final String? endDatetime;
  final double? totalCost;
  final String? currency;
  final String status;
  final String? createdAt;
  final PaymentResponse? payment;

  const BookingResponse({
    required this.bookingId,
    required this.tripId,
    required this.userId,
    this.placeId,
    required this.bookingType,
    this.provider,
    this.confirmationNumber,
    this.bookingDate,
    this.startDatetime,
    this.endDatetime,
    this.totalCost,
    this.currency,
    required this.status,
    this.createdAt,
    this.payment,
  });

  factory BookingResponse.fromJson(Map<String, dynamic> json) {
    return BookingResponse(
      bookingId: json['booking_id'] as String? ?? '',
      tripId: json['trip_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      placeId: json['place_id'] as String?,
      bookingType: json['booking_type'] as String? ?? '',
      provider: json['provider'] as String?,
      confirmationNumber: json['confirmation_number'] as String?,
      bookingDate: json['booking_date'] as String?,
      startDatetime: json['start_datetime'] as String?,
      endDatetime: json['end_datetime'] as String?,
      totalCost: (json['total_cost'] as num?)?.toDouble(),
      currency: json['currency'] as String?,
      status: json['status'] as String? ?? '',
      createdAt: json['created_at'] as String?,
      payment: json['payment'] != null
          ? PaymentResponse.fromJson(json['payment'] as Map<String, dynamic>)
          : null,
    );
  }

  @override
  List<Object?> get props => [
        bookingId, tripId, userId, placeId, bookingType,
        provider, confirmationNumber, bookingDate,
        startDatetime, endDatetime, totalCost, currency,
        status, createdAt, payment,
      ];
}


