import 'package:flutter/material.dart';
import '../../data/models/chat_message.dart';
import 'itinerary_card.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage msg;

  const MessageBubble({super.key, required this.msg});

  @override
  Widget build(BuildContext context) {
    if (msg.itinerary != null) {
      return Align(
        alignment: Alignment.centerLeft,
        child: ItineraryCard(itinerary: msg.itinerary!),
      );
    }

    final isUser = msg.isUser;

    return Column(
      crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        // Display image above the message bubble
        if (msg.imageBytes != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.memory(
                msg.imageBytes!,
                width: 200,
                fit: BoxFit.cover,
              ),
            ),
          ),
        // Message bubble
        if (msg.text.isNotEmpty || msg.isStreaming)
          Align(
            alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 4),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              decoration: BoxDecoration(
                color: isUser ? Colors.black : Colors.grey.shade100,
                borderRadius: BorderRadius.circular(18).copyWith(
                  bottomRight: isUser ? const Radius.circular(4) : null,
                  bottomLeft: !isUser ? const Radius.circular(4) : null,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (msg.text.isNotEmpty)
                    Text(
                      msg.text,
                      style: TextStyle(
                        color: isUser ? Colors.white : Colors.black,
                        fontSize: 15,
                        height: 1.3,
                      ),
                    ),
                  if (msg.isStreaming)
                    const Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.grey,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}