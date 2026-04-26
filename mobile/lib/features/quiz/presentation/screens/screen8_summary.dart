import 'package:flutter/material.dart';
import '../../data/models/persona_response.dart';
import '../widgets/choice_chip2.dart';
import '../widgets/nav_buttons.dart';

class Screen8Summary extends StatelessWidget {
  final PersonaResponse? persona;
  final VoidCallback onStartChat, onBack;

  const Screen8Summary({
    super.key,
    required this.persona,
    required this.onStartChat,
    required this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    // Fallback if persona is somehow null (shouldn't happen)
    final name = persona?.personaName ?? 'The Open Explorer';
    final bio = persona?.personaBio ?? '';
    final interests = persona?.interests ?? [];
    final questions = persona?.suggestedQuestions ?? [];

    return Scaffold(
      backgroundColor: Colors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Hero banner ──
              Container(
                height: 180,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  gradient: const LinearGradient(
                    colors: [Color(0xFF0D47A1), Color(0xFF1565C0)],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                child: const Center(
                  child: Icon(Icons.nightlife, size: 72, color: Colors.white),
                ),
              ),

              const SizedBox(height: 24),

              // ── Persona name ──
              Text(
                name,
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),

              const SizedBox(height: 16),

              // ── Persona bio ──
              Text(
                bio,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey.shade700,
                  height: 1.5,
                ),
              ),

              // ── Interests ──
              if (interests.isNotEmpty) ...[
                const SizedBox(height: 24),
                const Text(
                  'Interests',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: interests
                      .take(5)
                      .map((i) => ChoiceChip2(
                    label: i,
                    selected: true,
                    onTap: () {},
                  ))
                      .toList(),
                ),
              ],

              // ── Suggested questions ──
              if (questions.isNotEmpty) ...[
                const SizedBox(height: 24),
                const Text(
                  'Try asking…',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 10),
                ...questions.map(
                      (q) => Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '• $q',
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade700,
                      ),
                    ),
                  ),
                ),
              ],

              const SizedBox(height: 32),

              // ── Nav buttons ──
              NavButtons(
                onBack: onBack,
                onNext: onStartChat,
                nextLabel: 'Start chatting',
              ),
            ],
          ),
        ),
      ),
    );
  }
}