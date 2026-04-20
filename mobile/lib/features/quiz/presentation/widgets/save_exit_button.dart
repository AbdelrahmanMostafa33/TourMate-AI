import 'package:flutter/material.dart';

class SaveExitButton extends StatelessWidget {
  final VoidCallback onTap;
  const SaveExitButton({super.key, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.black,
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text('Save and Exit',
            style: TextStyle(color: Colors.white, fontSize: 12)),
      ),
    );
  }
}