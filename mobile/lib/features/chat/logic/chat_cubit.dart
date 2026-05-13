import 'dart:convert';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../data/repository/chat_repository.dart';
import '../data/models/chat_message.dart';
import 'chat_state.dart';

class ChatCubit extends Cubit<ChatState> {
  final ChatRepository _repo;

  List<ChatMessage> _messages = [];
  String _buffer = "";

  ChatCubit(this._repo) : super(const ChatState.initial());

  Future<void> connect() async {
    emit(const ChatState.loading());

    await _repo.connect();

    _repo.messages?.listen(
      _handleEvent,
      onError: (error) {
      emit(ChatState.error("Connection error: $error"));
    },
      onDone: () {
        // WebSocket closed by server
        emit(ChatState.error("Connection closed. Please try again."));
      },
    );

    emit(ChatState.connected(messages: _messages, isTyping: false));
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

  void _handleEvent(dynamic event) {
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
      // later: navigate to trips screen
        break;

      case "actions":
      // later: show itinerary UI
        break;

      case "error":
        emit(ChatState.error(data["data"]));
        break;
    }
  }

  @override
  Future<void> close() {
    _repo.disconnect();
    return super.close();
  }
}