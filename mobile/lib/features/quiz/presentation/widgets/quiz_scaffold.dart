import 'package:flutter/material.dart';

class QuizScaffold extends StatelessWidget {
  final Widget body;
  final String? heroImageUrl;
  final Color? bgColor;

  const QuizScaffold({
    super.key,
    required this.body,
    this.heroImageUrl,
    this.bgColor,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: bgColor ?? Colors.white,
      body: SafeArea(
        child: heroImageUrl != null
            ? Column(
                children: [
                  SizedBox(
                    height: 200,
                    width: double.infinity,
                    child: Image.asset(
                      heroImageUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: const Color(0xFF2C3E50),
                        child: const Icon(Icons.landscape, size: 60, color: Colors.white54),
                      ),
                    ),
                  ),
                  Expanded(
                    child: SingleChildScrollView(
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          minHeight: MediaQuery.of(context).size.height - 200,
                        ),
                        child: body,
                      ),
                    ),
                  ),
                ],
              )
            : SingleChildScrollView(child: body),
      ),
    );
  }
}