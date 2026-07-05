import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../../bookings/data/cache/booking_draft_cache.dart';
import '../data/datasource/chat_ws_service.dart';
import '../data/models/booking_data.dart';
import '../data/models/chat_history_message.dart';
import '../data/models/flight_options_payload.dart';
import '../data/models/hotel_option.dart';
import '../data/models/itinerary_data.dart';
import '../data/models/photo_analysis_data.dart';
import '../data/repository/chat_repository.dart';
import 'chat_event.dart' as events;
import '../data/models/chat_message.dart' as cm;
import 'chat_segment.dart';
import 'chat_state.dart';
import 'message_assembler.dart';
import 'stream_parser.dart';

/// A single step in the AI pipeline progress (visible to the UI).
class PipelineStep {
  final String agent;
  final String status;
  final String message;

  const PipelineStep({
    required this.agent,
    required this.status,
    this.message = '',
  });
}

class ChatCubit extends Cubit<ChatState> {
  final ChatRepository _repo;

  // ── Message state ───────────────────────────────────────────────────
  final List<cm.ChatMessage> _messages = [];
  final List<PipelineStep> _pipelineSteps = [];

  /// Assembles one assistant response from streamed events.
  late final MessageAssembler _assembler;

  /// Whether the booking card has been shown.
  bool _inBookingPhase = false;

  StreamSubscription<dynamic>? _subscription;
  StreamSubscription<WsConnectionState>? _wsStateSubscription;

  /// Tracks when reconnection started to enforce minimum banner display time.
  DateTime? _reconnectingSince;

  /// The last trip ID used for connection (null for new chats).
  String? _lastTripId;

  /// Called when a trip is created via chat so the parent can refresh trips.
  Function()? onTripCreated;

  /// Called when the trip is approved.
  Function()? onTripApproved;

  /// The trip_id from the most recent booking_data event, used for navigation.
  String? _bookingTripId;

  /// The flight_booking payload (with raw_offer) from the backend.
  Map<String, dynamic>? _flightBookingData;

  /// The hotel info from the booking_data payload.
  Map<String, dynamic>? _selectedHotelInfo;

  /// Tracks the signature of the most recently rendered itinerary card.
  String? _renderedItinerarySignature;

  ChatCubit(this._repo)
      : _assembler = MessageAssembler(),
        super(const ChatState.initial()) {
    _wsStateSubscription =
        _repo.connectionStateStream.listen(_onConnectionStateChanged);
  }

  /// Current pipeline steps exposed for the UI to read.
  List<PipelineStep> get pipelineSteps => List.unmodifiable(_pipelineSteps);

  /// The trip_id from the most recent booking_data event, for UI navigation.
  String? get bookingTripId => _bookingTripId;

  /// The flight_booking data (with raw_offer) stored from the last select_flight event.
  Map<String, dynamic>? get flightBookingData => _flightBookingData;

  /// The hotel info from the last booking_data event.
  Map<String, dynamic>? get selectedHotelInfo => _selectedHotelInfo;

  // ── Lifecycle ───────────────────────────────────────────────────────

  Future<void> resetForNewChat() async {
    _repo.disconnect();
    if (_bookingTripId != null) {
      BookingDraftCache.clearDraft(_bookingTripId!);
    }
    _resetState();
    await connect();
  }

  Future<void> switchToTrip(String tripId) async {
    _repo.disconnect();
    _resetState();
    _lastTripId = tripId;
    await connectToTrip(tripId, autoMsg: null);
  }

  Future<void> connect() async {
    _lastTripId = null;
    emit(const ChatState.loading());
    try {
      await _repo.connect();
      emit(ChatState.connected(messages: _messages, isTyping: false));
    } catch (e) {
      debugPrint('[ChatCubit] connect() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect: $e"));
      }
    }
  }

  Future<void> connectWithAutoMessage(String autoMessage) async {
    _lastTripId = null;
    emit(const ChatState.loading());
    try {
      await _repo.connect();
      sendMessage(autoMessage);
      emit(ChatState.connected(
          messages: List.from(_messages), isTyping: true));
    } catch (e) {
      debugPrint('[ChatCubit] connectWithAutoMessage() failed: $e');
      if (!isClosed) {
        emit(ChatState.error("Failed to connect: $e"));
      }
    }
  }

