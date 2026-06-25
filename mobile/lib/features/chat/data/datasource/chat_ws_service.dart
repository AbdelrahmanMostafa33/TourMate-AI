import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:stream_channel/stream_channel.dart';
import 'package:web_socket_channel/io.dart';
import '../../../../core/network/api_config.dart';
import '../../../auth/data/datasource/firebase_auth_service.dart';

/// Connection state for the WebSocket.
enum WsConnectionState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  failed,
}

/// Tracks the last connection parameters so we can reconnect with the same
/// mode after an unexpected disconnect.
class _ConnectionParams {
  final bool isNewChat;
  final String? tripId;
  final String? autoMsg;

  const _ConnectionParams({
    required this.isNewChat,
    this.tripId,
    this.autoMsg,
  });
}

class ChatWebSocketService {
  StreamChannel<dynamic>? _channel;
  StreamSubscription<dynamic>? _wsSubscription;
  Timer? _reconnectTimer;

  final FirebaseAuthService _authService;

  /// Current connection state.
  WsConnectionState _state = WsConnectionState.disconnected;
  WsConnectionState get state => _state;

  /// Stream of connection state changes.
  final _stateController = StreamController<WsConnectionState>.broadcast();
  Stream<WsConnectionState> get stateStream => _stateController.stream;

  /// Broadcast relay for incoming WebSocket messages.
  ///
  /// The raw channel stream is single-subscription, so we relay events
  /// through this broadcast controller so that both the internal
  /// `_wsSubscription` (for error/completion detection) AND the cubit's
  /// listener can coexist without a "Stream has already been listened to"
  /// error.
  final _messageController = StreamController<dynamic>.broadcast();

  /// Current reconnect attempt (resets on successful connect or manual disconnect).
  int _reconnectAttempt = 0;
  final int _maxReconnectAttempts;
  final Duration _initialBackoff;
  final Duration _maxBackoff;

  /// Whether the user explicitly called [disconnect]. When true, we will NOT
  /// auto-reconnect -- the user intentionally left the chat.
  bool _userDisconnected = false;

  /// Last connection parameters, used for automatic reconnection.
  _ConnectionParams? _lastParams;

  /// Optional factory for creating WebSocket channels (injectable for testing).
  final StreamChannel<dynamic> Function(String url)? _channelFactory;

  ChatWebSocketService(
    this._authService, {
    StreamChannel<dynamic> Function(String url)? channelFactory,
    int maxReconnectAttempts = 6,
    Duration initialBackoff = const Duration(seconds: 1),
    Duration maxBackoff = const Duration(seconds: 30),
  })  : _channelFactory = channelFactory,
        _maxReconnectAttempts = maxReconnectAttempts,
        _initialBackoff = initialBackoff,
        _maxBackoff = maxBackoff;

  /// Stream of incoming WebSocket messages.
  ///
  /// This is a broadcast stream relayed from the raw channel, so
  /// multiple listeners are safe.
  Stream<dynamic> get stream => _messageController.stream;

  // -- Public API ---------------------------------------------------------

  /// Connect to a new (fresh) chat session.
  Future<void> connectNewChat() async {
    _userDisconnected = false;
    _reconnectAttempt = 0;
    _lastParams = const _ConnectionParams(isNewChat: true);
    await _connect();
  }

  /// Connect to an existing trip's chat session.
  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    _userDisconnected = false;
    _reconnectAttempt = 0;
    _lastParams = _ConnectionParams(
      isNewChat: false,
      tripId: tripId,
      autoMsg: autoMsg,
    );
    await _connect();
  }

  void sendMessage(String message, {Uint8List? imageBytes}) {
    final payload = <String, dynamic>{"message": message};
    if (imageBytes != null) {
      payload["image"] = base64Encode(imageBytes);
    }
    _channel?.sink.add(jsonEncode(payload));
  }

  /// Explicitly disconnect. Disables automatic reconnection.
  void disconnect() {
    _userDisconnected = true;
    _cancelReconnect();
    _cleanup();
    _setState(WsConnectionState.disconnected);
  }

  /// Dispose all resources.
  void dispose() {
    _userDisconnected = true;
    _cancelReconnect();
    _cleanup();
    if (!_stateController.isClosed) {
      _stateController.add(WsConnectionState.disconnected);
      _stateController.close();
    }
    if (!_messageController.isClosed) {
      _messageController.close();
    }
    _state = WsConnectionState.disconnected;
  }

  // -- Internal -----------------------------------------------------------

  Future<void> _connect() async {
    if (_state == WsConnectionState.connecting ||
        _state == WsConnectionState.connected) {
      debugPrint('[WS] _connect: already $_state, skipping');
      return;
    }

    _setState(WsConnectionState.connecting);

    try {
      final token = await _authService.getToken();
      final url = _buildUrl(token);
      debugPrint('[WS] _connect: url=${url.split('?').first}… (token=${token != null ? 'present' : 'null'})');
      _channel = _channelFactory != null
          ? _channelFactory(url)
          : IOWebSocketChannel.connect(url) as StreamChannel<dynamic>;

      // Listen for connection close to trigger reconnection,
      // and relay data messages through the broadcast controller.
      _wsSubscription?.cancel();
      _wsSubscription = _channel!.stream.listen(
        (data) {
          // Relay all messages to the broadcast controller for the cubit.
          if (!_messageController.isClosed) {
            _messageController.add(data);
          }
        },
        onError: (e) {
          debugPrint('[WS] _connect: stream onError: $e');
          _onConnectionLost();
        },
        onDone: () {
          debugPrint('[WS] _connect: stream onDone (connection closed)');
          _onConnectionLost();
        },
      );

      _reconnectAttempt = 0;
      _setState(WsConnectionState.connected);
      debugPrint('[WS] _connect: connected OK');
    } catch (e) {
      debugPrint('[WS] _connect: exception: $e');
      _onConnectionLost();
    }
  }

  String _buildUrl(String? token) {
    final params = _lastParams!;
    final tokenParam = token?.trim() ?? '';

    if (params.isNewChat) {
      return "${ApiConfig.wsBaseUrl}/api/v1/ws/chat/new?token=$tokenParam";
    } else {
      final autoMsgParam = params.autoMsg != null
          ? "&auto_msg=${Uri.encodeComponent(params.autoMsg!)}"
          : '';
      return "${ApiConfig.wsBaseUrl}/api/v1/ws/chat/${params.tripId}?token=$tokenParam$autoMsgParam";
    }
  }

  void _onConnectionLost() {
    // If the user explicitly disconnected, don't auto-reconnect.
    if (_userDisconnected) return;

    _cleanup();
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    if (_reconnectAttempt >= _maxReconnectAttempts) {
      _setState(WsConnectionState.failed);
      return;
    }

    _setState(WsConnectionState.reconnecting);

    // Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped).
    final delayMs = _initialBackoff.inMilliseconds * (1 << _reconnectAttempt);
    final clampedMs = delayMs > _maxBackoff.inMilliseconds
        ? _maxBackoff.inMilliseconds
        : delayMs;
    final delay = Duration(milliseconds: clampedMs);

    _reconnectAttempt++;
    _reconnectTimer = Timer(delay, () async {
      if (_userDisconnected) return;
      await _connect();
    });
  }

  void _cancelReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
  }

  void _cleanup() {
    _wsSubscription?.cancel();
    _wsSubscription = null;
    _channel?.sink.close();
    _channel = null;
  }

  void _setState(WsConnectionState newState) {
    if (_state == newState) return;
    _state = newState;
    if (!_stateController.isClosed) {
      _stateController.add(newState);
    }
  }
}
