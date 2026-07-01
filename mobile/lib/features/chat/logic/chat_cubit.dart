import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/errors/api_result.dart';
import '../../bookings/data/cache/booking_draft_cache.dart';
import '../data/datasource/chat_ws_service.dart';
import '../data/repository/chat_repository.dart';
import '../data/models/chat_message.dart';
import '../data/models/itinerary_data.dart';
import '../data/models/hotel_option.dart';
import '../data/models/booking_data.dart';
import '../data/models/flight_options_payload.dart';
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
  
  /// Tracks the signature of the most recently rendered itinerary card.
  /// Used to suppress duplicate itinerary cards during phase transitions
  /// (e.g. when the AI re-sends the same itinerary during FLIGHT_SELECTION
  /// or HOTEL_SELECTION even though it hasn't actually changed).
  String? _renderedItinerarySignature;

  /// Whether the booking card has been shown (i.e., we're in the BOOKING
  /// phase on the backend).  When true, ANY user text input is redirected
  /// to "approve" because the backend's message interpreter has no BOOKING-
  /// phase action — the only valid action is approve_itinerary, which
  /// transitions from BOOKING to COMPLETED.  Without this, any user text
  /// gets classified as ask_clarification → safety-overridden to plan_trip
  /// → starts planning a new trip instead of completing the booking flow.
  bool _inBookingPhase = false;
  
  StreamSubscription<dynamic>? _subscription;
  StreamSubscription<WsConnectionState>? _wsStateSubscription;
  
  /// Tracks when reconnection started to enforce minimum banner display time.
  DateTime? _reconnectingSince;

  /// The last trip ID used for connection (null for new chats).
  String? _lastTripId;

  /// Called when a trip is created via chat so the parent can refresh trips.
  Function()? onTripCreated;

  /// Called when the trip is approved (trip_approved event received).
  /// Used by ChatScreen to navigate to TripDetailScreen after the backend
  /// has finished processing the approve action and committed to the DB.
  /// Unlike a fixed timer, this ensures the trip status is already
  /// awaiting_booking before the screen loads.
  Function()? onTripApproved;

  /// The trip_id from the most recent booking_data event, used for navigation.
  /// The ChatScreen reads this to navigate to TripDetailScreen when
  /// the user taps "Pay Now" on the BookingCard.
  String? _bookingTripId;

  /// The flight_booking payload (with raw_offer) from the backend,
  /// sent during the select_flight phase.  Stored here so the Pay Now
  /// flow can use it to call POST /flights/book/initiate without needing
  /// the raw_offer from the chat WebSocket again.
  Map<String, dynamic>? _flightBookingData;

  /// The hotel info from the booking_data payload (name, place_id,
  /// nightly_rate, total_cost, currency).  Populated when booking_data
  /// is received during the BOOKING phase.  Used by Pay Now to book
  /// the exact hotel the user selected rather than all stops.
  Map<String, dynamic>? _selectedHotelInfo;

  ChatCubit(this._repo) : super(const ChatState.initial()) {
    // Listen to WebSocket connection state changes for reconnection feedback.
    _wsStateSubscription = _repo.connectionStateStream.listen(_onConnectionStateChanged);
  }

  /// Current pipeline steps exposed for the UI to read.
  List<PipelineStep> get pipelineSteps => List.unmodifiable(_pipelineSteps);

  /// Start a fresh chat: disconnect current WS, clear all state, connect anew.
  Future<void> resetForNewChat() async {
    _repo.disconnect();
    // Clear cached draft for the abandoned trip
    if (_bookingTripId != null) {
      BookingDraftCache.clearDraft(_bookingTripId!);
    }
    _messages.clear();
    _pipelineSteps.clear();
    _buffer = "";
    _pendingItinerary = null;
    _renderedItinerarySignature = null;
    _inBookingPhase = false;
    _bookingTripId = null;
    _flightBookingData = null;
    _selectedHotelInfo = null;
    onTripApproved = null;
    _subscription?.cancel();
    _subscription = null;
    _lastTripId = null;
    await connect();
  }

  /// Switch to a trip chat: disconnect, clear state, load history, connect.
  Future<void> switchToTrip(String tripId) async {
    _repo.disconnect();
    // Note: we do NOT clear the old trip's cached draft here.
    // The cache is keyed by tripId, so switching to a different trip
    // won't cause a collision. If the user switches back, the cached
    // draft is still available.
    _messages.clear();
    _pipelineSteps.clear();
    _buffer = "";
    _pendingItinerary = null;
    _renderedItinerarySignature = null;
    _inBookingPhase = false;
    _bookingTripId = null;
    _flightBookingData = null;
    _selectedHotelInfo = null;
    onTripApproved = null;
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
      // 1. Load existing chat history from REST API.
      //    Each message may contain `metadata` — structured card data that
      //    was persisted alongside the text during the live chat. We parse
      //    it here to reconstruct cards exactly as they appeared live.
      final historyResult = await _repo.loadChatHistory(tripId);
      _messages.clear();
      historyResult.when(
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

            // ── Parse structured card_data into card data ─────────────
            //    The backend persists `rendered_cards` in card_data to
            //    explicitly tell us which card types were shown in live chat.
            //    Structured data like flight_booking is persisted for Pay Now
            //    even without being in rendered_cards.
            ItineraryData? itinerary;
            HotelOptionsPayload? hotelOptions;
            BookingData? bookingData;
            FlightOptionsPayload? flightOptions;

            final meta = msg.cardData;
            if (meta != null && meta.isNotEmpty) {
              // Read the rendered_cards list — only render cards explicitly
              // listed here. Empty list or absent = plain text message.
              final renderedCards =
                  (meta['rendered_cards'] as List?)?.cast<String>() ?? [];

              // itinerary_data — only parse if explicitly marked as rendered
              if (renderedCards.contains('itinerary') &&
                  meta['itinerary_data'] is Map<String, dynamic>) {
                itinerary = _tryParseItinerary(meta['itinerary_data']);
              }
              // hotel_options — only parse if explicitly marked as rendered
              if (renderedCards.contains('hotel') &&
                  meta['hotel_options'] is Map<String, dynamic>) {
                try {
                  hotelOptions = HotelOptionsPayload.fromJson(
                    meta['hotel_options'] as Map<String, dynamic>,
                  );
                } catch (e) {
                  debugPrint('[ChatCubit] Failed to parse hotel_options: $e');
                }
              }
              // booking_data — only parse if explicitly marked as rendered.
              // Also restore selectedHotelInfo and bookingTripId for Pay Now.
              if (renderedCards.contains('booking') &&
                  meta['booking_data'] is Map<String, dynamic>) {
                try {
                  bookingData = BookingData.fromJson(
                    meta['booking_data'] as Map<String, dynamic>,
                  );
                  final rawHotel = meta['booking_data']['hotel'] as Map<String, dynamic>?;
                  if (rawHotel != null) {
                    _selectedHotelInfo = rawHotel;
                  }
                  _bookingTripId = tripId;
                } catch (e) {
                  debugPrint('[ChatCubit] Failed to parse booking_data: $e');
                }
              }
              // flight_options — only parse if explicitly marked as rendered
              if (renderedCards.contains('flight') &&
                  meta['flight_options'] is Map<String, dynamic>) {
                try {
                  flightOptions = FlightOptionsPayload.fromJson(
                    meta['flight_options'] as Map<String, dynamic>,
                  );
                } catch (e) {
                  debugPrint('[ChatCubit] Failed to parse flight_options: $e');
                }
              }
              // flight_booking — raw_offer needed for Pay Now flow.
              // Parsed regardless of rendered_cards (this is data, not a card).
              if (meta['flight_booking'] is Map<String, dynamic>) {
                _flightBookingData =
                    meta['flight_booking'] as Map<String, dynamic>;
                debugPrint('[ChatCubit] ✅ Restored flight_booking from card_data');
              }
            }

            _messages.add(ChatMessage(
              text: msg.content,
              isUser: msg.isUser,
              isStreaming: false,
              imageBytes: decodedImage,
              itinerary: itinerary,
              hotelOptions: hotelOptions,
              bookingData: bookingData,
              flightOptions: flightOptions,
            ));
          }
        },
        failure: (e) {
          debugPrint('[ChatCubit] history load failed: $e');
        },
      );

      // 2. Restore cached booking draft (flight raw_offer + hotel info)
      //    so Pay Now works even after app restart or session switch.
      final draft = await BookingDraftCache.loadDraft(tripId);
      if (draft != null) {
        if (draft['flight_booking'] is Map<String, dynamic>) {
          _flightBookingData = draft['flight_booking'] as Map<String, dynamic>;
          debugPrint('[ChatCubit] ✅ Restored flight_booking from cache');
        }
        if (draft['hotel_info'] is Map<String, dynamic>) {
          _selectedHotelInfo = draft['hotel_info'] as Map<String, dynamic>;
          debugPrint('[ChatCubit] ✅ Restored hotel info from cache');
        }
      }

      // 4. Set bookingTripId so Pay Now works immediately after reconnect,
      //    even before any WebSocket booking_data event arrives.
      _bookingTripId = tripId;

      // 5. Connect WebSocket (without auto_msg to avoid regenerating the trip)
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

    // ── Booking phase redirect ───────────────────────────────────────────
    // After the booking card is shown (hotel selected, AI asks "Pay Now or
    // Do It Later?", the backend is in the BOOKING phase.  The only action
    // its interpreter can handle here is "approve_itinerary", which transitions
    // to COMPLETED.  Any other text gets classified as ask_clarification →
    // safety-overridden to plan_trip → replanning!  We redirect all text to
    // "approve" to ensure a clean transition to COMPLETED.
    if (_inBookingPhase && message.trim().isNotEmpty) {
      debugPrint('[ChatCubit] Booking phase active — redirecting "${message.trim()}" → "approve"');
      message = 'approve';
      _inBookingPhase = false;
    }

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

  void _applyPendingItineraryToLastAssistant() {
    if (_pendingItinerary == null) return;
    if (_messages.isEmpty || _messages.last.isUser) return;

    _messages[_messages.length - 1] = _messages.last.copyWith(
      itinerary: _pendingItinerary,
      text: '',
    );
    _pendingItinerary = null;
  }

  /// Compute a signature for an itinerary to detect duplicates.
  /// Uses destination + duration + sorted stop IDs across all days.
  String _computeItinerarySignature(ItineraryData itinerary) {
    final stopIds = <String>[];
    for (final day in itinerary.days) {
      for (final stop in day.stops) {
        stopIds.add(stop.id);
      }
    }
    stopIds.sort();
    return '${itinerary.destination}|${itinerary.durationDays}|${stopIds.join(",")}';
  }

  /// Check if an itinerary is a duplicate of what's already rendered.
  /// Returns true if this exact itinerary (same destination, days, stop IDs)
  /// has already been rendered as a card in the chat.
  bool _isDuplicateItinerary(ItineraryData itinerary) {
    if (_renderedItinerarySignature == null) return false;
    final sig = _computeItinerarySignature(itinerary);
    return sig == _renderedItinerarySignature;
  }

  /// Handle booking_data events from the backend.
  ///
  /// Checks for an existing booking card BEFORE adding a new one, so the
  /// booking_confirmed response (which carries duplicate booking_data)
  /// is skipped rather than creating a second card.
  ///
  /// Attaches the booking card to the last assistant message (replacing
  /// its text) so only the card renders, without duplicated AI text above
  /// it — matching how _attachItinerary works for the itinerary card.
  ///
  /// If the last assistant message already has an itinerary card attached
  /// (e.g. from a prior _attachItinerary call in the same response), the
  /// booking card is added as a new separate message instead, so the
  /// itinerary card is not overwritten.
  void _handleBookingData(Map<String, dynamic> raw) {
    try {
      final booking = BookingData.fromJson(raw);
      if (booking.tripId != null) {
        _bookingTripId = booking.tripId;
      }

      // Check BEFORE adding — if a booking card already exists, this is
      // a booking_confirmed duplicate.  Skip it to prevent confusion.
      final alreadyHasBookingCard = _messages.any((m) => m.bookingData != null);
      if (alreadyHasBookingCard) {
        debugPrint('[ChatCubit] Booking card exists — skipping duplicate booking_data (booking_confirmed)');
        return;
      }

      // Attach booking card to the last assistant message (replace text),
      // so only the card appears without duplicated AI text above it.
      // If the last message already has an itinerary card, create a new
      // message instead so we don't overwrite the itinerary.
      if (_messages.isNotEmpty && !_messages.last.isUser && _messages.last.itinerary == null) {
        _messages[_messages.length - 1] = _messages.last.copyWith(
          text: '',
          isStreaming: false,
          bookingData: booking,
        );
      } else {
        _messages.add(ChatMessage(
          text: '',
          isUser: false,
          isStreaming: false,
          bookingData: booking,
        ));
      }

      // Store selected hotel info (place_id, nightly_rate, total_cost)
      // so Pay Now can book the exact selected hotel.
      final rawHotel = raw['hotel'] as Map<String, dynamic>?;
      if (rawHotel != null) {
        _selectedHotelInfo = rawHotel;
        debugPrint('[ChatCubit] Stored selected hotel info: ${rawHotel["name"]} (place_id=${rawHotel["place_id"]})');
        // Persist to local storage so it survives app restarts
        if (_bookingTripId != null) {
          BookingDraftCache.saveDraft(
            tripId: _bookingTripId!,
            hotelInfo: rawHotel,
          );
        }
      }

      // Mark that we're now in the booking phase, so sendMessage()
      // redirects any user text to "approve" to prevent replanning.
      _inBookingPhase = true;
    } catch (e) {
      debugPrint('[ChatCubit] Failed to parse booking_data: $e');
    }
  }

  /// The trip_id from the most recent booking_data event, for UI navigation.
  String? get bookingTripId => _bookingTripId;

  /// The flight_booking data (with raw_offer) stored from the last
  /// select_flight event.  Null until a flight is selected.
  Map<String, dynamic>? get flightBookingData => _flightBookingData;

  /// The hotel info (place_id, nightly_rate, total_cost, name, currency)
  /// from the last booking_data event.  Null until the booking card is shown.
  Map<String, dynamic>? get selectedHotelInfo => _selectedHotelInfo;

  /// Store the selected flight's raw_offer so Pay Now can use it.
  /// Called from ChatScreen._selectFlight when the user taps a flight option.
  void setFlightBookingData(Map<String, dynamic> rawOffer) {
    _flightBookingData = {'raw_offer': rawOffer};
    debugPrint('[ChatCubit] ✅ Stored flight_booking data from flight selection (raw_offer keys: ${rawOffer.keys.toList()})');
    // Persist to local storage so it survives app restarts
    if (_bookingTripId != null) {
      BookingDraftCache.saveDraft(
        tripId: _bookingTripId!,
        flightBookingData: _flightBookingData,
      );
    }
  }

  /// Exit the booking phase so the user can type freely after "Do It Later".
  /// Without this, the first message after "Do It Later" would be silently
  /// redirected to "approve" by sendMessage().
  void leaveBookingPhase() {
    _inBookingPhase = false;
    debugPrint('[ChatCubit] Exited booking phase — user can type freely');
  }

  /// Mark the booking card as confirmed after Pay Now succeeds.
  /// Updates the booking data in-place so the UI shows the confirmed badge.
  /// Also clears the persisted draft since payment has been completed.
  void markBookingConfirmed() {
    for (var i = 0; i < _messages.length; i++) {
      final bd = _messages[i].bookingData;
      if (bd != null) {
        _messages[i] = _messages[i].copyWith(
          bookingData: bd.copyWith(isConfirmed: true),
        );
        _emitConnected(isTyping: false, bumpRefresh: true);
        debugPrint('[ChatCubit] Marked booking card as confirmed');
        // Clear the persisted draft — booking is done
        if (_bookingTripId != null) {
          BookingDraftCache.clearDraft(_bookingTripId!);
        }
        return;
      }
    }
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

          // Store trip_id for later navigation
          _bookingTripId = tripId;

          // Notify parent (e.g. MainShell) to refresh the trips list.
          onTripCreated?.call();
        }
        break;

      case "trip_approved":
        // The trip was approved (status → awaiting_booking/booking_pending).
        // The UI can read bookingTripId to navigate to the trip detail page.
        debugPrint('[ChatCubit] trip_approved event received, tripId=$_bookingTripId');
        if (_messages.isNotEmpty && !_messages.last.isUser) {
          final last = _messages.last;
          _messages[_messages.length - 1] = last.copyWith(
            isStreaming: false,
          );
        }
        _emitConnected(isTyping: false, bumpRefresh: true);
        // Notify the ChatScreen to navigate to TripDetailScreen.
        // This fires only if the user tapped "Pay Now" (which set onTripApproved).
        // "Book Later" does not set the callback, so no navigation occurs.
        onTripApproved?.call();
        break;

      case "result":
        final resultPayload = data["data"];
        if (resultPayload is Map) {
          // 🔍 DEBUG: Log all keys in the result payload to see what's available
          debugPrint('[ChatCubit] 🔍 result event received — payload keys: ${resultPayload.keys.toList()}');
          final hasFlightBooking = resultPayload.containsKey("flight_booking");
          debugPrint('[ChatCubit] 🔍 result payload has flight_booking key? $hasFlightBooking');
          if (hasFlightBooking) {
            final fb = resultPayload["flight_booking"];
            debugPrint('[ChatCubit] 🔍 flight_booking value type=${fb.runtimeType}, null? ${fb == null}, value=$fb');
          }

          // Parse itinerary if present — suppress duplicates from phase transitions
          final itinerary = _tryParseItinerary(resultPayload["itinerary"]);
          if (itinerary != null) {
            if (!_isDuplicateItinerary(itinerary)) {
              _attachItinerary(itinerary);
              _renderedItinerarySignature = _computeItinerarySignature(itinerary);
            } else {
              debugPrint('[ChatCubit] Suppressed duplicate itinerary in result event (phase transition)');
            }
          }

          // Parse booking_data if present (from booking / booking_confirmed events)
          final rawBooking = resultPayload["booking_data"];
          if (rawBooking is Map<String, dynamic>) {
            _handleBookingData(rawBooking);
          }

          // Handle flight_search_results if present (for Flutter to display)
          final flightSearchResults = resultPayload["flight_search_results"];
          if (flightSearchResults is List && flightSearchResults.isNotEmpty) {
            // Flight search results are handled by the AI text message,
            // no special card rendering needed on Flutter side
          }

          // Store flight_booking data (with raw_offer) for Pay Now flow
          final flightBooking = resultPayload["flight_booking"];
          if (flightBooking is Map<String, dynamic> && flightBooking.isNotEmpty) {
            _flightBookingData = flightBooking;
            debugPrint('[ChatCubit] ✅ Stored flight_booking data (raw_offer available: ${flightBooking.containsKey("raw_offer") && flightBooking["raw_offer"] != null})');
            // Persist to local storage so it survives app restarts
            if (_bookingTripId != null) {
              BookingDraftCache.saveDraft(
                tripId: _bookingTripId!,
                flightBookingData: flightBooking,
              );
            }
          } else {
            debugPrint('[ChatCubit] ❌ flight_booking NOT stored — type=${flightBooking?.runtimeType}, value=$flightBooking, isMap=${flightBooking is Map}, isNotEmpty=${(flightBooking is Map ? flightBooking.isNotEmpty : false)}');
          }

          final currentIsTyping = state.maybeWhen(
            connected: (_, isTyping, _, _) => isTyping,
            orElse: () => false,
          );
          _emitConnected(isTyping: currentIsTyping, bumpRefresh: true);
        }
        break;

      case "itinerary_data":
        final itinerary = _tryParseItinerary(data["data"]);
        if (itinerary != null) {
          // Suppress duplicate itinerary cards during phase transitions.
          // The AI engine sends the same itinerary with every response
          // even during FLIGHT_SELECTION/HOTEL_SELECTION phases — we only
          // want to render the card once (when it first arrives).
          if (!_isDuplicateItinerary(itinerary)) {
            _attachItinerary(itinerary);
            _renderedItinerarySignature = _computeItinerarySignature(itinerary);
          } else {
            debugPrint('[ChatCubit] Suppressed duplicate itinerary card (phase transition)');
          }
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
            // Attach to the last assistant message (replacing its text)
            // so only the card shows, without duplicated AI text above it.
            // If the last message already has an itinerary card, create a
            // new message instead so we don't overwrite the itinerary.
            if (_messages.isNotEmpty && !_messages.last.isUser && _messages.last.itinerary == null) {
              _messages[_messages.length - 1] = _messages.last.copyWith(
                text: '',
                isStreaming: false,
                hotelOptions: payload,
              );
            } else {
              _messages.add(ChatMessage(
                text: '',
                isUser: false,
                isStreaming: false,
                hotelOptions: payload,
              ));
            }
            _emitConnected(isTyping: false, bumpRefresh: true);
          }
        }
        break;

      case "booking_data":
        final rawBooking = data["data"];
        if (rawBooking is Map<String, dynamic>) {
          _handleBookingData(rawBooking);
        }
        break;

      case "flight_options":
        final rawFlight = data["data"];
        // DEBUG: Log flight_options event structure
        debugPrint('[ChatCubit] 📡 flight_options event — rawFlight type=${rawFlight.runtimeType}, isMap=${rawFlight is Map}');
        if (rawFlight is Map<String, dynamic>) {
          final offersList = rawFlight['offers'] ?? [];
          debugPrint('[ChatCubit] 📡 flight_options — offers type=${offersList.runtimeType}, length=${offersList is List ? offersList.length : "N/A"}, first keys=${offersList is List && offersList.isNotEmpty && offersList[0] is Map ? (offersList[0] as Map).keys.toList() : "N/A"}');
          final payload = FlightOptionsPayload.fromJson(rawFlight);
          if (payload.offers.isNotEmpty) {
            // Attach to the last assistant message (replacing its text)
            // so only the card shows, without duplicated AI text above it.
            // If the last message already has an itinerary card, create a
            // new message instead so we don't overwrite the itinerary.
            if (_messages.isNotEmpty && !_messages.last.isUser && _messages.last.itinerary == null) {
              _messages[_messages.length - 1] = _messages.last.copyWith(
                text: '',
                isStreaming: false,
                flightOptions: payload,
              );
            } else {
              _messages.add(ChatMessage(
                text: '',
                isUser: false,
                isStreaming: false,
                flightOptions: payload,
              ));
            }
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