import 'dart:io' show Platform;

import 'api_url_storage.dart';

/// Platform-aware API URL configuration.
///
/// Resolves the correct base URL depending on the platform:
/// - **Android emulator**: `10.0.2.2` (special IP to reach host localhost)
/// - **iOS simulator / others**: `localhost`
///
/// Override mechanisms (in order of precedence):
/// 1. **Persisted** via [init] (loads from [FlutterSecureStorage])
/// 2. **Compile-time** via `--dart-define=API_BASE_URL=http://192.168.1.5:8000`
/// 3. **Runtime** via [setBaseUrl] (highest, also persists)
///
/// Call [init] in `main()` **before** `setupLocator()` so that Dio and
/// WebSocket connections start with the correct base URL.
class ApiConfig {
  ApiConfig._();

  // ── Private state ──────────────────────────────────────────

  /// Runtime override (highest precedence).
  static String? _customBaseUrl;

  /// Whether [init] has already been called.
  static bool _initialized = false;

  // ── Lifecycle ──────────────────────────────────────────────

  /// Initialize the config: load a previously saved URL from secure storage.
  ///
  /// Must be called early in `main()`, before [setupLocator].
  /// Safe to call multiple times — only the first call loads storage.
  static Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    final saved = await ApiUrlStorage.loadSavedUrl();
    if (saved != null && saved.isNotEmpty) {
      _customBaseUrl = saved;
    }
  }

  // ── Public API ─────────────────────────────────────────────

  /// Override the detected base URL at runtime.
  ///
  /// Useful for developer settings, QR-code pairing, or manual IP entry.
  /// The URL is **persisted** via [FlutterSecureStorage] and restored on
  /// the next app start via [init].
  static void setBaseUrl(String url) {
    final trimmed = url.trim();
    _customBaseUrl = trimmed.endsWith('/') ? trimmed.substring(0, trimmed.length - 1) : trimmed;

    // Persist so the URL survives app restarts.
    ApiUrlStorage.saveUrl(_customBaseUrl!);
  }

  /// Clear any runtime override and revert to platform detection.
  /// Also removes the persisted URL from secure storage.
  static void resetBaseUrl() {
    _customBaseUrl = null;
    ApiUrlStorage.clearUrl();
  }

  /// HTTP base URL for REST API calls.
  ///
  /// Precedence: runtime override > compile-time define > auto-detect.
  static String get httpBaseUrl {
    if (_customBaseUrl != null) return _customBaseUrl!;

    // Compile-time override via --dart-define=API_BASE_URL=...
    // ignore: avoid_init_to_null
    const define = String.fromEnvironment('API_BASE_URL');
    if (define.isNotEmpty) return define;

    return 'http://$_host:8000';
  }

  /// WebSocket base URL for chat connections (ws:// or wss://).
  static String get wsBaseUrl {
    if (_customBaseUrl != null) {
      return _customBaseUrl!.replaceFirst(RegExp(r'^http'), 'ws');
    }

    const define = String.fromEnvironment('API_BASE_URL');
    if (define.isNotEmpty) {
      return define.replaceFirst(RegExp(r'^http'), 'ws');
    }

    return 'ws://$_host:8000';
  }

  // ── Platform detection ─────────────────────────────────────

  static String get _host {
    // Android emulator uses 10.0.2.2 to reach the host machine's localhost.
    if (Platform.isAndroid) return '10.0.2.2';

    // iOS simulator, macOS, Windows, Linux all use localhost.
    return 'localhost';
  }
}
