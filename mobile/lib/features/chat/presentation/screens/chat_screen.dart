import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../../core/utils/image_picker_service.dart';
import '../../../../core/widgets/app_snackbar.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../data/models/chat_session_response.dart';
import '../../data/repository/chat_repository.dart';
import '../../logic/chat_cubit.dart';
import '../../logic/chat_state.dart';
import '../widgets/message_bubble.dart';
import '../widgets/pipeline_progress_widget.dart';

import '../widgets/suggestion_chips.dart';
import '../widgets/assistant_avatar.dart';
import '../../../trips/presentation/screens/trip_detail_screen.dart';
import '../../../payments/data/datasource/payment_service.dart';
import '../../../auth/data/datasource/firebase_auth_service.dart';

class ChatScreen extends StatefulWidget {
  final VoidCallback? onTripCreated;
  final String? initialTripId;
  final String? autoMessage;

  const ChatScreen({
    super.key,
    this.onTripCreated,
    this.initialTripId,
    this.autoMessage,
  });

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  List<ChatSessionResponse> _chatSessions = [];
  bool _loadingSessions = false;
  String? _activeTripId;

  @override
  void initState() {
    super.initState();
    _activeTripId = widget.initialTripId;
    if (_activeTripId == null) {
      _fetchChatSessions();
    }
  }

  Future<void> _fetchChatSessions() async {
    setState(() => _loadingSessions = true);
    try {
      final data = await locator<ApiServices>().getChatSessions();
      setState(() => _chatSessions = data);
    } catch (_) {}
    if (mounted) setState(() => _loadingSessions = false);
  }

  /// Called by _ChatViewState when the user navigates to a different chat.
  void _onSessionChanged(String? tripId) {
    setState(() => _activeTripId = tripId);
    if (tripId == null) {
      _fetchChatSessions();
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) {
        final cubit = ChatCubit(locator<ChatRepository>());
        if (widget.initialTripId != null) {
          cubit.connectToTrip(widget.initialTripId!, autoMsg: null);
        } else if (widget.autoMessage != null) {
          cubit.connectWithAutoMessage(widget.autoMessage!);
        } else {
          cubit.connect();
        }
        cubit.onTripCreated = widget.onTripCreated;
        return cubit;
      },
      child: _ChatView(
        scaffoldKey: _scaffoldKey,
        chatSessions: _chatSessions,
        loadingSessions: _loadingSessions,
        activeTripId: _activeTripId,
        onSessionChanged: _onSessionChanged,
      ),
    );
  }
}

// ─── Chat view with sidebar drawer ───────────────────────────────────────

class _ChatView extends StatefulWidget {
  final GlobalKey<ScaffoldState> scaffoldKey;
  final List<ChatSessionResponse> chatSessions;
  final bool loadingSessions;
  final String? activeTripId;
  final void Function(String?) onSessionChanged;

  const _ChatView({
    required this.scaffoldKey,
    required this.chatSessions,
    required this.loadingSessions,
    this.activeTripId,
    required this.onSessionChanged,
  });

