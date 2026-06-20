import 'dart:convert';
import 'package:web_socket_channel/io.dart';
import '../../../auth/data/datasource/firebase_auth_service.dart';

class ChatWebSocketService {
  IOWebSocketChannel? _channel;

  final FirebaseAuthService _authService;

  ChatWebSocketService(this._authService);

  Stream<dynamic>? get stream => _channel?.stream;

  Future<void> connectNewChat() async {
    final token = await _authService.getToken();

    final url = "ws://10.0.2.2:8000/api/v1/ws/chat/new?token=${token?.trim()}";

    _channel = IOWebSocketChannel.connect(url);
  }

  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    final token = await _authService.getToken();
    final autoMsgParam = autoMsg != null ? "&auto_msg=${Uri.encodeComponent(autoMsg)}" : '';

    final url = "ws://10.0.2.2:8000/api/v1/ws/chat/$tripId?token=${token?.trim()}$autoMsgParam";

    _channel = IOWebSocketChannel.connect(url);
  }

  void sendMessage(String message) {
    _channel?.sink.add(jsonEncode({
      "message": message,
    }));
  }

  void disconnect() {
    _channel?.sink.close();
  }
}