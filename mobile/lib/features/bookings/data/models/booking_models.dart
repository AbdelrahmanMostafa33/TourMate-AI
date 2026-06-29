import 'package:equatable/equatable.dart';

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

/// Matches the backend TripPackageBookingResponse schema.
class TripPackageBookingResponse extends Equatable {
  final String tripId;
  final String? tripName;
  final String destination;
  final double totalCost;
  final String currency;
  final int stopCount;
  final int bookingCount;
  final List<PackageBookingItem> bookings;

  const TripPackageBookingResponse({
    required this.tripId,
    this.tripName,
    required this.destination,
    required this.totalCost,
    required this.currency,
    required this.stopCount,
    required this.bookingCount,
    required this.bookings,
  });

  factory TripPackageBookingResponse.fromJson(Map<String, dynamic> json) {
    return TripPackageBookingResponse(
      tripId: json['trip_id'] as String? ?? '',
      tripName: json['trip_name'] as String?,
      destination: json['destination'] as String? ?? '',
      totalCost: (json['total_cost'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? 'USD',
      stopCount: (json['stop_count'] as num?)?.toInt() ?? 0,
      bookingCount: (json['booking_count'] as num?)?.toInt() ?? 0,
      bookings: (json['bookings'] as List<dynamic>?)
              ?.map((e) =>
                  PackageBookingItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  @override
  List<Object?> get props => [
        tripId, tripName, destination, totalCost, currency,
        stopCount, bookingCount, bookings,
      ];
}

class PackageBookingItem extends Equatable {
  final String bookingId;
  final String placeName;
  final String bookingType;
  final String category;
  final double? totalCost;
  final String? currency;
  final String status;
  final String confirmationNumber;

  const PackageBookingItem({
    required this.bookingId,
    required this.placeName,
    required this.bookingType,
    required this.category,
    this.totalCost,
    this.currency,
    required this.status,
    required this.confirmationNumber,
  });

  factory PackageBookingItem.fromJson(Map<String, dynamic> json) {
    return PackageBookingItem(
      bookingId: json['booking_id'] as String? ?? '',
      placeName: json['place_name'] as String? ?? '',
      bookingType: json['booking_type'] as String? ?? '',
      category: json['category'] as String? ?? '',
      totalCost: (json['total_cost'] as num?)?.toDouble(),
      currency: json['currency'] as String?,
      status: json['status'] as String? ?? '',
      confirmationNumber: json['confirmation_number'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        bookingId, placeName, bookingType, category,
        totalCost, currency, status, confirmationNumber,
      ];
}

/// Matches the backend TripPackagePaymentResponse schema.
class TripPackagePaymentResponse extends Equatable {
  final String tripId;
  final double totalCharged;
  final String currency;
  final int paidCount;
  final int skippedCount;
  final List<PaidBookingItem> paidBookings;
  final List<SkippedBookingItem> skippedBookings;

  const TripPackagePaymentResponse({
    required this.tripId,
    required this.totalCharged,
    required this.currency,
    required this.paidCount,
    required this.skippedCount,
    required this.paidBookings,
    required this.skippedBookings,
  });

  factory TripPackagePaymentResponse.fromJson(Map<String, dynamic> json) {
    return TripPackagePaymentResponse(
      tripId: json['trip_id'] as String? ?? '',
      totalCharged: (json['total_charged'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? 'USD',
      paidCount: (json['paid_count'] as num?)?.toInt() ?? 0,
      skippedCount: (json['skipped_count'] as num?)?.toInt() ?? 0,
      paidBookings: (json['paid_bookings'] as List<dynamic>?)
              ?.map((e) =>
                  PaidBookingItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      skippedBookings: (json['skipped_bookings'] as List<dynamic>?)
              ?.map((e) =>
                  SkippedBookingItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  @override
  List<Object?> get props => [
        tripId, totalCharged, currency, paidCount, skippedCount,
        paidBookings, skippedBookings,
      ];
}

class PaidBookingItem extends Equatable {
  final String bookingId;
  final double amount;
  final String currency;
  final String receiptNumber;
  final String status;

  const PaidBookingItem({
    required this.bookingId,
    required this.amount,
    required this.currency,
    required this.receiptNumber,
    required this.status,
  });

  factory PaidBookingItem.fromJson(Map<String, dynamic> json) {
    return PaidBookingItem(
      bookingId: json['booking_id'] as String? ?? '',
      amount: (json['amount'] as num?)?.toDouble() ?? 0.0,
      currency: json['currency'] as String? ?? '',
      receiptNumber: json['receipt_number'] as String? ?? '',
      status: json['status'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [
        bookingId, amount, currency, receiptNumber, status,
      ];
}

class SkippedBookingItem extends Equatable {
  final String bookingId;
  final String reason;

  const SkippedBookingItem({
    required this.bookingId,
    required this.reason,
  });

  factory SkippedBookingItem.fromJson(Map<String, dynamic> json) {
    return SkippedBookingItem(
      bookingId: json['booking_id'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
    );
  }

  @override
  List<Object?> get props => [bookingId, reason];
}
