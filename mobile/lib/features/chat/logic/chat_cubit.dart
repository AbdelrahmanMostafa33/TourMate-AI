import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../data/datasource/chat_ws_service.dart';
import '../data/repository/chat_repository.dart';
import '../data/models/chat_message.dart';
import '../data/models/itinerary_data.dart';
import '../data/models/hotel_option.dart';
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
  ItineraryData? _pendingItinerary;
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

  /// Start a fresh chat: disconnect current WS, clear all state, connect anew.
  Future<void> resetForNewChat() async {
    _repo.disconnect();
    _messages.clear();
    _pipelineSteps.clear();
    _buffer = "";
    _pendingItinerary = null;
    _subscription?.cancel();
    _subscription = null;
    _lastTripId = null;
    await connect();
  }

  /// Switch to a trip chat: disconnect, clear state, load history, connect.
  Future<void> switchToTrip(String tripId) async {
    _repo.disconnect();
    _messages.clear();
    _pipelineSteps.clear();
    _buffer = "";
    _pendingItinerary = null;
    _subscription?.cancel();
    _subscription = null;
    _lastTripId = tripId;
    await connectToTrip(tripId, autoMsg: null);
  }

  Future<void> connect() async {
    _lastTripId = null;
    emit(const ChatState.loading());
    try {
      await _repo.connect();
      // Stream listener is set up by _onConnectionStateChanged(connected).
      emit(ChatState.connected(messages: _messages, isTyping: false));
    } catch (e) {
      debugPrint('[ChatCubit] connect() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect: $e"));
      }
    }
  }

  /// Connect as a new chat and immediately send the given auto-message.
  /// Used by the trip creation form to pre-fill the conversation with
  /// destination, dates, travelers, and interests.
  Future<void> connectWithAutoMessage(String autoMessage) async {
    _lastTripId = null;
    emit(const ChatState.loading());
    try {
      await _repo.connect();
      // Stream listener is set up by _onConnectionStateChanged(connected).
      // Send the auto message immediately — the WebSocket is already connected
      // and _repo.sendMessage writes directly to the channel sink.
      sendMessage(autoMessage);
      emit(ChatState.connected(messages: List.from(_messages), isTyping: true));
    } catch (e) {
      debugPrint('[ChatCubit] connectWithAutoMessage() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect: $e"));
      }
    }
  }

  /// Reconnect using the last connection mode (new chat or trip chat).
  Future<void> reconnect() async {
    debugPrint('[ChatCubit] reconnect: lastTripId=$_lastTripId');
    if (_lastTripId != null) {
      return connectToTrip(_lastTripId!, autoMsg: null);
    }
    return connect();
  }

  /// Connect to a specific trip's chat session.
  /// Loads existing chat history first, then connects the WebSocket.
  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    _lastTripId = tripId;
    debugPrint('[ChatCubit] connectToTrip: tripId=$tripId');
    emit(const ChatState.loading());
    try {
      // 1. Load existing chat history from REST API
      final historyResult = await _repo.loadChatHistory(tripId);
      _messages.clear();        historyResult.when(
        success: (history) {
          debugPrint('[ChatCubit] loaded ${history.length} history messages');
          for (final msg in history) {
            Uint8List? decodedImage;
            if (msg.imageData != null && msg.imageData!.isNotEmpty) {
              try {
                decodedImage = base64Decode(msg.imageData!);
              } catch (e) {
                debugPrint('[ChatCubit] Failed to decode image_data: $e');
              }
            }
            _messages.add(ChatMessage(
              text: msg.content,
              isUser: msg.isUser,
              isStreaming: false,
              imageBytes: decodedImage,
            ));
          }
        },
        failure: (e) {
          debugPrint('[ChatCubit] history load failed: $e');
        },
      );

      // 2. Hydrate itinerary cards from persisted trip data (history is text-only).
      final tripDetail = await _repo.fetchTripDetail(tripId);
      if (tripDetail != null) {
        final itinerary = ItineraryData.fromTripDetail(tripDetail);
        if (itinerary != null) {
          _attachItineraryToHistory(itinerary);
        }
      }

      // 3. Connect WebSocket (without auto_msg to avoid regenerating the trip)
      await _repo.connectToTrip(tripId, autoMsg: null);
      // Stream listener is set up by _onConnectionStateChanged(connected).
      final hasItineraryCard = _messages.any((m) => m.itinerary != null);
      emit(ChatState.connected(
        messages: List.from(_messages),
        isTyping: false,
        refreshToken: hasItineraryCard ? 1 : 0,
      ));
    } catch (e) {
      debugPrint('[ChatCubit] connectToTrip() failed: $e');
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
        debugPrint('[ChatCubit] WS state → connected (hasSubscription=${_subscription != null})');
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
        debugPrint('[ChatCubit] WS state → failed');
        emit(ChatState.error("Connection lost. Please try again."));
        break;

      case WsConnectionState.connecting:
      case WsConnectionState.disconnected:
        break;
    }
  }

  void sendMessage(String message, {Uint8List? imageBytes}) {
    if (message.trim().isEmpty && imageBytes == null) return;

    _messages.add(ChatMessage(text: message, isUser: true, imageBytes: imageBytes));
    _resetPipeline();
    emit(ChatState.connected(messages: List.from(_messages), isTyping: true));
    _buffer = "";
    _repo.sendMessage(message, imageBytes: imageBytes);

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

  void _emitConnected({required bool isTyping, bool bumpRefresh = false}) {
    if (isClosed) return;

    final (refreshToken, isReconnecting) = state.maybeWhen(
      connected: (_, _, token, reconnecting) =>
          (bumpRefresh ? token + 1 : token, reconnecting),
      orElse: () => (bumpRefresh ? 1 : 0, false),
    );

    emit(ChatState.connected(
      messages: List.from(_messages),
      isTyping: isTyping,
      refreshToken: refreshToken,
      isReconnecting: isReconnecting,
    ));
  }

  Map<String, dynamic> _decodeEvent(dynamic event) {
    if (event is String) {
      return Map<String, dynamic>.from(jsonDecode(event) as Map);
    }
    if (event is Map) {
      return Map<String, dynamic>.from(event);
    }
    throw FormatException('Unsupported WS payload: ${event.runtimeType}');
  }

  ItineraryData? _tryParseItinerary(dynamic raw) {
    if (raw is! Map) return null;
    try {
      return ItineraryData.fromJson(Map<String, dynamic>.from(raw));
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse itinerary JSON: $e');
      return null;
    }
  }

  void _attachItinerary(ItineraryData itineraryData) {
    if (_messages.isNotEmpty && !_messages.last.isUser) {
      _messages[_messages.length - 1] = _messages.last.copyWith(
        itinerary: itineraryData,
        text: '',
        isStreaming: false,
      );
    } else {
      _messages.add(
        ChatMessage(
          text: '',
          isUser: false,
          isStreaming: false,
          itinerary: itineraryData,
        ),
      );
    }
    _pendingItinerary = null;
  }

  void _attachItineraryToHistory(ItineraryData itineraryData) {
    for (var i = _messages.length - 1; i >= 0; i--) {
      if (_messages[i].isUser) continue;
      if (_looksLikeItineraryMessage(_messages[i].text)) {
        _messages[i] = _messages[i].copyWith(
          itinerary: itineraryData,
          text: '',
        );
        return;
      }
    }

    for (var i = _messages.length - 1; i >= 0; i--) {
      if (!_messages[i].isUser) {
        _messages[i] = _messages[i].copyWith(
          itinerary: itineraryData,
          text: '',
        );
        return;
      }
    }
  }

  bool _looksLikeItineraryMessage(String text) {
    final normalized = text.toLowerCase();
    return normalized.contains('day 1') ||
        normalized.contains('itinerary') ||
        text.contains('🗓') ||
        text.contains('✨');
  }

  void _applyPendingItineraryToLastAssistant() {
    if (_pendingItinerary == null) return;
    if (_messages.isEmpty || _messages.last.isUser) return;

    _messages[_messages.length - 1] = _messages.last.copyWith(
      itinerary: _pendingItinerary,
      text: '',
    );
    _pendingItinerary = null;
  }

  Future<void> _handleEvent(dynamic event) async {
    final Map<String, dynamic> data;
    try {
      data = _decodeEvent(event);
    } catch (e) {
      debugPrint('[ChatCubit] Failed to decode WS event: $e');
      return;
    }

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

          // Bump refreshToken so freezed sees a different state and
          // BlocBuilder rebuilds — _messages hasn't changed (no new
          // ChatMessage), so DeepCollectionEquality would otherwise
          // consider the new state equal to the previous one and skip
          // the UI update.
          _emitConnected(isTyping: true, bumpRefresh: true);
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
          final last = _messages.last;
          if (last.itinerary != null) break;

          _messages[_messages.length - 1] = last.copyWith(
            text: _buffer,
            isStreaming: true,
          );
        } else {
          _messages.add(
            ChatMessage(text: _buffer, isUser: false, isStreaming: true),
          );
        }

        _applyPendingItineraryToLastAssistant();
        _emitConnected(isTyping: true);
        break;

      case "done":
        if (_pendingItinerary != null) {
          _attachItinerary(_pendingItinerary!);
        }

        if (_messages.isNotEmpty && !_messages.last.isUser) {
          final last = _messages.last;
          _messages[_messages.length - 1] = last.copyWith(
            text: last.itinerary != null ? '' : _buffer,
            isStreaming: false,
          );
        }

        _emitConnected(isTyping: false, bumpRefresh: true);
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


      case "result":
        final resultPayload = data["data"];
        if (resultPayload is Map) {
          final itinerary = _tryParseItinerary(resultPayload["itinerary"]);
          if (itinerary != null) {
            _attachItinerary(itinerary);
            final currentIsTyping = state.maybeWhen(
              connected: (_, isTyping, _, _) => isTyping,
              orElse: () => false,
            );
            _emitConnected(isTyping: currentIsTyping, bumpRefresh: true);
          }
        }
        break;

      case "itinerary_data":
        final itinerary = _tryParseItinerary(data["data"]);
        if (itinerary != null) {
          _attachItinerary(itinerary);
          final currentIsTyping = state.maybeWhen(
            connected: (_, isTyping, _, _) => isTyping,
            orElse: () => false,
          );
          _emitConnected(isTyping: currentIsTyping, bumpRefresh: true);
        }
        break;

      case "hotel_options":
        final rawPayload = data["data"] as Map<String, dynamic>?;
        if (rawPayload != null) {
          final payload = HotelOptionsPayload.fromJson(rawPayload);
          if (payload.options.isNotEmpty) {
            _messages.add(ChatMessage(
              text: payload.message ?? '',
              isUser: false,
              isStreaming: false,
              hotelOptions: payload,
            ));
            _emitConnected(isTyping: false, bumpRefresh: true);
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