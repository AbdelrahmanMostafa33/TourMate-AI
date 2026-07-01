import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists booking draft data (flight raw_offer + hotel info) to local
/// storage so it survives app restarts and session switches.
///
/// The draft is keyed by trip ID, so reconnecting to the same trip
/// automatically restores the cached data.
///
/// Cache is cleared when:
///   - The user successfully completes Pay Now (booking confirmed)
///   - The user starts a fresh chat or switches to a different trip
class BookingDraftCache {
  static const String _prefix = 'booking_draft_';

  /// Save the flight booking data (with raw_offer) and hotel info for a trip.
  static Future<void> saveDraft({
    required String tripId,
    Map<String, dynamic>? flightBookingData,
    Map<String, dynamic>? hotelInfo,
  }) async {
    if (tripId.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final payload = <String, dynamic>{};
      if (flightBookingData != null) {
        payload['flight_booking'] = flightBookingData;
      }
      if (hotelInfo != null) {
        payload['hotel_info'] = hotelInfo;
      }
      if (payload.isEmpty) return;
      await prefs.setString('$_prefix$tripId', jsonEncode(payload));
    } catch (e) {
      // Non-critical — failure just means the user may need to re-select.
    }
  }

  /// Load cached booking draft for a trip.
  /// Returns a map with optional `flightBookingData` and `hotelInfo` keys.
  static Future<Map<String, dynamic>?> loadDraft(String tripId) async {
    if (tripId.isEmpty) return null;
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString('$_prefix$tripId');
      if (raw == null || raw.isEmpty) return null;
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return decoded;
    } catch (e) {
      return null;
    }
  }

  /// Clear the cached booking draft for a trip (e.g. after successful payment).
  static Future<void> clearDraft(String tripId) async {
    if (tripId.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('$_prefix$tripId');
    } catch (e) {
      // Non-critical
    }
  }
}
