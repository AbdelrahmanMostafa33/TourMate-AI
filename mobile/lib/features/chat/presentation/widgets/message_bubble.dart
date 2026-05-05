import 'package:flutter/material.dart';
import '../../data/models/chat_message.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage msg;

  const MessageBubble({super.key, required this.msg});

  @override
  Widget build(BuildContext context) {
    final isUser = msg.isUser;

    return Align(
      alignment:
      isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isUser ? Colors.blue : Colors.grey.shade200,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          msg.text,
          style: TextStyle(
            color: isUser ? Colors.white : Colors.black,
          ),
        ),
      ),
    );
  }
}