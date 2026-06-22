import 'dart:async';
import 'dart:convert';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../data/repository/chat_repository.dart';
import '../data/models/chat_message.dart';
import '../data/models/itinerary_data.dart';
import 'chat_state.dart';

/// A single step in the AI pipeline progress (visible to the UI).
class PipelineStep {
  final String agent;
  final String status; // "running", "done", "error"
  final String message;

  const PipelineStep({
    required this.agent,
    required this.status,
    this.message = '',
  });
}

class ChatCubit extends Cubit<ChatState> {
  final ChatRepository _repo;

  final List<ChatMessage> _messages = [];
  final List<PipelineStep> _pipelineSteps = [];
  String _buffer = "";
  StreamSubscription<dynamic>? _subscription;

  ChatCubit(this._repo) : super(const ChatState.initial());

  /// Current pipeline steps exposed for the UI to read.
  List<PipelineStep> get pipelineSteps => List.unmodifiable(_pipelineSteps);

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
    _resetPipeline();
    emit(ChatState.connected(messages: List.from(_messages), isTyping: true));
    _buffer = "";
    _repo.sendMessage(message);

    // ✅ Safety net: force-stop loading after 30s if "done" never arrives
    Future.delayed(const Duration(seconds: 30), () {
      final isStillTyping = state.maybeWhen(
        connected: (messages, isTyping, refreshToken) => isTyping,
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

  /// Reset pipeline steps (called on new message send).
  void _resetPipeline() {
    _pipelineSteps.clear();
  }

  Future<void> _handleEvent(dynamic event) async {
    final data = jsonDecode(event) as Map<String, dynamic>;

    switch (data["type"]) {

      case "progress":
        final progressData = data["data"] as Map<String, dynamic>?;
        if (progressData != null) {
          final agent = progressData["agent"] as String? ?? '';
          final status = progressData["status"] as String? ?? 'running';
          final message = progressData["message"] as String? ?? '';

          if (status == 'running') {
            // Remove any previous entry for this agent, then add new running entry
            _pipelineSteps.removeWhere((s) => s.agent == agent);
            _pipelineSteps.add(PipelineStep(
              agent: agent,
              status: 'running',
              message: message,
            ));
          } else {
            // Update existing entry or add completed one
            _pipelineSteps.removeWhere((s) => s.agent == agent);
            _pipelineSteps.add(PipelineStep(
              agent: agent,
              status: status == 'done' ? 'done' : 'error',
              message: message,
            ));
          }

          emit(ChatState.connected(
            messages: List.from(_messages),
            isTyping: true,
          ));
        }
        break;

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
          // ✅ Keep the SAME WebSocket open — the backend already remapped
          //    this connection from "new_userid" to the trip_id internally.
          //    Disconnecting and reconnecting would cause the backend's
          //    websocket_new_chat handler to exit (WebSocketDisconnect)
          //    and the new connection to /ws/chat/{trip_id} would have
          //    no auto_msg → both sides waiting forever → deadlock.
        }
        break;

      case "actions":
        final actionsList = data["data"] as List<dynamic>?;
        if (actionsList != null) {
          for (final action in actionsList) {
            if (action is Map && action["type"] == "CREATE_TRIP") {
              final rawData = action["data"];
              if (rawData is Map<String, dynamic>) {
                final itineraryData = ItineraryData.fromJson(rawData);
                // Update the last assistant message with structured itinerary
                if (_messages.isNotEmpty && !_messages.last.isUser) {
                  _messages[_messages.length - 1] = _messages.last.copyWith(
                    itinerary: itineraryData,
                  );
                  if (!isClosed) {
                    emit(ChatState.connected(
                      messages: List.from(_messages),
                      isTyping: false,
                    ));
                  }
                }
              }
            }
          }
        }
        break;

      case "itinerary_data":
        // Full structured itinerary JSON arrived from the backend.
        // Parse it and attach to the last assistant message.
        final rawItinerary = data["data"];
        if (rawItinerary is Map<String, dynamic>) {
          try {
            final itineraryData = ItineraryData.fromJson(rawItinerary);
            if (_messages.isNotEmpty && !_messages.last.isUser) {
              _messages[_messages.length - 1] = _messages.last.copyWith(
                itinerary: itineraryData,
              );
              if (!isClosed) {
                emit(ChatState.connected(
                  messages: List.from(_messages),
                  isTyping: false,
                ));
              }
            }
          } catch (e) {
            // Silently ignore malformed itinerary data
          }
        }
        break;

      case "itinerary_updated":
        // The card already has the latest data from the 'itinerary_data'
        // event that preceded this.  Force a UI refresh by bumping the
        // refreshToken so BlocBuilder sees a different state object.
        state.maybeWhen(
          connected: (messages, isTyping, refreshToken) {
            if (!isClosed) {
              emit(ChatState.connected(
                messages: List.from(messages),
                isTyping: isTyping,
                refreshToken: refreshToken + 1,
              ));
            }
          },
          orElse: () {},
        );
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