  Future<void> reconnect() async {
    debugPrint('[ChatCubit] reconnect: lastTripId=$_lastTripId');
    if (_lastTripId != null) {
      return connectToTrip(_lastTripId!, autoMsg: null);
    }
    return connect();
  }

  Future<void> connectToTrip(String tripId, {String? autoMsg}) async {
    _lastTripId = tripId;
    debugPrint('[ChatCubit] connectToTrip: tripId=$tripId');
    emit(const ChatState.loading());
    try {
      // 1. Load existing chat history from REST API.
      final historyResult = await _repo.loadChatHistory(tripId);
      _messages.clear();
      historyResult.when(
        success: (history) {
          debugPrint('[ChatCubit] loaded ${history.length} history messages');
          for (final msg in history) {
            _messages.add(_historyToChatMessage(msg, tripId));
          }
        },
        failure: (e) {
          debugPrint('[ChatCubit] history load failed: $e');
        },
      );

      // 2. Restore cached booking draft
      final draft = await BookingDraftCache.loadDraft(tripId);
      if (draft != null) {
        if (draft['flight_booking'] is Map<String, dynamic>) {
          _flightBookingData =
              draft['flight_booking'] as Map<String, dynamic>;
        }
        if (draft['hotel_info'] is Map<String, dynamic>) {
          _selectedHotelInfo = draft['hotel_info'] as Map<String, dynamic>;
        }
      }

      _bookingTripId = tripId;

      // 3. Connect WebSocket
      await _repo.connectToTrip(tripId, autoMsg: null);
      final hasItineraryCard = _messages.any((m) => m.hasCard);
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

  @override
  Future<void> close() {
    _subscription?.cancel();
    _wsStateSubscription?.cancel();
    _repo.disconnect();
    return super.close();
  }

  // ── Message sending ─────────────────────────────────────────────────

  void sendMessage(String message, {Uint8List? imageBytes}) {
    if (message.trim().isEmpty && imageBytes == null) return;

    // Booking phase redirect
    if (_inBookingPhase && message.trim().isNotEmpty) {
      debugPrint(
          '[ChatCubit] Booking phase active — redirecting "${message.trim()}" → "approve"');
      message = 'approve';
      _inBookingPhase = false;
    }

    _messages.add(cm.ChatMessage.text(
      message,
      isUser: true,
      imageBytes: imageBytes,
    ));
    _resetPipeline();
    emit(ChatState.connected(
        messages: List.from(_messages), isTyping: true));
    _assembler.reset();
    _repo.sendMessage(message, imageBytes: imageBytes);

    // Safety net: force-stop loading after 10 min
    Future.delayed(const Duration(minutes: 10), () {
      final isStillTyping = state.maybeWhen(
        connected: (_, isTyping, _, _) => isTyping,
        orElse: () => false,
      );
      if (isStillTyping) {
        emit(ChatState.connected(
            messages: List.from(_messages), isTyping: false));
      }
    });
  }

  void leaveBookingPhase() {
    _inBookingPhase = false;
    debugPrint('[ChatCubit] Exited booking phase — user can type freely');
  }

  void markBookingConfirmed() {
    for (var i = 0; i < _messages.length; i++) {
      final segments = _messages[i].segments;
      for (var j = 0; j < segments.length; j++) {
        final seg = segments[j];
        if (seg is CardSegment && seg.cardType == 'booking') {
          final updatedSeg = CardSegment(
            cardType: 'booking',
            rawData: {...seg.rawData, 'is_confirmed': true},
          );
          final newSegments = List<ChatSegment>.from(segments);
          newSegments[j] = updatedSeg;
          _messages[i] = _messages[i].copyWith(segments: newSegments);
          _emitConnected(isTyping: false, bumpRefresh: true);
          if (_bookingTripId != null) {
            BookingDraftCache.clearDraft(_bookingTripId!);
          }
          return;
        }
      }
    }
  }

  void setFlightBookingData(Map<String, dynamic> rawOffer) {
    _flightBookingData = {'raw_offer': rawOffer};
    debugPrint(
        '[ChatCubit] ✅ Stored flight_booking data from flight selection');
    if (_bookingTripId != null) {
      BookingDraftCache.saveDraft(
        tripId: _bookingTripId!,
        flightBookingData: _flightBookingData,
      );
    }
  }

  // ── Internal ────────────────────────────────────────────────────────

  void _resetState() {
    _messages.clear();
    _pipelineSteps.clear();
    _assembler.reset();
    _inBookingPhase = false;
    _bookingTripId = null;
    _flightBookingData = null;
    _selectedHotelInfo = null;
    _renderedItinerarySignature = null;
    _reconnectingSince = null;
    onTripApproved = null;
    onTripCreated = null;
    _subscription?.cancel();
    _subscription = null;
    _lastTripId = null;
  }

  void _resetPipeline() {
    _pipelineSteps.clear();
  }

  void _listenToStream() {
    _subscription?.cancel();
    _subscription = _repo.messages?.listen(
      _handleEvent,
      onError: (_) {},
      onDone: () {},
    );
  }

  void _onConnectionStateChanged(WsConnectionState wsState) {
    if (isClosed) return;

    switch (wsState) {
      case WsConnectionState.connected:
        debugPrint('[ChatCubit] WS state → connected');
        _listenToStream();
        final reconnectingSince = _reconnectingSince;
        _reconnectingSince = null;

        if (reconnectingSince != null) {
          final elapsed = DateTime.now().difference(reconnectingSince);
          final remaining = const Duration(milliseconds: 500) - elapsed;
          if (remaining.isNegative) {
            emit(ChatState.connected(
              messages: List.from(_messages),
              isTyping: false,
              isReconnecting: false,
            ));
          } else {
            Future.delayed(remaining, () {
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

  // ── Event handling ──────────────────────────────────────────────────

  Future<void> _handleEvent(dynamic event) async {
    final Map<String, dynamic> raw;
    try {
      raw = _decodeEvent(event);
    } catch (e) {
      debugPrint('[ChatCubit] Failed to decode WS event: $e');
      return;
    }

    // Parse raw event into typed event using StreamParser.
    final typed = StreamParser.parse(raw);
    if (typed == null) {
      // Unknown/malformed events are silently dropped by the parser.
      return;
    }

    // ── Route typed event ─────────────────────────────────────────────
    switch (typed) {
      case events.TokenEvent():
        _assembler.onEvent(typed);
        _updateOrCreateAssistantMessage();
        break;

      case events.TypingEvent():
        emit(ChatState.connected(messages: _messages, isTyping: true));
        break;

      case events.DoneEvent():
        _finalizeAssistantMessage();
        break;

      case events.ProgressEvent(
          :final agent, :final status, :final message):
        _handleProgress(agent, status, message);
        break;

      case events.CardDataEvent(:final cardType, :final data):
        _handleCardData(cardType, data);
        break;

      case events.TripCreatedEvent(:final tripId):
        _bookingTripId = tripId;
        _repo.updateConnectionToTrip(tripId);
        _assembler.reset();
        onTripCreated?.call();
        break;

      case events.TripApprovedEvent():
        debugPrint(
            '[ChatCubit] trip_approved event received, tripId=$_bookingTripId');
        _lockRenderedItinerary();
        _emitConnected(isTyping: false, bumpRefresh: true);
        onTripApproved?.call();
        break;

      case events.RefreshEvent():
        state.maybeWhen(
          connected:
              (messages, isTyping, refreshToken, isReconnecting) {
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

      case events.ErrorEvent(:final message):
        if (!isClosed) {
          emit(ChatState.error(message));
        }
        break;
    }
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

  // ── Sub-handlers ────────────────────────────────────────────────────

  void _handleProgress(String agent, String status, String message) {
    _pipelineSteps.removeWhere((s) => s.agent == agent);
    _pipelineSteps.add(PipelineStep(
      agent: agent,
      status: status == 'done'
          ? 'done'
          : (status == 'error' ? 'error' : 'running'),
      message: message,
    ));
    _emitConnected(isTyping: true, bumpRefresh: true);
  }

  void _handleCardData(String cardType, Map<String, dynamic> data) {
    switch (cardType) {
      case 'itinerary':
        _handleItineraryCard(data);
        break;
      case 'booking':
        _handleBookingCard(data);
        break;
      case 'hotel_options':
        _handleHotelOptionsCard(data);
        break;
      case 'flight_options':
        _handleFlightOptionsCard(data);
        break;
      case 'image_features':
        _handleImageFeaturesCard(data);
        break;
      default:
        debugPrint('[ChatCubit] Unknown card type: $cardType');
    }
  }

  void _handleItineraryCard(Map<String, dynamic> rawData) {
    final itinerary = _tryParseItinerary(rawData);
    if (itinerary == null) {
      debugPrint('[ChatCubit] ⚠️ itinerary_data parsing returned null');
      return;
    }

    final result = _assembler.onEvent(
        events.CardDataEvent(cardType: 'itinerary', data: rawData));
    if (result != null) {
      _updateOrCreateAssistantMessage();
      _renderedItinerarySignature = _computeItinerarySignature(itinerary);
    }
    _emitConnected(
        isTyping: state.maybeWhen(
          connected: (_, t, _, _) => t,
          orElse: () => false,
        ),
        bumpRefresh: true);
  }

  void _handleBookingCard(Map<String, dynamic> rawData) {
    try {
      final booking = BookingData.fromJson(rawData);
      if (booking.tripId != null) {
        _bookingTripId = booking.tripId;
      }

      // Check if booking card already exists
      final alreadyHasBooking = _messages.any((m) =>
          m.segments.any((s) => s is CardSegment && s.cardType == 'booking'));
      if (alreadyHasBooking) {
        debugPrint('[ChatCubit] Booking card exists — skipping duplicate');
        return;
      }

      _assembler
          .onEvent(events.CardDataEvent(cardType: 'booking', data: rawData));
      _updateOrCreateAssistantMessage();

      final rawHotel = rawData['hotel'] as Map<String, dynamic>?;
      if (rawHotel != null) {
        _selectedHotelInfo = rawHotel;
        if (_bookingTripId != null) {
          BookingDraftCache.saveDraft(
              tripId: _bookingTripId!, hotelInfo: rawHotel);
        }
      }
      _inBookingPhase = true;
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse booking_data: $e');
    }
  }

  void _handleHotelOptionsCard(Map<String, dynamic> rawData) {
    try {
      final payload = HotelOptionsPayload.fromJson(rawData);
      if (payload.options.isEmpty) return;

      _assembler.onEvent(
          events.CardDataEvent(cardType: 'hotel_options', data: rawData));
      _updateOrCreateAssistantMessage();
      _emitConnected(isTyping: false, bumpRefresh: true);
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse hotel_options: $e');
    }
  }

  void _handleFlightOptionsCard(Map<String, dynamic> rawData) {
    try {
      final offersList = rawData['offers'] ?? [];
      debugPrint(
          '[ChatCubit] 📡 flight_options — offers length=${offersList is List ? offersList.length : "N/A"}');
      final payload = FlightOptionsPayload.fromJson(rawData);
      if (payload.offers.isEmpty) return;

      _assembler.onEvent(
          events.CardDataEvent(cardType: 'flight_options', data: rawData));
      _updateOrCreateAssistantMessage();
      _emitConnected(isTyping: false, bumpRefresh: true);
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse flight_options: $e');
    }
  }

  void _handleImageFeaturesCard(Map<String, dynamic> rawData) {
    try {
      final photoData = PhotoAnalysisData.fromJson(rawData);
      if (!photoData.hasSignal) return;

      _assembler.onEvent(
          events.CardDataEvent(cardType: 'image_features', data: rawData));
      _updateOrCreateAssistantMessage();
      debugPrint('[ChatCubit] ✅ Attached Photo Analysis Card');
      _emitConnected(isTyping: false, bumpRefresh: true);
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse image_features: $e');
    }
  }

  // ── Message assembly helpers ────────────────────────────────────────

  /// Update or create the assistant message from the current assembler state.
  void _updateOrCreateAssistantMessage() {
    final segments = _assembler.segments;
    if (segments.isEmpty) return;

    if (_messages.isNotEmpty && !_messages.last.isUser) {
      _messages[_messages.length - 1] = _messages.last.copyWith(
        segments: segments,
        isStreaming: true,
      );
    } else {
      _messages.add(cm.ChatMessage(
        isUser: false,
        segments: segments,
        isStreaming: true,
      ));
    }
    _emitConnected(isTyping: true);
  }

  void _finalizeAssistantMessage() {
    final segments = _assembler.finalize();

    if (_messages.isNotEmpty && !_messages.last.isUser) {
      _messages[_messages.length - 1] = _messages.last.copyWith(
        segments: segments,
        isStreaming: false,
      );
    } else if (segments.isNotEmpty) {
      _messages.add(cm.ChatMessage(
        isUser: false,
        segments: segments,
        isStreaming: false,
      ));
    }

    _emitConnected(isTyping: false, bumpRefresh: true);
  }

  // ── Itinerary duplicate detection ───────────────────────────────────

  String _computeItinerarySignature(ItineraryData itinerary) {
    final stopIds = <String>[];
    for (final day in itinerary.days) {
      for (final stop in day.stops) {
        stopIds.add(stop.id);
      }
    }
    stopIds.sort();
    final hotelIds = itinerary.accommodationSuggestions
        .map((h) => h.id)
        .where((id) => id.isNotEmpty)
        .toList()
      ..sort();
    return '${itinerary.destination}|${itinerary.durationDays}|${stopIds.join(",")}|hotels:${hotelIds.join(",")}';
  }

  void _lockRenderedItinerary() {
    for (final msg in _messages.reversed) {
      for (final seg in msg.segments) {
        if (seg is CardSegment && seg.cardType == 'itinerary') {
          final it = seg.itinerary;
          if (it != null) {
            _renderedItinerarySignature =
                _computeItinerarySignature(it);
            debugPrint(
                '[ChatCubit] 🛑 Locked itinerary signature after approval: $_renderedItinerarySignature');
            return;
          }
        }
      }
    }
  }

  // ── Parsing helpers ─────────────────────────────────────────────────

  ItineraryData? _tryParseItinerary(Map<String, dynamic> raw) {
    try {
      final parsed = ItineraryData.fromJson(raw);
      if (parsed.days.isEmpty) {
        debugPrint(
            '[ChatCubit] ⚠️ itinerary parsed but has 0 days — data may be malformed');
        debugPrint('[ChatCubit] ⚠️ Raw data keys: ${raw.keys.toList()}');
      }
      return parsed;
    } catch (e) {
      debugPrint('[ChatCubit] ❌ Failed to parse itinerary JSON: $e');
      debugPrint(
          '[ChatCubit] ❌ Raw data keys: ${raw.keys.take(20).toList()}');
      return null;
    }
  }

  // ── History reconstruction ──────────────────────────────────────────

  cm.ChatMessage _historyToChatMessage(
      ChatHistoryMessage msg, String tripId) {
    final segments = <ChatSegment>[];
    Uint8List? decodedImage;

    if (msg.imageData != null && msg.imageData!.isNotEmpty) {
      try {
        decodedImage = base64Decode(msg.imageData!);
      } catch (e) {
        debugPrint('[ChatCubit] Failed to decode image_data: $e');
      }
    }

    // Text segment
    if (msg.content.isNotEmpty) {
      segments.add(TextSegment(text: msg.content));
    }

    // Card segments from card_data metadata
    final meta = msg.cardData;
    if (meta != null && meta.isNotEmpty) {
      final renderedCards =
          (meta['rendered_cards'] as List?)?.cast<String>() ?? [];

      if (renderedCards.contains('itinerary') &&
          meta['itinerary_data'] is Map) {
        segments.add(CardSegment(
          cardType: 'itinerary',
          rawData: Map<String, dynamic>.from(meta['itinerary_data'] as Map),
        ));
      }
      if (renderedCards.contains('hotel') &&
          meta['hotel_options'] is Map) {
        segments.add(CardSegment(
          cardType: 'hotel_options',
          rawData: Map<String, dynamic>.from(meta['hotel_options'] as Map),
        ));
      }
      if (renderedCards.contains('booking') &&
          meta['booking_data'] is Map) {
        segments.add(CardSegment(
          cardType: 'booking',
          rawData: Map<String, dynamic>.from(meta['booking_data'] as Map),
        ));
        final rawHotel =
            meta['booking_data']['hotel'] as Map<String, dynamic>?;
        if (rawHotel != null) {
          _selectedHotelInfo = rawHotel;
        }
        _bookingTripId = tripId;
      }
      if (renderedCards.contains('flight') &&
          meta['flight_options'] is Map) {
        segments.add(CardSegment(
          cardType: 'flight_options',
          rawData: Map<String, dynamic>.from(meta['flight_options'] as Map),
        ));
      }
      if (renderedCards.contains('photo_analysis') &&
          meta['image_features'] is Map) {
        segments.add(CardSegment(
          cardType: 'image_features',
          rawData: Map<String, dynamic>.from(meta['image_features'] as Map),
        ));
      }
      if (meta['flight_booking'] is Map) {
        _flightBookingData =
            Map<String, dynamic>.from(meta['flight_booking'] as Map);
      }
    }

    return cm.ChatMessage(
      isUser: msg.isUser,
      segments: segments,
      imageBytes: decodedImage,
    );
  }
}
