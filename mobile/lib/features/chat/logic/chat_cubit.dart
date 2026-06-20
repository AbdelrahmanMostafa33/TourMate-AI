import 'dart:async';
import 'dart:convert';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../data/repository/chat_repository.dart';
import '../data/models/chat_message.dart';
import 'chat_state.dart';

class ChatCubit extends Cubit<ChatState> {
  final ChatRepository _repo;

  final List<ChatMessage> _messages = [];
  String _buffer = "";
  StreamSubscription<dynamic>? _subscription;

  ChatCubit(this._repo) : super(const ChatState.initial());

  Future<void> connect() async {
    emit(const ChatState.loading());
    await _repo.connect();
    _listenToStream();
    emit(ChatState.connected(messages: _messages, isTyping: false));
  }

  void _listenToStream() {
    _subscription?.cancel();
    _subscription = _repo.messages?.listen(
      _handleEvent,
      onError: (error) {
        if (!isClosed) {
          emit(ChatState.error("Connection error: $error"));
        }
      },
      onDone: () {
        if (!isClosed) {
          emit(ChatState.error("Connection closed. Please try again."));
        }
      },
    );
  }

  void sendMessage(String message) {
    if (message.trim().isEmpty) return;

    _messages.add(ChatMessage(text: message, isUser: true));
    emit(ChatState.connected(messages: List.from(_messages), isTyping: true));
    _buffer = "";
    _repo.sendMessage(message);

    // ✅ Safety net: force-stop loading after 30s if "done" never arrives
    Future.delayed(const Duration(seconds: 30), () {
      final isStillTyping = state.maybeWhen(
        connected: (messages, isTyping) => isTyping,
        orElse: () => false,
      );

      if (isStillTyping) {
        emit(ChatState.connected(
          messages: List.from(_messages),
          isTyping: false,
        ));
      }
    });
  }

  Future<void> _handleEvent(dynamic event) async {
    final data = jsonDecode(event);

    switch (data["type"]) {

      case "typing":
        emit(ChatState.connected(
          messages: _messages,
          isTyping: true,
        ));
        break;

      case "token":
        _buffer += data["data"];

        if (_messages.isNotEmpty && !_messages.last.isUser) {
          _messages[_messages.length - 1] =
              ChatMessage(text: _buffer, isUser: false, isStreaming: true);
        } else {
          _messages.add(
            ChatMessage(text: _buffer, isUser: false, isStreaming: true),
          );
        }

        emit(ChatState.connected(
          messages: List.from(_messages),
          isTyping: true,
        ));
        break;

      case "done":
        if (_messages.isNotEmpty && !_messages.last.isUser) {
          _messages[_messages.length - 1] =
              ChatMessage(text: _buffer, isUser: false, isStreaming: false);
        }

        emit(ChatState.connected(
          messages: List.from(_messages),
          isTyping: false,
        ));

        _buffer = "";
        break;

      case "trip_created":
        final tripId = data["trip_id"] as String?;
        if (tripId != null) {
          _repo.disconnect();
          _buffer = "";
          try {
            await _repo.connectToTrip(tripId);
            _listenToStream();
          } catch (e) {
            if (!isClosed) {
              emit(ChatState.error("Failed to reconnect: $e"));
            }
          }
        }
        break;

      case "actions":
        // Actions from AI (ADD_ACTIVITY, UPDATE_ACTIVITY, etc.)
        // Could be used to update a local itinerary state
        break;

      case "itinerary_updated":
        // Itinerary was modified by the backend
        break;

      case "error":
        if (!isClosed) {
          emit(ChatState.error(data["data"]));
        }
        break;
    }
  }

  @override
  Future<void> close() {
    _subscription?.cancel();
    _repo.disconnect();
    return super.close();
  }
}