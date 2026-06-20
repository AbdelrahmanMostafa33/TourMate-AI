import '../datasource/chat_ws_service.dart';

class ChatRepository {
  final ChatWebSocketService _ws;

  ChatRepository(this._ws);

  Stream<dynamic>? get messages => _ws.stream;

  Future<void> connect() async {
    await _ws.connectNewChat();
  }

  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    await _ws.connectToTrip(tripId, autoMsg: autoMsg);
  }

  void sendMessage(String message) {
    _ws.sendMessage(message);
  }

  void disconnect() {
    _ws.disconnect();
  }
}