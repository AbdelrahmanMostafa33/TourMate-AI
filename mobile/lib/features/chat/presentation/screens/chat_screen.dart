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
      backgroundColor: Colors.white,
      body: SafeArea(
        child: Column(
          children: [
            /// ================= HEADER =================
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Row(
                  children: [
                    const Spacer(),
                    const Text(
                      "✨ TourMate.",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const Spacer(),
                  ],
                ),
              ),
            ),

            /// ================= CHAT AREA =================
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
                    orElse: () =>
                    const Center(child: CircularProgressIndicator()),
                  );
                },
              ),
            ),

            /// ================= INPUT BAR =================
            _buildInputBar(cubit),

            /// ================= BOTTOM NAV =================
          ],
        ),
      ),
    );
  }

  /// ================= EMPTY STATE =================
  Widget _buildEmptyState() {
    return SingleChildScrollView(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const SizedBox(height: 40),

          /// IMAGE
          CircleAvatar(
            radius: 110,
            backgroundImage: const AssetImage("assets/images/Screen1.png"),
            backgroundColor: Colors.transparent,
          ),

          const SizedBox(height: 30),

          /// TITLE
          const Text(
            "Where to today?",
            style: TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.bold,
            ),
          ),

          const SizedBox(height: 10),

          /// SUBTEXT
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 30),
            child: Text(
              "Hey there, I'm here to assist you in planning your experience. Ask me anything travel related.",
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.grey.shade600,
                fontSize: 14,
              ),
            ),
          ),

          const SizedBox(height: 20),

          /// BUTTON
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.grey.shade200,
              borderRadius: BorderRadius.circular(25),
            ),
            child: const Text(
              "What can I ask Tour Mate?",
              style: TextStyle(fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }

  /// ================= INPUT BAR =================
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
                controller: controller,
                decoration: const InputDecoration(
                  hintText: "Ask anything",
                  border: InputBorder.none,
                ),
              ),
            ),

            IconButton(
              icon: const Icon(Icons.send),
              onPressed: () {
                cubit.sendMessage(controller.text);
                controller.clear();
              },
            ),
          ],
        ),
      ),
    );
  }

}