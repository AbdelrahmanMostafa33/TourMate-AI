import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/network/api_services.dart';
import '../../data/models/chat_session_response.dart';
import '../../data/repository/chat_repository.dart';
import '../../logic/chat_cubit.dart';
import '../../logic/chat_state.dart';
import '../widgets/message_bubble.dart';
import '../widgets/pipeline_progress_widget.dart';

class ChatScreen extends StatefulWidget {
  final VoidCallback? onTripCreated;
  final String? initialTripId;

  const ChatScreen({
    super.key,
    this.onTripCreated,
    this.initialTripId,
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

  void _openChatSession(ChatSessionResponse session) {
    final tripInfo = session.trip;
    if (tripInfo != null) {
      Navigator.pushReplacementNamed(
        context,
        '/chat',
        arguments: {'trip_id': tripInfo.tripId},
      );
    }
  }

  void _startNewChat() {
    Navigator.pushReplacementNamed(context, '/chat');
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) {
        final cubit = ChatCubit(locator<ChatRepository>());
        if (_activeTripId != null) {
          cubit.connectToTrip(_activeTripId!, autoMsg: null);
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
        onOpenSession: _openChatSession,
        onStartNewChat: _startNewChat,
        onRefreshSessions: _fetchChatSessions,
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
  final void Function(ChatSessionResponse) onOpenSession;
  final VoidCallback onStartNewChat;
  final VoidCallback onRefreshSessions;

  const _ChatView({
    required this.scaffoldKey,
    required this.chatSessions,
    required this.loadingSessions,
    this.activeTripId,
    required this.onOpenSession,
    required this.onStartNewChat,
    required this.onRefreshSessions,
  });

  @override
  State<_ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<_ChatView> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  int _lastMessageCount = 0;

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

  void _sendMessage(ChatCubit cubit) {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;
    cubit.sendMessage(text);
    _inputController.clear();
    _scrollToBottom();
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
                        return widget.chatSessions.isNotEmpty
                            ? _buildHistoryBody()
                            : _buildEmptyState();
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
                                return MessageBubble(msg: messages[i]);
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
                        widget.onStartNewChat();
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
        widget.onOpenSession(session);
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
                onTap: () => Navigator.pop(context),
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
            // Refresh button to reload sidebar sessions
            if (showSidebarBtn)
              GestureDetector(
                onTap: widget.onRefreshSessions,
                child: Padding(
                  padding: const EdgeInsets.all(4),
                  child: Icon(Icons.refresh_rounded, size: 18, color: Colors.grey[700]),
                ),
              ),
          ],
        ),
      ),
    );
  }

  // ── History body (shown when on main chat and sessions exist) ──────

  Widget _buildHistoryBody() {
    if (widget.loadingSessions) {
      return const Center(child: CircularProgressIndicator());
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
          child: Row(
            children: [
              const Text(
                "Recent Chats",
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const Spacer(),
              TextButton.icon(
                onPressed: widget.onStartNewChat,
                icon: const Icon(Icons.add_circle_outline, size: 18),
                label: const Text("New Chat"),
                style: TextButton.styleFrom(foregroundColor: Colors.black),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: widget.chatSessions.isEmpty
              ? _buildEmptyState()
              : ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: widget.chatSessions.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 8),
                  itemBuilder: (_, i) => _buildSessionCard(widget.chatSessions[i]),
                ),
        ),
      ],
    );
  }

  Widget _buildSessionCard(ChatSessionResponse session) {
    final tripInfo = session.trip;
    final destination = tripInfo?.destination ?? 'Chat';
    final status = tripInfo?.status;
    final lastMessage = session.lastMessage;

    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => widget.onOpenSession(session),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.grey.shade200),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  tripInfo != null ? Icons.card_travel : Icons.chat_bubble_outline,
                  size: 20,
                  color: Colors.grey[700],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      destination,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                    ),
                    if (lastMessage != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        lastMessage,
                        style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    if (status != null) ...[
                      const SizedBox(height: 2),
                      Text(
                        status.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          color: Colors.grey[400],
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: Colors.grey[300], size: 18),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildError(String msg, ChatCubit cubit) {
    print('[ChatScreen] _buildError: $msg');
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
          if (widget.chatSessions.isNotEmpty)
            Text(
              "Or pick up where you left off",
              style: TextStyle(fontSize: 13, color: Colors.grey[400]),
            ),
        ],
      ),
    );
  }

  Widget _buildInputBar(ChatCubit cubit) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10),
        decoration: BoxDecoration(
          color: Colors.grey.shade100,
          borderRadius: BorderRadius.circular(30),
          border: Border.all(color: Colors.grey.shade300),
        ),
        child: Row(
          children: [
            const Icon(Icons.camera_alt_outlined),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: _inputController,
                decoration: const InputDecoration(
                  hintText: "Ask anything",
                  border: InputBorder.none,
                ),
                onSubmitted: (_) => _sendMessage(cubit),
              ),
            ),
            IconButton(
              icon: const Icon(Icons.send),
              onPressed: () => _sendMessage(cubit),
            ),
          ],
        ),
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
