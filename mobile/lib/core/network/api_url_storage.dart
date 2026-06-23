import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the runtime API URL override using [FlutterSecureStorage].
///
/// The stored URL is loaded on app startup via [loadSavedUrl] so that Dio and
/// WebSocket connections pick it up before any network calls are made.
class ApiUrlStorage {
  ApiUrlStorage._();

  static const _key = 'api_base_url';
  static final _storage = const FlutterSecureStorage();

  /// Read the saved URL from secure storage, or null if none.
  static Future<String?> loadSavedUrl() async {
    try {
      return await _storage.read(key: _key);
    } catch (_) {
      return null;
    }
  }

  /// Save a URL override to secure storage.
  static Future<void> saveUrl(String url) async {
    try {
      await _storage.write(key: _key, value: url);
    } catch (_) {
      // Silently ignore — next app start will use default URL.
    }
  }

  /// Clear the saved URL from secure storage.
  static Future<void> clearUrl() async {
    try {
      await _storage.delete(key: _key);
    } catch (_) {
      // Silently ignore.
    }
  }
}
