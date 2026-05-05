import 'package:freezed_annotation/freezed_annotation.dart';
import '../data/models/chat_message.dart';

part 'chat_state.freezed.dart';

@freezed
class ChatState with _$ChatState {
  const factory ChatState.initial() = _Initial;

  const factory ChatState.loading() = _Loading;

  const factory ChatState.connected({
    required List<ChatMessage> messages,
    required bool isTyping,
  }) = _Connected;

  const factory ChatState.error(String message) = _Error;
}