import 'dart:async';
import '../../../../core/errors/api_result.dart';
import '../../../../core/network/api_services.dart';
import '../datasource/chat_ws_service.dart';
import '../models/chat_history_message.dart';
import '../../../trips/data/models/trip_detail_model.dart';

class ChatRepository {
  final ChatWebSocketService _ws;
  final ApiServices _api;

  ChatRepository(this._ws, this._api);

  Stream<dynamic>? get messages => _ws.stream;

  /// Stream of WebSocket connection state changes (connected, reconnecting, etc.).
  Stream<WsConnectionState> get connectionStateStream => _ws.stateStream;

  /// Current WebSocket connection state.
  WsConnectionState get connectionState => _ws.state;

  Future<void> connect() async {
    await _ws.connectNewChat();
  }

  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    await _ws.connectToTrip(tripId, autoMsg: autoMsg);
  }

  /// Load chat history for a trip from the REST API.
  Future<ApiResult<List<ChatHistoryMessage>>> loadChatHistory(String tripId) async {
    try {
      final data = await _api.getChatHistory(tripId);
      return ApiResult.success(data);
    } catch (e) {
      return ApiResult.failure(e.toString());
    }
  }

  /// Load trip detail for hydrating itinerary cards in chat history.
  Future<TripDetailModel?> fetchTripDetail(String tripId) async {
    try {
      return await _api.getTripDetail(tripId);
    } catch (e) {
      print('[ChatRepository] fetchTripDetail failed: $e');
      return null;
    }
  }

  void sendMessage(String message) {
    _ws.sendMessage(message);
  }

  void disconnect() {
    _ws.disconnect();
  }
}