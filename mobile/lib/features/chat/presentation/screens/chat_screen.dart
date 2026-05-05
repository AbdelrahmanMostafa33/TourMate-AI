import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/repository/chat_repository.dart';
import '../../logic/chat_cubit.dart';
import '../../logic/chat_state.dart';
import '../widgets/message_bubble.dart';

class ChatScreen extends StatelessWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ChatCubit(locator<ChatRepository>())..connect(),
      child: const _ChatView(),
    );
  }
}

class _ChatView extends StatefulWidget {
  const _ChatView();

  @override
  State<_ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<_ChatView> {
  final controller = TextEditingController();

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ChatCubit>();

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            /// ─── HEADER ─────────────────────────
            const SizedBox(height: 10),
            const Text("✨ TourMate.", style: TextStyle(fontSize: 20)),

            /// ─── CHAT AREA ──────────────────────
            Expanded(
              child: BlocBuilder<ChatCubit, ChatState>(
                builder: (context, state) {
                  return state.maybeWhen(
                    connected: (messages, isTyping) {
                      if (messages.isEmpty) {
                        return _buildEmptyState();
                      }

                      return ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: messages.length,
                        itemBuilder: (_, i) {
                          return MessageBubble(msg: messages[i]);
                        },
                      );
                    },
                    orElse: () => const Center(child: CircularProgressIndicator()),
                  );
                },
              ),
            ),

            /// ─── INPUT BAR ──────────────────────
            _buildInputBar(cubit),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: const [
        Icon(Icons.travel_explore, size: 80),
        SizedBox(height: 10),
        Text("Where to today?", style: TextStyle(fontSize: 22)),
        SizedBox(height: 8),
        Text("Ask me anything travel related"),
      ],
    );
  }

  Widget _buildInputBar(ChatCubit cubit) {
    return Padding(
      padding: const EdgeInsets.all(10),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.camera_alt),
            onPressed: () {},
          ),
          Expanded(
            child: TextField(
              controller: controller,
              decoration: const InputDecoration(
                hintText: "Ask anything...",
                border: OutlineInputBorder(),
              ),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.send),
            onPressed: () {
              print("SENDING...");
              cubit.sendMessage(controller.text);
              controller.clear();
            },
          ),
        ],
      ),
    );
  }
}