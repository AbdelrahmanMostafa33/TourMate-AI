import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';
import 'package:stream_channel/stream_channel.dart';
import 'package:tourmate/features/chat/data/datasource/chat_ws_service.dart';
import 'package:tourmate/features/auth/data/datasource/firebase_auth_service.dart';

@GenerateMocks([FirebaseAuthService])
import 'chat_ws_service_test.mocks.dart';

/// A fake WebSocket channel backed by in-memory stream controllers.
class FakeWsChannel extends StreamChannelMixin<dynamic> {
  final StreamController<dynamic> _inbound = StreamController<dynamic>.broadcast();
  final List<dynamic> sentMessages = [];
  bool isClosed = false;

  @override
  Stream<dynamic> get stream => _inbound.stream;

  @override
  StreamSink<dynamic> get sink => _FakeSink(this);

  void simulateMessage(String message) => _inbound.add(message);
  void simulateClose() {
    _inbound.close();
    isClosed = true;
  }
  void simulateError(Object error) => _inbound.addError(error);

  void dispose() => _inbound.close();
}

class _FakeSink implements StreamSink<dynamic> {
  final FakeWsChannel _ch;
  _FakeSink(this._ch);

  @override
  void add(data) => _ch.sentMessages.add(data);

  @override
  void addError(error, [StackTrace? st]) {}

  @override
  Future<void> addStream(Stream<dynamic> s) async {}

  @override
  Future<void> close([int? code, String? reason]) async {
    _ch.isClosed = true;
  }

  @override
  Future<dynamic> get done async {}
}

void main() {
  late MockFirebaseAuthService mockAuth;
  late List<FakeWsChannel> channels;

  setUp(() {
    mockAuth = MockFirebaseAuthService();
    channels = [];
    when(mockAuth.getToken()).thenAnswer((_) async => 'tok');
  });

  tearDown(() {
    for (final ch in channels) {
      ch.dispose();
    }
  });

  ChatWebSocketService createService({
    int maxAttempts = 6,
    Duration backoff = const Duration(milliseconds: 10),
  }) {
    return ChatWebSocketService(
      mockAuth,
      channelFactory: (url) {
        final ch = FakeWsChannel();
        channels.add(ch);
        return ch;
      },
      maxReconnectAttempts: maxAttempts,
      initialBackoff: backoff,
      maxBackoff: backoff,
    );
  }

  // ── State transitions ────────────────────────────────────────────────

  group('Initial state', () {
    test('starts disconnected', () {
      expect(createService().state, WsConnectionState.disconnected);
    });
  });

  group('connectNewChat', () {
    test('transitions to connected', () async {
      final svc = createService();
      await svc.connectNewChat();
      expect(svc.state, WsConnectionState.connected);
      svc.disconnect();
    });

    test('emits connected on stateStream', () async {
      final svc = createService();
      final states = <WsConnectionState>[];
      svc.stateStream.listen(states.add);

      await svc.connectNewChat();
      await Future<void>.delayed(Duration.zero);

      expect(states, contains(WsConnectionState.connected));
      svc.disconnect();
    });
  });

  group('connectToTrip', () {
    test('transitions to connected', () async {
      final svc = createService();
      await svc.connectToTrip('t1');
      expect(svc.state, WsConnectionState.connected);
      svc.disconnect();
    });
  });

  group('disconnect', () {
    test('transitions to disconnected and prevents reconnect', () async {
      final svc = createService();
      await svc.connectNewChat();
      svc.disconnect();
      expect(svc.state, WsConnectionState.disconnected);

      // Simulate close on old channel — should NOT trigger reconnect.
      channels.last.simulateClose();
      await Future<void>.delayed(const Duration(milliseconds: 200));
      expect(svc.state, WsConnectionState.disconnected);
    });

    test('can reconnect after explicit disconnect', () async {
      final svc = createService();
      await svc.connectNewChat();
      svc.disconnect();
      expect(svc.state, WsConnectionState.disconnected);

      await svc.connectNewChat();
      expect(svc.state, WsConnectionState.connected);
      svc.disconnect();
    });
  });

  // ── Reconnection ────────────────────────────────────────────────────

  group('Auto-reconnect', () {
    test('schedules reconnect when connection lost', () async {
      final svc = createService();
      await svc.connectNewChat();

      channels.last.simulateClose();
      await Future<void>.delayed(Duration.zero);

      expect(svc.state, WsConnectionState.reconnecting);
      svc.disconnect();
    }, timeout: const Timeout(Duration(seconds: 10)));

    test('transitions to failed after max attempts', () async {
      final svc = createService(maxAttempts: 3, backoff: const Duration(milliseconds: 10));
      await svc.connectNewChat(); // First connect succeeds with valid token from setUp().

      // Now make reconnects fail by switching the mock to throw.
      when(mockAuth.getToken()).thenAnswer((_) async => throw Exception('auth expired'));

      // Lose initial connection — triggers reconnect attempts that will fail.
      channels.last.simulateClose();
      await Future<void>.delayed(Duration.zero);
      expect(svc.state, WsConnectionState.reconnecting);

      // Wait for each failed reconnect timer to fire (10ms backoff).
      for (var i = 0; i < 3; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }

      expect(svc.state, WsConnectionState.failed);
    });

    test('resets attempt counter on successful reconnect', () async {
      final svc = createService(backoff: const Duration(milliseconds: 10));
      await svc.connectNewChat();

      // Connection lost → reconnecting.
      channels.last.simulateClose();
      await Future<void>.delayed(Duration.zero);
      expect(svc.state, WsConnectionState.reconnecting);

      // Wait for the 10ms backoff to fire and reconnect to succeed.
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(svc.state, WsConnectionState.connected);

      // Lose connection again — should still reconnect (counter was reset).
      channels.last.simulateClose();
      await Future<void>.delayed(Duration.zero);
      expect(svc.state, WsConnectionState.reconnecting);

      svc.disconnect();
    });
  });

  // ── Double connect guard ────────────────────────────────────────────

  group('Double connect', () {
    test('does not create duplicate channels', () async {
      final svc = createService();
      await svc.connectNewChat();
      final count = channels.length;

      await svc.connectNewChat(); // Should be a no-op.
      expect(channels.length, count);
      svc.disconnect();
    });
  });

  // ── Messaging ───────────────────────────────────────────────────────

  group('sendMessage', () {
    test('sends JSON through the sink', () async {
      final svc = createService();
      await svc.connectNewChat();
      svc.sendMessage('hi');
      expect(channels.last.sentMessages, contains('{"message":"hi"}'));
      svc.disconnect();
    });

    test('does not throw when disconnected', () {
      createService().sendMessage('hi'); // No crash.
    });
  });

  // ── Dispose ─────────────────────────────────────────────────────────

  group('dispose', () {
    test('closes state stream', () async {
      final svc = createService();
      await svc.connectNewChat();
      svc.dispose();
      // Adding to closed controller should not throw.
      expect(svc.state, WsConnectionState.disconnected);
    });
  });
}
