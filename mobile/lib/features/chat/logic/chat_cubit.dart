import 'dart:async';
import 'dart:convert';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/datasource/chat_ws_service.dart';
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
  StreamSubscription<WsConnectionState>? _wsStateSubscription;
  
  /// Tracks when reconnection started to enforce minimum banner display time.
  DateTime? _reconnectingSince;

  /// The last trip ID used for connection (null for new chats).
  String? _lastTripId;

  /// Called when a trip is created via chat so the parent can refresh trips.
  Function()? onTripCreated;

  ChatCubit(this._repo) : super(const ChatState.initial()) {
    // Listen to WebSocket connection state changes for reconnection feedback.
    _wsStateSubscription = _repo.connectionStateStream.listen(_onConnectionStateChanged);
  }

  /// Current pipeline steps exposed for the UI to read.
  List<PipelineStep> get pipelineSteps => List.unmodifiable(_pipelineSteps);

  Future<void> connect() async {
    _lastTripId = null;
    emit(const ChatState.loading());
    try {
      await _repo.connect();
      // Stream listener is set up by _onConnectionStateChanged(connected).
      emit(ChatState.connected(messages: _messages, isTyping: false));
    } catch (e) {
      print('[ChatCubit] connect() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect: $e"));
      }
    }
  }

  /// Reconnect using the last connection mode (new chat or trip chat).
  Future<void> reconnect() async {
    print('[ChatCubit] reconnect: lastTripId=$_lastTripId');
    if (_lastTripId != null) {
      return connectToTrip(_lastTripId!, autoMsg: null);
    }
    return connect();
  }

  /// Connect to a specific trip's chat session.
  /// Loads existing chat history first, then connects the WebSocket.
  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    _lastTripId = tripId;
    print('[ChatCubit] connectToTrip: tripId=$tripId');
    emit(const ChatState.loading());
    try {
      // 1. Load existing chat history from REST API
      final historyResult = await _repo.loadChatHistory(tripId);
      _messages.clear();
      historyResult.when(
        success: (history) {
          print('[ChatCubit] loaded ${history.length} history messages');
          for (final msg in history) {
            _messages.add(ChatMessage(
              text: msg.content,
              isUser: msg.isUser,
              isStreaming: false,
            ));
          }
        },
        failure: (e) {
          print('[ChatCubit] history load failed: $e');
        },
      );

      // 2. Connect WebSocket (without auto_msg to avoid regenerating the trip)
      await _repo.connectToTrip(tripId, autoMsg: null);
      // Stream listener is set up by _onConnectionStateChanged(connected).
      emit(ChatState.connected(messages: List.from(_messages), isTyping: false));
    } catch (e) {
      print('[ChatCubit] connectToTrip() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect to trip chat: $e"));
      }
    }
  }

  void _listenToStream() {
    // Always cancel previous subscription before re-subscribing.
    // On reconnection the WS service creates a new channel, so
    // _repo.messages now points to a *different* stream object.
    // Canceling the old sub is safe even if it was already cancelled.
    _subscription?.cancel();
    _subscription = _repo.messages?.listen(
      _handleEvent,
      onError: (error) {
        // Errors are handled via the connection state stream.
      },
      onDone: () {
        // Stream done triggers reconnection in the service layer.
        // The cubit reacts via _onConnectionStateChanged.
      },
    );
  }

  void _onConnectionStateChanged(WsConnectionState wsState) {
    if (isClosed) return;

    switch (wsState) {
      case WsConnectionState.connected:
        print('[ChatCubit] WS state → connected (hasSubscription=${_subscription != null})');
        // Reconnected — always re-subscribe to the new channel's stream.
        _listenToStream();
        
        // Enforce minimum 500ms display time for the banner to prevent flickering.
        final reconnectingSince = _reconnectingSince;
        _reconnectingSince = null;
        
        if (reconnectingSince != null) {
          final elapsed = DateTime.now().difference(reconnectingSince);
          final remaining = const Duration(milliseconds: 500) - elapsed;
          
          if (remaining.isNegative) {
            // Already shown for 500ms+, hide immediately.
            emit(ChatState.connected(
              messages: List.from(_messages),
              isTyping: false,
              isReconnecting: false,
            ));
          } else {
            // Keep banner visible for the remaining time.
            Future.delayed(remaining, () {
              // Only hide if no new reconnection started during the delay.
              if (!isClosed && _reconnectingSince == null) {
                emit(ChatState.connected(
                  messages: List.from(_messages),
                  isTyping: false,
                  isReconnecting: false,
                ));
              }
            });
          }
        } else {
          // Normal connected (not after reconnecting), hide immediately.
          emit(ChatState.connected(
            messages: List.from(_messages),
            isTyping: false,
            isReconnecting: false,
          ));
        }
        break;

      case WsConnectionState.reconnecting:
        _reconnectingSince = DateTime.now();
        emit(ChatState.connected(
          messages: List.from(_messages),
          isTyping: false,
          isReconnecting: true,
        ));
        break;

      case WsConnectionState.failed:
        print('[ChatCubit] WS state → failed');
        emit(ChatState.error("Connection lost. Please try again."));
        break;

      case WsConnectionState.connecting:
      case WsConnectionState.disconnected:
        break;
    }
  }

  void sendMessage(String message) {
    if (message.trim().isEmpty) return;

    _messages.add(ChatMessage(text: message, isUser: true));
    _resetPipeline();
    emit(ChatState.connected(messages: List.from(_messages), isTyping: true));
    _buffer = "";
    _repo.sendMessage(message);

    // ✅ Safety net: force-stop loading after 10 min if "done" never arrives
    // (pipeline can take 5+ min due to LLM calls and rate-limit retries)
    Future.delayed(const Duration(minutes: 10), () {
      final isStillTyping = state.maybeWhen(
        connected: (messages, isTyping, refreshToken, isReconnecting) => isTyping,
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
          // Flush any leftover streaming buffer.
          _buffer = "";

          // Notify parent (e.g. MainShell) to refresh the trips list.
          onTripCreated?.call();
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
          connected: (messages, isTyping, refreshToken, isReconnecting) {
            if (!isClosed) {
              emit(ChatState.connected(
                messages: List.from(messages),
                isTyping: isTyping,
                refreshToken: refreshToken + 1,
                isReconnecting: isReconnecting,
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
    _wsStateSubscription?.cancel();
    _repo.disconnect();
    return super.close();
  }
}