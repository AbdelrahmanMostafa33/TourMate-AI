import '../datasource/chat_ws_service.dart';

class ChatRepository {
  final ChatWebSocketService _ws;

  ChatRepository(this._ws);

  Stream<dynamic>? get messages => _ws.stream;

  Future<void> connect() async {
    await _ws.connectNewChat();
  }

  void sendMessage(String message) {
    _ws.sendMessage(message);
  }

  void disconnect() {
    _ws.disconnect();
  }
}