  @override
  State<_ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<_ChatView>
    with SingleTickerProviderStateMixin {
  TourMateColors get tm => context.tm;

  late final AnimationController _emptyAnimController;

  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final ImagePickerService _imagePicker = ImagePickerService();
  int _lastMessageCount = 0;
  int _lastRefreshToken = 0;
  Uint8List? _selectedImageBytes;

  /// Open a fresh chat: disconnect, clear state, connect anew.
  void _startNewChat() {
    context.read<ChatCubit>().resetForNewChat();
    widget.onSessionChanged(null);
  }

  /// Open a past chat session: disconnect, clear state, switch to that trip.
  void _openSession(ChatSessionResponse session) {
    final tripInfo = session.trip;
    if (tripInfo != null) {
      context.read<ChatCubit>().switchToTrip(tripInfo.tripId!);
      widget.onSessionChanged(tripInfo.tripId);
    }
  }

  @override
  void initState() {
    super.initState();
    _emptyAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _inputController.dispose();
    _emptyAnimController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _pickImage() async {
    final imageBytes = await _imagePicker.pickImageFromGallery();
    if (imageBytes != null) {
      setState(() => _selectedImageBytes = imageBytes);
    }
  }

  void _clearImage() {
    setState(() => _selectedImageBytes = null);
  }

  void _sendMessage(ChatCubit cubit) {
    final text = _inputController.text.trim();
    if (text.isEmpty && _selectedImageBytes == null) return;
    cubit.sendMessage(text, imageBytes: _selectedImageBytes);
    _inputController.clear();
    _clearImage();
    _scrollToBottom();
  }

  /// Called when the user taps the green "Approve Itinerary" button.
  void _sendApprove(ChatCubit cubit) {
    cubit.sendMessage('approve');
  }

  /// Called when the user taps a specific hotel option.
  /// Sends the hotel name so the backend's message interpreter extracts
  /// ``selected_hotel_name`` and routes to select_hotel action.
  void _selectHotel(ChatCubit cubit, dynamic hotel) {
    // hotel is a HotelOption object with name, id, etc.
    // Dynamic access works: hotel.name returns HotelOption.name
    final name = hotel?.name ?? '';
    final msg = name.isNotEmpty ? 'Select hotel: $name' : 'Select hotel';
    cubit.sendMessage(msg);
  }

  /// Called when the user taps a specific flight option.
  /// Sends airline + flight number so the backend's message interpreter
  /// can match it to a flight offer and route to select_flight action.
  /// Also stores the selected flight's raw_offer in the cubit so the
  /// Pay Now flow can later use it to book the exact flight.
  void _selectFlight(ChatCubit cubit, dynamic flight) {
    // flight is a FlightOffer object with airlineName, flightNumber, etc.
    // Dynamic access works: flight.airlineName returns FlightOffer.airlineName
    final airline = flight?.airlineName ?? flight?.airlineCode ?? '';
    final flightNum = flight?.flightNumber ?? '';
    final desc = airline.isNotEmpty && flightNum.isNotEmpty
        ? '$airline $flightNum'
        : (airline.isNotEmpty ? airline : '');
    final msg = desc.isNotEmpty
        ? "I'll take the $desc flight"
        : 'Pick the first one';

    // DEBUG: Log the flight object's rawOffer status
    debugPrint('[ChatScreen] _selectFlight — flight type=${flight.runtimeType}, rawOffer type=${flight?.rawOffer.runtimeType}, rawOffer isEmpty=${flight?.rawOffer is Map ? (flight!.rawOffer as Map).isEmpty : "N/A"}, rawOffer keys=${flight?.rawOffer is Map ? (flight!.rawOffer as Map).keys.take(10).toList() : "N/A"}');

    // Store the selected flight's raw_offer so Pay Now can use it
    final rawOffer = flight?.rawOffer;
    if (rawOffer is Map<String, dynamic> && rawOffer.isNotEmpty) {
      cubit.setFlightBookingData(rawOffer);
    } else {
      debugPrint('[ChatScreen] ⚠️ No raw_offer on selected flight — Pay Now will only cover hotel');
    }

    cubit.sendMessage(msg);
  }

  /// Called when the user taps "Pay Now" on the booking card.
  ///
  /// **Smart flow** — handles flight-only, hotel-only, or both together:
  ///   - Both: POST /bookings/combined/initiate (flight + hotel) → one Stripe sheet
  ///     → POST /bookings/combined/confirm
  ///   - Flight only: POST /bookings/combined/initiate (no hotel) → Stripe sheet
  ///     → POST /bookings/combined/confirm (no hotel_booking_id)
  ///   - Hotel only: POST /bookings/combined/initiate (no flight) → Stripe sheet
  ///     → POST /bookings/combined/confirm (no priced_offer)
  Future<void> _onBookingPayNow(ChatCubit cubit) async {
    debugPrint('[ChatScreen] _onBookingPayNow CALLED');
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    final tripId = cubit.bookingTripId;
    if (tripId == null || tripId.isEmpty) {
      debugPrint('[ChatScreen] tripId is null or empty, returning early');
      return;
    }

    // ── Gather available data ─────────────────────────────
    final flightBooking = cubit.flightBookingData;
    final rawOffer = flightBooking?['raw_offer'] as Map<String, dynamic>?;
    final hotelInfo = cubit.selectedHotelInfo;

    final hasFlight = rawOffer != null && rawOffer.isNotEmpty;
    final hasHotel = hotelInfo != null;

    debugPrint('[ChatScreen] Pay Now — hasFlight=$hasFlight, hasHotel=$hasHotel');

    if (!hasFlight && !hasHotel) {
      if (context.mounted) {
        AppSnackbar.error(context,
            'Please select both or at least one (flight / hotel) before paying.');
      }
      return;
    }

    // Extract hotel fields (if any)
    String? placeId;
    double totalCost = 0;
    String currency = 'USD';
    if (hasHotel) {
      placeId = hotelInfo['place_id'] as String?;
      totalCost = (hotelInfo['total_cost'] as num?)?.toDouble() ??
          (hotelInfo['nightly_rate'] as num?)?.toDouble() ?? 0;
      currency = hotelInfo['currency'] as String? ?? 'USD';

      if (placeId == null || placeId.isEmpty || totalCost <= 0) {
        if (context.mounted) {
          AppSnackbar.error(
              context, 'Hotel info is incomplete. Please re-select the hotel.');
        }
        return;
      }
    }

    // ── Step 1: Update trip status ────────────────────────
    try {
      await locator<ApiServices>().updateTripStatus(
        tripId,
        {'status': 'awaiting_booking'},
      );
    } catch (e) {
      debugPrint('[ChatScreen] updateTripStatus failed: $e');
    }

    final dio = locator<Dio>();

    try {
      // ── Step 2: Combined initiate ──────────────────────
      // Build body dynamically — only include what's available
      final initiateBody = <String, dynamic>{
        'trip_id': tripId,
      };
      if (hasFlight) {
        initiateBody['raw_offer'] = rawOffer;
      }
      if (hasHotel) {
        initiateBody['hotel_place_id'] = placeId;
        initiateBody['hotel_total_cost'] = totalCost;
        initiateBody['hotel_currency'] = currency;
      }

      debugPrint('[ChatScreen] Calling POST /bookings/combined/initiate (flight=$hasFlight, hotel=$hasHotel)...');
      final initiateResp =
          await dio.post('/api/v1/bookings/combined/initiate', data: initiateBody);

      final initData = initiateResp.data as Map<String, dynamic>;
      final clientSecret = initData['client_secret'] as String;
      final pricedOffer = initData['priced_offer']; // null when hotel-only
      final hotelBookingId = initData['hotel_booking_id']; // null when flight-only
      debugPrint('[ChatScreen] Combined initiate OK: PI=${initData['payment_intent_id']}, '
          'combined_amount=${initData['combined_amount']} ${initData['currency']}');

      // ── Step 3: Open Stripe Payment Sheet (ONCE) ───────
      final paymentService = locator<PaymentService>();
      debugPrint('[ChatScreen] Opening Stripe Payment Sheet...');
      final paymentSuccess = await paymentService.payWithStripeSheet(
        clientSecret: clientSecret,
      );
      debugPrint('[ChatScreen] Stripe Payment Sheet result: $paymentSuccess');

      if (!paymentSuccess) {
        if (mounted) {
          messenger.showSnackBar(
            SnackBar(
              content: const Text('Payment was cancelled or failed. You can try again later.'),
              backgroundColor: tm.error,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
              margin: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
              padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
              duration: const Duration(seconds: 4),
              dismissDirection: DismissDirection.horizontal,
            ),
          );
        }
        return;
      }

      // ── Step 4: Combined confirm ───────────────────────
      // Build traveler info from Firebase user (if available)
      String travelerEmail = 'traveler@example.com';
      String travelerFirstName = 'Test';
      String travelerLastName = 'User';
      try {
        final firebaseAuth = locator<FirebaseAuthService>();
        final user = firebaseAuth.currentUser;
        if (user != null) {
          travelerEmail = user.email ?? travelerEmail;
          final displayName = user.displayName ?? '';
          final parts = displayName.split(' ');
          if (parts.length >= 2) {
            travelerFirstName = parts[0];
            travelerLastName = parts.sublist(1).join(' ');
          } else if (parts.isNotEmpty) {
            travelerFirstName = parts[0];
          }
        }
      } catch (_) {}

      final confirmBody = <String, dynamic>{
        'payment_intent_id': initData['payment_intent_id'],
        'trip_id': tripId,
      };
      if (pricedOffer != null) {
        confirmBody['priced_offer'] = pricedOffer;
        confirmBody['traveler_first_name'] = travelerFirstName;
        confirmBody['traveler_last_name'] = travelerLastName;
        confirmBody['traveler_date_of_birth'] = '1990-01-15';
        confirmBody['traveler_gender'] = 'MALE';
        confirmBody['traveler_email'] = travelerEmail;
        confirmBody['traveler_phone'] = '+201000000000';
      }
      if (hotelBookingId != null) {
        confirmBody['hotel_booking_id'] = hotelBookingId;
      }

      debugPrint('[ChatScreen] Calling POST /bookings/combined/confirm...');
      final confirmResp =
          await dio.post('/api/v1/bookings/combined/confirm', data: confirmBody);

      debugPrint('[ChatScreen] Combined confirm OK: ${confirmResp.data}');

      // ── Step 5: Finalize UI ─────────────────────────────
      cubit.markBookingConfirmed();

      // Build success message based on what was booked
      final label = (hasFlight && hasHotel)
          ? 'Flight + Hotel'
          : hasFlight
              ? 'Flight'
              : 'Hotel';

      if (mounted) {
        messenger.showSnackBar(
          SnackBar(
            content: Text('✅ $label booked!'),
            backgroundColor: tm.success,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
            margin: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
            duration: const Duration(seconds: 3),
            dismissDirection: DismissDirection.horizontal,
          ),
        );
        navigator.push(
          MaterialPageRoute(
            builder: (_) => TripDetailScreen(tripId: tripId),
          ),
        );
      }
    } catch (e) {
      debugPrint('[ChatScreen] Combined booking FAILED: $e');
      if (mounted) {
        messenger.showSnackBar(
          SnackBar(
            content: Text('Booking failed: ${e.toString().replaceFirst(RegExp(r'^.+?: '), '')}'),
            backgroundColor: tm.error,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
            margin: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
            duration: const Duration(seconds: 4),
            dismissDirection: DismissDirection.horizontal,
          ),
        );
      }
    }
  }



  /// Called when the user taps "Do It Later" on the booking card.
  /// Sets the trip status to `awaiting_booking` so the trip is ready
  /// for payment later.  Does NOT reset the chat — the booking card
  /// stays visible so the user can tap Pay Now at any time.
  Future<void> _onBookingLater(ChatCubit cubit) async {
    final messenger = ScaffoldMessenger.of(context);
    final tripId = cubit.bookingTripId;
    if (tripId == null || tripId.isEmpty) return;

    String? patchError;
    try {
      await locator<ApiServices>().updateTripStatus(
        tripId,
        {'status': 'awaiting_booking'},
      );
    } catch (e) {
      patchError = e.toString();
      debugPrint('[ChatScreen] updateTripStatus (book later) failed: $e');
    }

    if (patchError != null && mounted) {
      messenger.showSnackBar(
        SnackBar(
          content: Text('Could not update trip status: $patchError.'),
          backgroundColor: tm.error,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
          margin: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
          padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
          duration: const Duration(seconds: 4),
          dismissDirection: DismissDirection.horizontal,
        ),
      );
    } else if (mounted) {
      messenger.showSnackBar(
        SnackBar(
          content: const Text('Trip saved — you can pay whenever you\'re ready.'),
          backgroundColor: tm.info,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(RadiusTokens.xl2)),
          margin: const EdgeInsets.fromLTRB(Spacing.xl3, 0, Spacing.xl3, Spacing.xl5),
          padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
          duration: const Duration(seconds: 3),
          dismissDirection: DismissDirection.horizontal,
        ),
      );
    }

    // Allow the user to type freely — prevent sendMessage from redirecting
    // their next input to "approve" (which was active during the booking phase).
    cubit.leaveBookingPhase();
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ChatCubit>();
    final hasBack = widget.activeTripId != null;
    final showSidebarBtn = !hasBack;

    return Scaffold(
      key: widget.scaffoldKey,
      backgroundColor: tm.nearWhite,
      drawer: showSidebarBtn ? _buildSidebar(context) : null,
      body: SafeArea(
        child: Column(
          children: [
            // ── Header ─────────────────────────────────
            _buildHeader(cubit, hasBack, showSidebarBtn),

            // ── Chat area ──────────────────────────────
            Expanded(
              child: BlocBuilder<ChatCubit, ChatState>(
                builder: (context, state) {
                  return state.when(
                    initial: () => const SizedBox(),
                    loading: () =>
                        const Center(child: TMLoadingIndicator(message: 'Connecting...')),
                    connected: (messages, isTyping, refreshToken, isReconnecting) {
                      if (messages.isEmpty && !isTyping) {
                        return _buildEmptyState();
                      }

                      final steps = cubit.pipelineSteps;
                      final showTyping = isTyping && steps.isEmpty;
                      final showPipeline = isTyping && steps.isNotEmpty;
                      final itemCount = messages.length +
                          (showPipeline ? 1 : 0) +
                          (showTyping ? 1 : 0);

                      if (messages.length != _lastMessageCount) {
                        _lastMessageCount = messages.length;
                        _scrollToBottom();
                      } else if (refreshToken != _lastRefreshToken) {
                        _lastRefreshToken = refreshToken;
                        _scrollToBottom();
                      } else if (isTyping && messages.isNotEmpty) {
                        _scrollToBottom();
                      }

                      return Column(
                        children: [
                          if (isReconnecting) const _ReconnectingBanner(),
                          Expanded(
                            child: ListView.builder(
                              controller: _scrollController,
                              padding: const EdgeInsets.all(Spacing.xl),
                              itemCount: itemCount,
                              itemBuilder: (_, i) {
                                if (showPipeline && i == messages.length) {
                                  return PipelineProgressWidget(steps: steps);
                                }
                                if (showTyping && i == messages.length) {
                                  return const _TypingIndicator();
                                }
                                return MessageBubble(
                                key: ValueKey(
                                  'msg-$i-${messages[i].itinerary != null}-$refreshToken',
                                ),
                                msg: messages[i],
                                onApproveItinerary: () => _sendApprove(cubit),
                                onSelectHotel: (hotel) => _selectHotel(cubit, hotel),
                                onSelectFlight: (flight) => _selectFlight(cubit, flight),
                                onBookingPayNow: () => _onBookingPayNow(cubit),
                                onBookingLater: () => _onBookingLater(cubit),
                              );
                              },
                            ),
                          ),
                        ],
                      );
                    },
                    error: (msg) => _buildError(msg, cubit),
                  );
                },
              ),
            ),

            // ── Input bar ──────────────────────────────
            _buildInputBar(cubit),
          ],
        ),
      ),
    );
  }

  // ── Premium Sidebar Drawer ───────────────────────────────────────────

  Widget _buildSidebar(BuildContext context) {
    return Drawer(
      backgroundColor: tm.brandWhite,
      child: SafeArea(
        child: Column(
          children: [
            // Premium header
            Container(
              padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.xl5, Spacing.xl4, Spacing.xl3),
              width: double.infinity,
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: tm.divider, width: 0.5)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(Spacing.md),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(RadiusTokens.lg),
                          border: Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                        ),
                        child: Icon(Icons.chat_bubble_outline, color: tm.sapphireLight, size: 18),
                      ),
                      const SizedBox(width: Spacing.xl),
                      Text(
                        'Chats',
                        style: GoogleFonts.inter(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          color: tm.textPrimary,
                          letterSpacing: -0.4,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: Spacing.xs),
                  Text(
                    '${widget.chatSessions.length} conversations',
                    style: GoogleFonts.inter(fontSize: 13, color: tm.textTertiary),
                  ),
                  const SizedBox(height: Spacing.xl3),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pop(context);
                        _startNewChat();
                      },
                      icon: Icon(Icons.add_rounded, size: 18, color: tm.brandWhite),
                      label: Text(
                        'New Chat',
                        style: GoogleFonts.inter(fontWeight: FontWeight.w600),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: tm.deepNavy,
                        foregroundColor: tm.brandWhite,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(RadiusTokens.xl),
                          side: BorderSide(color: tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: Spacing.xl),
                        elevation: 0,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // Chat sessions list
            Expanded(
              child: widget.loadingSessions
                  ? const Center(child: TMLoadingIndicator(message: 'Loading chats...'))
                  : widget.chatSessions.isEmpty
                      ? TMEmptyState(
                          icon: Icons.chat_bubble_outline,
                          title: 'No past chats yet',
                          subtitle: 'Start a new conversation with TourMate',
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(vertical: Spacing.sm),
                          itemCount: widget.chatSessions.length,
                          separatorBuilder: (_, _) => Divider(
                            height: 1,
                            indent: Spacing.xl4,
                            endIndent: Spacing.xl4,
                            color: tm.divider,
                          ),
                          itemBuilder: (_, i) =>
                              _buildSidebarItem(widget.chatSessions[i]),
                        ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSidebarItem(ChatSessionResponse session) {
    final tripInfo = session.trip;
    final destination = tripInfo?.destination ?? 'Chat';
    final lastMessage = session.lastMessage;

    return InkWell(
      onTap: () {
        Navigator.pop(context);
        _openSession(session);
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4, vertical: Spacing.xl2),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(Spacing.lg),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
              ),
              child: Icon(
                tripInfo != null ? Icons.card_travel : Icons.chat_bubble_outline,
                size: 16,
                color: tm.sapphireLight,
              ),
            ),
            const SizedBox(width: Spacing.xl2),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    destination,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: tm.textPrimary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (lastMessage != null) ...[
                    const SizedBox(height: Spacing.xxs),
                    Text(
                      lastMessage,
                      style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: tm.border, size: 16),
          ],
        ),
      ),
    );
  }

  // ── Premium Header ───────────────────────────────────────────────────

  Widget _buildHeader(ChatCubit cubit, bool hasBack, bool showSidebarBtn) {
    return Container(
      padding: EdgeInsets.only(
        top: Spacing.sm,
        left: Spacing.xl3,
        right: Spacing.xl3,
        bottom: Spacing.sm,
      ),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        border: Border(bottom: BorderSide(color: tm.divider, width: 0.5)),
      ),
      child: Row(
        children: [
          if (hasBack)
            Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
                onTap: () {
                  if (Navigator.canPop(context)) {
                    Navigator.pop(context);
                  } else {
                    _startNewChat();
                  }
                },
                child: Container(
                  padding: const EdgeInsets.all(Spacing.md),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.lg),
                    border: Border.all(color: tm.borderLight),
                  ),
                  child: Icon(Icons.arrow_back_rounded, color: tm.textPrimary, size: 18),
                ),
              ),
            ),
          if (showSidebarBtn)
            Material(
              color: Colors.transparent,
              child: InkWell(
                borderRadius: BorderRadius.circular(RadiusTokens.lg),
                onTap: () => widget.scaffoldKey.currentState?.openDrawer(),
                child: Container(
                  padding: const EdgeInsets.all(Spacing.md),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    borderRadius: BorderRadius.circular(RadiusTokens.lg),
                    border: Border.all(color: tm.borderLight),
                  ),
                  child: Icon(Icons.menu_rounded, color: tm.textPrimary, size: 18),
                ),
              ),
            ),
          const SizedBox(width: Spacing.lg),          // Logo — standalone brand mark, no container
          Image.asset(
            'assets/images/logo.png',
            width: 38,
            height: 38,
            fit: BoxFit.contain,
          ),
          const SizedBox(width: Spacing.lg),
          Text(
            widget.activeTripId != null ? "Trip Chat" : "TourMate",
            style: GoogleFonts.inter(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: tm.textPrimary,
              letterSpacing: -0.3,
            ),
          ),
          const Spacer(),
        ],
      ),
    );
  }

  Widget _buildError(String msg, ChatCubit cubit) {
    debugPrint('[ChatScreen] _buildError: $msg');
    return TMErrorState(
      message: msg,
      onRetry: () => cubit.reconnect(),
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: Spacing.xl10),
          // Premium concierge avatar — staggered entrance
          FadeTransition(
            opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
              CurvedAnimation(
                parent: _emptyAnimController,
                curve:
                    const Interval(0.0, 0.25, curve: Curves.easeOut),
              ),
            ),
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.3),
                end: Offset.zero,
              ).animate(
                CurvedAnimation(
                  parent: _emptyAnimController,
                  curve: const Interval(0.0, 0.25, curve: Curves.easeOutCubic),
                ),
              ),
              child: const AssistantAvatar(
                size: AssistantAvatarSize.xlarge,
              ),
            ),
          ),
          const SizedBox(height: Spacing.xl6),
          // "Where to today?" title — staggered entrance
          FadeTransition(
            opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
              CurvedAnimation(
                parent: _emptyAnimController,
                curve:
                    const Interval(0.08, 0.33, curve: Curves.easeOut),
              ),
            ),
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.25),
                end: Offset.zero,
              ).animate(
                CurvedAnimation(
                  parent: _emptyAnimController,
                  curve: const Interval(0.08, 0.33, curve: Curves.easeOutCubic),
                ),
              ),
              child: Text(
                "Where to today?",
                style: GoogleFonts.inter(
                  fontSize: 26,
                  fontWeight: FontWeight.w700,
                  color: tm.textPrimary,
                  letterSpacing: -0.5,
                ),
              ),
            ),
          ),
          const SizedBox(height: Spacing.lg),
          // Welcome message — staggered entrance
          FadeTransition(
            opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
              CurvedAnimation(
                parent: _emptyAnimController,
                curve:
                    const Interval(0.16, 0.41, curve: Curves.easeOut),
              ),
            ),
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.2),
                end: Offset.zero,
              ).animate(
                CurvedAnimation(
                  parent: _emptyAnimController,
                  curve: const Interval(0.16, 0.41, curve: Curves.easeOutCubic),
                ),
              ),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text.rich(
                  TextSpan(
                    style: GoogleFonts.inter(
                      color: tm.textSecondary,
                      fontSize: 14,
                      height: 1.5,
                    ),
                    children: [
                      TextSpan(
                        text: "Hey there",
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: tm.textPrimary.withValues(alpha: 0.8),
                        ),
                      ),
                      const TextSpan(
                        text:
                            ", I'm your TourMate concierge. Ask me anything about your next adventure.",
                      ),
                    ],
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ),
          const SizedBox(height: Spacing.xl7),
          // accent line — staggered entrance
          FadeTransition(
            opacity: Tween<double>(begin: 0.0, end: 1.0).animate(
              CurvedAnimation(
                parent: _emptyAnimController,
                curve:
                    const Interval(0.24, 0.49, curve: Curves.easeOut),
              ),
            ),
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.15),
                end: Offset.zero,
              ).animate(
                CurvedAnimation(
                  parent: _emptyAnimController,
                  curve: const Interval(0.24, 0.49, curve: Curves.easeOutCubic),
                ),
              ),
              child: Container(
                width: 48,
                height: 2,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      Colors.transparent,
                      tm.sapphire.withValues(alpha: 0.6),
                      Colors.transparent,
                    ],
                  ),
                  borderRadius: BorderRadius.circular(1),
                ),
              ),
            ),
          ),
          const SizedBox(height: Spacing.xl7),
          // Quick suggestion chips (have their own staggered animation)
          SuggestionChips(
            onChipTapped: (message) {
              final cubit = context.read<ChatCubit>();
              cubit.sendMessage(message);
            },
          ),            const SizedBox(height: Spacing.xl8),
        ],
      ),
    );
  }
  Widget _buildInputBar(ChatCubit cubit) {
    return Container(
      padding: EdgeInsets.fromLTRB(Spacing.xl3, Spacing.sm, Spacing.xl3, Spacing.xl4),
      decoration: BoxDecoration(
        color: tm.brandWhite,
        border: Border(top: BorderSide(color: tm.divider, width: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (_selectedImageBytes != null)
            Container(
              margin: const EdgeInsets.only(bottom: Spacing.md),
              padding: const EdgeInsets.all(Spacing.md),
              decoration: BoxDecoration(
                color: tm.surface,
                borderRadius: BorderRadius.circular(RadiusTokens.xl),
                border: Border.all(color: tm.borderLight),
              ),
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                    child: Image.memory(
                      _selectedImageBytes!,
                      height: 80,
                      width: 80,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: 4,
                    right: 4,
                    child: GestureDetector(
                      onTap: _clearImage,
                      child: Container(
                        padding: const EdgeInsets.all(Spacing.xs),
                        decoration: BoxDecoration(
                          color: tm.deepNavy.withValues(alpha: 0.6),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(Icons.close, color: tm.brandWhite, size: 14),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.xxs),
            decoration: BoxDecoration(
              color: tm.surface,
              borderRadius: BorderRadius.circular(RadiusTokens.xl2 + 14),
              border: Border.all(color: tm.borderLight),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                SizedBox(
                  width: 38,
                  height: 38,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    icon: Icon(Icons.camera_alt_outlined, size: 20, color: tm.textTertiary),
                    onPressed: _pickImage,
                    splashRadius: 20,
                  ),
                ),
                const SizedBox(width: Spacing.md),
                Expanded(
                  child: TextField(
                    controller: _inputController,
                    maxLines: 3,
                    minLines: 1,
                    textInputAction: TextInputAction.newline,
                    decoration: InputDecoration(
                      hintText: "Ask your travel concierge...",
                      hintStyle: GoogleFonts.inter(color: tm.textTertiary, fontSize: 15),
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: const EdgeInsets.symmetric(vertical: Spacing.lg),
                    ),
                    style: GoogleFonts.inter(fontSize: 15, color: tm.textPrimary),
                    onSubmitted: (_) => _sendMessage(cubit),
                  ),
                ),
                const SizedBox(width: Spacing.sm),
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [tm.deepRoyalBlue, tm.sapphire],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(RadiusTokens.full),
                    boxShadow: [
                      BoxShadow(
                        color: tm.deepRoyalBlue.withValues(alpha: 0.25),
                        blurRadius: 6,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    icon: Icon(Icons.send_rounded, size: 18, color: tm.brandWhite),
                    onPressed: () => _sendMessage(cubit),
                    splashRadius: 20,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// ================= PREMIUM RECONNECTING BANNER =================
class _ReconnectingBanner extends StatelessWidget {
  const _ReconnectingBanner();

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.sm),
      decoration: BoxDecoration(
        color: tm.deepRoyalBlue.withValues(alpha: 0.06),
        border: Border(bottom: BorderSide(color: tm.deepRoyalBlue.withValues(alpha: 0.15))),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: tm.deepRoyalBlue,
            ),
          ),
          const SizedBox(width: Spacing.lg),
          Text(
            'Reconnecting...',
            style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: tm.deepRoyalBlue),
          ),
        ],
      ),
    );
  }
}

/// ================= PREMIUM TYPING INDICATOR =================
class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: Spacing.xs),
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.md),
        decoration: BoxDecoration(
          color: tm.brandWhite,
          borderRadius: BorderRadius.circular(20).copyWith(
            bottomLeft: const Radius.circular(RadiusTokens.xs),
          ),
          border: Border.all(color: tm.borderLight),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Animated dots
            SizedBox(
              width: 32,
              height: 16,
              child: AnimatedBuilder(
                animation: _controller,
                builder: (context, _) {
                  return Row(
                    mainAxisSize: MainAxisSize.min,
                    children: List.generate(3, (i) {
                  final delay = i * 0.25;
                  final raw = (_controller.value - delay);
                  final sine = (math.sin(raw * 2 * math.pi) + 1) / 2;
                  final opacity = 0.3 + sine * 0.7;
                      return Padding(
                        padding: EdgeInsets.only(left: i > 0 ? Spacing.sm : 0),
                        child: Opacity(
                          opacity: opacity.toDouble(),
                          child: Container(
                            width: 7,
                            height: 7,
                            decoration: BoxDecoration(
                              color: tm.deepRoyalBlue,
                              shape: BoxShape.circle,
                            ),
                          ),
                        ),
                      );
                    }),
                  );
                },
              ),
            ),
            const SizedBox(width: Spacing.md),
            // "TourMate is thinking" label
            Text(
              'TourMate is thinking',
              style: GoogleFonts.inter(
                fontSize: 12,
                color: tm.textTertiary,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}


