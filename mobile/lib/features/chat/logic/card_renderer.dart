import 'package:flutter/material.dart';
import '../logic/chat_segment.dart';
import '../presentation/widgets/itinerary_card.dart' show ItineraryCard;
import '../presentation/widgets/booking_card.dart' show BookingCard;
import '../presentation/widgets/flight_options_card.dart' show FlightOptionsCard;
import '../presentation/widgets/hotel_options_list.dart' show HotelOptionsList;
import '../presentation/widgets/photo_analysis_card.dart' show PhotoAnalysisCard;

// ── Callbacks ──────────────────────────────────────────────────────────────

/// Callbacks passed to every card renderer.
class CardCallbacks {
  final VoidCallback? onApproveItinerary;
  final void Function(dynamic)? onSelectHotel;
  final void Function(dynamic)? onSelectFlight;
  final VoidCallback? onBookingPayNow;
  final VoidCallback? onBookingLater;
  final VoidCallback? onPlanTrip;
  final VoidCallback? onModifyPreferences;
  final VoidCallback? onStartFresh;

  const CardCallbacks({
    this.onApproveItinerary,
    this.onSelectHotel,
    this.onSelectFlight,
    this.onBookingPayNow,
    this.onBookingLater,
    this.onPlanTrip,
    this.onModifyPreferences,
    this.onStartFresh,
  });
}

// ── Abstract Renderer ──────────────────────────────────────────────────────

/// Renders a [CardSegment] for a specific [cardType].
///
/// Implementations must be registered in [CardRendererRegistry] to be
/// available for rendering.
abstract class CardRenderer {
  String get cardType;
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks);
}

// ── Registry ───────────────────────────────────────────────────────────────

/// Pluggable registry of card renderers.
///
/// To add a new card type:
///   1. Implement [CardRenderer].
///   2. Register: `registry.register(MyCardRenderer())`.
///   3. No other code changes needed.
class CardRendererRegistry {
  final Map<String, CardRenderer> _renderers = {};

  void register(CardRenderer renderer) {
    _renderers[renderer.cardType] = renderer;
  }

  CardRenderer? get(String cardType) => _renderers[cardType];

  /// Built-in renderers for all supported card types.
  static CardRendererRegistry get builtIn {
    final reg = CardRendererRegistry();
    reg.register(_ItineraryCardRenderer());
    reg.register(_BookingCardRenderer());
    reg.register(_FlightOptionsCardRenderer());
    reg.register(_HotelOptionsCardRenderer());
    reg.register(_PhotoAnalysisCardRenderer());
    return reg;
  }
}

// ── Built-in renderers ─────────────────────────────────────────────────────

class _ItineraryCardRenderer extends CardRenderer {
  @override
  String get cardType => 'itinerary';

  @override
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks) {
    final itinerary = segment.itinerary;
    if (itinerary == null) return const SizedBox.shrink();
    return ItineraryCard(
      itinerary: itinerary,
      onApprove: callbacks.onApproveItinerary,
    );
  }
}

class _BookingCardRenderer extends CardRenderer {
  @override
  String get cardType => 'booking';

  @override
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks) {
    final booking = segment.booking;
    if (booking == null) return const SizedBox.shrink();
    return BookingCard(
      booking: booking,
      onPayNow: callbacks.onBookingPayNow,
      onLater: callbacks.onBookingLater,
    );
  }
}

class _FlightOptionsCardRenderer extends CardRenderer {
  @override
  String get cardType => 'flight_options';

  @override
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks) {
    final flight = segment.flightOptions;
    if (flight == null) return const SizedBox.shrink();
    return FlightOptionsCard(
      payload: flight,
      onSelectFlight: callbacks.onSelectFlight,
    );
  }
}

class _HotelOptionsCardRenderer extends CardRenderer {
  @override
  String get cardType => 'hotel_options';

  @override
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks) {
    final hotel = segment.hotelOptions;
    if (hotel == null) return const SizedBox.shrink();
    return HotelOptionsList(
      payload: hotel,
      onSelectHotel: callbacks.onSelectHotel,
    );
  }
}

class _PhotoAnalysisCardRenderer extends CardRenderer {
  @override
  String get cardType => 'image_features';

  @override
  Widget build(BuildContext context, CardSegment segment, CardCallbacks callbacks) {
    final photo = segment.photoAnalysis;
    if (photo == null) return const SizedBox.shrink();
    return PhotoAnalysisCard(
      data: photo,
      onPlanTrip: callbacks.onPlanTrip,
      onModifyPreferences: callbacks.onModifyPreferences,
      onStartFresh: callbacks.onStartFresh,
    );
  }
}
