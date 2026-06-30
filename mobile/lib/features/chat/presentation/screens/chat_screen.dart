import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../../../core/utils/image_picker_service.dart';
import '../../data/models/chat_session_response.dart';
import '../../data/repository/chat_repository.dart';
import '../../logic/chat_cubit.dart';
import '../../logic/chat_state.dart';
import '../widgets/message_bubble.dart';
import '../widgets/pipeline_progress_widget.dart';
import '../../../trips/presentation/screens/trip_detail_screen.dart';

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

class _ChatViewState extends State<_ChatView> {
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
  void dispose() {
    _scrollController.dispose();
    _inputController.dispose();
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

  /// Called when the user selects a hotel option to start booking.
  void _selectHotel(ChatCubit cubit, dynamic hotel) {
    // In the future, this will trigger the booking flow.
    // For now, send a message to the backend indicating the selection.
    cubit.sendMessage('book');
  }

  /// Called when the user taps "Pay Now" on the booking card.
  /// Approves the booking via WS and navigates to the trip detail page.
  void _onBookingPayNow(ChatCubit cubit) {
    // Send explicit approve text to trigger COMPLETED phase
    // ("1️⃣" may not be properly interpreted by the AI engine)
    cubit.sendMessage('approve');

    // The trip already exists with status awaiting_booking from the initial
    // itinerary approval. Navigate to the trip detail page where the payment
    // section will handle booking creation and payment.
    final tripId = cubit.bookingTripId;
    if (tripId != null && tripId.isNotEmpty) {
      // Small delay to let the WS message send before navigating
      Future.delayed(const Duration(milliseconds: 800), () {
        if (!mounted) return;
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => TripDetailScreen(tripId: tripId),
          ),
        );
      });
    }
  }

  /// Called when the user taps "Do It Later" on the booking card.
  /// Approves/saves the booking without navigating to payment.
  /// Uses "approve" (same as Pay Now) since both need to exit the
  /// BOOKING phase — the only difference is whether we navigate.
  void _onBookingLater(ChatCubit cubit) {
    cubit.sendMessage('approve');
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ChatCubit>();
    final hasBack = widget.activeTripId != null;
    final showSidebarBtn = !hasBack;

    return Scaffold(
      key: widget.scaffoldKey,
      backgroundColor: Colors.white,
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
                        const Center(child: CircularProgressIndicator()),
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
                              padding: const EdgeInsets.all(12),
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

  // ── Sidebar Drawer ───────────────────────────────────────────────────

  Widget _buildSidebar(BuildContext context) {
    return Drawer(
      backgroundColor: Colors.white,
      child: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
              width: double.infinity,
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Color(0xFFF0F0F0)),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Chats',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: Colors.black,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${widget.chatSessions.length} conversations',
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey[500],
                    ),
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        Navigator.pop(context); // close drawer
                        _startNewChat();
                      },
                      icon: const Icon(Icons.add_rounded, size: 18),
                      label: const Text('New Chat'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 12),
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
                  ? const Center(child: CircularProgressIndicator())
                  : widget.chatSessions.isEmpty
                      ? Center(
                          child: Text(
                            'No past chats yet',
                            style: TextStyle(color: Colors.grey[400]),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          itemCount: widget.chatSessions.length,
                          separatorBuilder: (_, _) => const Divider(
                            height: 1,
                            indent: 20,
                            endIndent: 20,
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
        Navigator.pop(context); // close drawer
        _openSession(session);
      },
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                tripInfo != null ? Icons.card_travel : Icons.chat_bubble_outline,
                size: 18,
                color: Colors.grey[700],
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    destination,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (lastMessage != null) ...[
                    const SizedBox(height: 2),
                    Text(
                      lastMessage,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[500],
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[300], size: 16),
          ],
        ),
      ),
    );
  }

  // ── Header ──────────────────────────────────────────────────────────

  Widget _buildHeader(ChatCubit cubit, bool hasBack, bool showSidebarBtn) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(30),
        ),
        child: Row(
          children: [
            if (hasBack)
              GestureDetector(
                onTap: () {
                  if (Navigator.canPop(context)) {
                    Navigator.pop(context);
                  } else {
                    _startNewChat();
                  }
                },
                child: const Padding(
                  padding: EdgeInsets.all(4),
                  child: Icon(Icons.arrow_back_rounded, size: 20),
                ),
              ),
            if (showSidebarBtn)
              GestureDetector(
                onTap: () => widget.scaffoldKey.currentState?.openDrawer(),
                child: const Padding(
                  padding: EdgeInsets.all(4),
                  child: Icon(Icons.menu_rounded, size: 20),
                ),
              ),
            const SizedBox(width: 8),
            const Spacer(),
            Text(
              widget.activeTripId != null ? "Trip Chat" : "✨ TourMate.",
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            const Spacer(),
          ],
        ),
      ),
    );
  }

  Widget _buildError(String msg, ChatCubit cubit) {
    debugPrint('[ChatScreen] _buildError: $msg');
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            const Text("Connection lost",
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(msg, textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey[600])),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () => cubit.reconnect(),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.black,
                foregroundColor: Colors.white,
              ),
              child: const Text("Reconnect"),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return SingleChildScrollView(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 40),
          CircleAvatar(
            radius: 110,
            backgroundImage: const AssetImage("assets/images/Screen1.png"),
            backgroundColor: Colors.transparent,
          ),
          const SizedBox(height: 30),
          const Text(
            "Where to today?",
            style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 10),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 30),
            child: Text(
              "Hey there, I'm here to assist you in planning your experience. Ask me anything travel related.",
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
            ),
          ),
          const SizedBox(height: 24),

        ],
      ),
    );
  }

  Widget _buildInputBar(ChatCubit cubit) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (_selectedImageBytes != null)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey.shade100,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.memory(
                      _selectedImageBytes!,
                      height: 100,
                      width: 100,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: 4,
                    right: 4,
                    child: GestureDetector(
                      onTap: _clearImage,
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: Colors.black54,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.close,
                          color: Colors.white,
                          size: 16,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(30),
              border: Border.all(color: Colors.grey.shade300),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                SizedBox(
                  width: 36,
                  height: 36,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    icon: const Icon(Icons.camera_alt_outlined, size: 22),
                    onPressed: _pickImage,
                  ),
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: TextField(
                    controller: _inputController,
                    maxLines: 3,
                    minLines: 1,
                    textInputAction: TextInputAction.newline,
                    decoration: const InputDecoration(
                      hintText: "Ask anything",
                      border: InputBorder.none,
                      isDense: true,
                      contentPadding: EdgeInsets.symmetric(vertical: 8),
                    ),
                    onSubmitted: (_) => _sendMessage(cubit),
                  ),
                ),
                SizedBox(
                  width: 36,
                  height: 36,
                  child: IconButton(
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(),
                    icon: const Icon(Icons.send, size: 22),
                    onPressed: () => _sendMessage(cubit),
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

/// ================= RECONNECTING BANNER =================
class _ReconnectingBanner extends StatelessWidget {
  const _ReconnectingBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.orange.shade50,
        border: Border(
          bottom: BorderSide(color: Colors.orange.shade200),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: Colors.orange.shade700,
            ),
          ),
          const SizedBox(width: 10),
          Text(
            'Reconnecting...',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Colors.orange.shade800,
            ),
          ),
        ],
      ),
    );
  }
}

/// ================= TYPING INDICATOR =================
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
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(18).copyWith(
            bottomLeft: const Radius.circular(4),
          ),
        ),
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            return Row(
              mainAxisSize: MainAxisSize.min,
              children: List.generate(3, (i) {
                final delay = i * 0.2;
                final value = ((_controller.value - delay) % 1.0);
                final opacity = (value < 0.5)
                    ? (value * 2).clamp(0.3, 1.0)
                    : (1.0 - (value - 0.5) * 2).clamp(0.3, 1.0);
                return Padding(
                  padding: EdgeInsets.only(left: i > 0 ? 5 : 0),
                  child: Opacity(
                    opacity: opacity.toDouble(),
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade500,
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
    );
  }
}
