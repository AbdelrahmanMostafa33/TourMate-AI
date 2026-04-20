import 'package:flutter/material.dart';
import 'package:tourmate/features/quiz/presentation/widgets/quiz_scaffold.dart';
import '../../data/models/quiz_answers.dart';

class Screen1Basics extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext;

  const Screen1Basics({
    super.key,
    required this.answers,
    required this.onNext,
  });

  @override
  State<Screen1Basics> createState() => _Screen1BasicsState();
}

class _Screen1BasicsState extends State<Screen1Basics> {
  final _ageCtrl = TextEditingController();
  final _locationCtrl = TextEditingController();

  String _sex = '';
  String _travelCompanion = '';

  final _companions = ['Solo', 'Couple', 'Family', 'Friends', 'Group'];

  @override
  void initState() {
    super.initState();
    _ageCtrl.text =
        widget.answers.age == 0 ? '' : widget.answers.age.toString();
    _locationCtrl.text = widget.answers.location;
    _sex = widget.answers.sex;
    _travelCompanion = widget.answers.travelCompanion;
  }

  @override
  void dispose() {
    _ageCtrl.dispose();
    _locationCtrl.dispose();
    super.dispose();
  }

  void _save() {
    widget.answers.age = int.tryParse(_ageCtrl.text.trim()) ?? 0;
    widget.answers.sex = _sex;
    widget.answers.location = _locationCtrl.text.trim();
    widget.answers.travelCompanion = _travelCompanion;
    widget.onNext();
  }

  @override
  Widget build(BuildContext context) {
    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen1.png',
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 28),
              const Text(
                "Let's start with the basics.",
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              const Text('Tell us about yourself.',
                  style: TextStyle(fontSize: 14, color: Colors.black)),
              const SizedBox(height: 18),
              _buildLabel('Age'),
              const SizedBox(height: 6),
              _buildTextField(_ageCtrl,
                  hint: 'e.g. 22',
                  keyboardType: TextInputType.number),
              const SizedBox(height: 18),
              _buildLabel('Sex'),
              const SizedBox(height: 10),
              Wrap(
                spacing: 10,
                children: ['Male', 'Female', 'Other'].map((option) {
                  final isSelected = _sex == option;
                  return GestureDetector(
                    onTap: () => setState(() => _sex = option),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                      decoration: BoxDecoration(
                        color:
                            isSelected ? Colors.black : Colors.white,
                        border: Border.all(
                          color: isSelected
                              ? Colors.black
                              : Colors.grey.shade300,
                        ),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Text(
                        option,
                        style: TextStyle(
                          color: isSelected
                              ? Colors.white
                              : Colors.black,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.normal,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 18),
              _buildLabel('Location'),
              const SizedBox(height: 6),
              _buildTextField(_locationCtrl, hint: 'e.g. Cairo, Egypt'),
              const SizedBox(height: 18),
              _buildLabel('Who do you usually travel with?'),
              const SizedBox(height: 10),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: _companions.map((c) {
                  final isSelected = _travelCompanion == c;
                  return GestureDetector(
                    onTap: () => setState(() => _travelCompanion = c),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      padding: const EdgeInsets.symmetric(
                          horizontal: 20, vertical: 10),
                      decoration: BoxDecoration(
                        color:
                            isSelected ? Colors.black : Colors.white,
                        border: Border.all(
                          color: isSelected
                              ? Colors.black
                              : Colors.grey.shade300,
                        ),
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Text(
                        c,
                        style: TextStyle(
                          color: isSelected
                              ? Colors.white
                              : Colors.black,
                          fontWeight: isSelected
                              ? FontWeight.w600
                              : FontWeight.normal,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 36),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _save,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.black,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(30),
                    ),
                  ),
                  child: const Text(
                    'Next',
                    style: TextStyle(
                        fontSize: 16, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLabel(String text) {
    return Text(text,
        style: const TextStyle(
            fontSize: 14, fontWeight: FontWeight.w600));
  }

  Widget _buildTextField(
    TextEditingController controller, {
    String? hint,
    TextInputType? keyboardType,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(color: Colors.grey.shade400),
        contentPadding: const EdgeInsets.symmetric(
            horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: Colors.black),
        ),
      ),
    );
  }
}