import 'package:flutter/material.dart';
import '../../data/models/quiz_answers.dart';
import '../widgets/nav_buttons.dart';
import '../widgets/quiz_scaffold.dart';
import '../widgets/save_exit_button.dart';

class Screen3Accommodation extends StatefulWidget {
  final QuizAnswers answers;
  final VoidCallback onNext, onBack;
  final Future<void> Function() onSaveExit;

  const Screen3Accommodation({
    super.key,
    required this.answers,
    required this.onNext,
    required this.onBack,
    required this.onSaveExit,
  });

  @override
  State<Screen3Accommodation> createState() => _Screen3AccommodationState();
}

class _Screen3AccommodationState extends State<Screen3Accommodation> {
  final List<String> _selected = [];
  final List<String> _customOptions = [];

  final List<Map<String, dynamic>> _options = [
    {'label': 'Luxury Hotels', 'icon': Icons.hotel},
    {'label': 'Boutique', 'icon': Icons.house},
    {'label': 'Bed & Breakfast', 'icon': Icons.breakfast_dining},
    {'label': 'Budget-Friendly Hotels', 'icon': Icons.savings},
    {'label': 'Hostels', 'icon': Icons.bed},
    {'label': 'Camping Grounds', 'icon': Icons.forest},
    {'label': 'Eco-lodges', 'icon': Icons.eco},
    {'label': 'Inns', 'icon': Icons.local_hotel},
    {'label': 'Resorts', 'icon': Icons.beach_access},
    {'label': 'Motels', 'icon': Icons.directions_car},
    {'label': 'Vacation Rentals', 'icon': Icons.home},
  ];

  @override
  void initState() {
    super.initState();
    _selected.addAll(widget.answers.accommodationStyles);
  }

  void _toggle(String value) {
    setState(() {
      _selected.contains(value)
          ? _selected.remove(value)
          : _selected.add(value);
    });
  }

  void _showAddCustomOptionDialog() {
    final controller = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Add your own"),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: "Enter accommodation type",
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Cancel"),
          ),
          ElevatedButton(
            onPressed: () {
              final value = controller.text.trim();

              final exists =
                  _selected.contains(value) ||
                  _options.any((e) => e['label'] == value) ||
                  _customOptions.contains(value);

              if (value.isNotEmpty && !exists) {
                setState(() {
                  _customOptions.add(value);
                  _selected.add(value);
                });
              }

              Navigator.pop(context);
            },
            child: const Text("Add"),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final allOptions = [
      ..._options,
      ..._customOptions.map((e) => {'label': e, 'icon': Icons.home}),
    ];

    return QuizScaffold(
      heroImageUrl: 'assets/images/Screen3.png',
      body: SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 24),
            child: Column(
              mainAxisSize: MainAxisSize.min, // ✅ important fix
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Text(
                          "What's your usual accommodation style?",
                          style: TextStyle(
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      SaveExitButton(onTap: widget.onSaveExit),
                    ],
                  ),
                ),

                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 6, 24, 0),
                  child: Text(
                    'Select all that apply or add your own.',
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ),

                const SizedBox(height: 16),

                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: [
                      ...allOptions.map((o) {
                        final lbl = o['label'] as String;
                        final ico = o['icon'] as IconData;
                        final sel = _selected.contains(lbl);

                        return GestureDetector(
                          onTap: () => _toggle(lbl),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 180),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 10,
                            ),
                            decoration: BoxDecoration(
                              color: sel ? Colors.black : Colors.white,
                              border: Border.all(
                                color: sel
                                    ? Colors.black
                                    : Colors.grey.shade300,
                              ),
                              borderRadius: BorderRadius.circular(24),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  ico,
                                  size: 16,
                                  color: sel
                                      ? Colors.white
                                      : Colors.black54,
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  lbl,
                                  style: TextStyle(
                                    fontSize: 13,
                                    color: sel
                                        ? Colors.white
                                        : Colors.black87,
                                    fontWeight: sel
                                        ? FontWeight.w600
                                        : FontWeight.normal,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),

                      GestureDetector(
                        onTap: _showAddCustomOptionDialog,
                        child: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 14,
                            vertical: 10,
                          ),
                          decoration: BoxDecoration(
                            border: Border.all(color: Colors.grey.shade300),
                            borderRadius: BorderRadius.circular(24),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.add,
                                  size: 16, color: Colors.black54),
                              SizedBox(width: 6),
                              Text(
                                'Add your own',
                                style: TextStyle(fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),

                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: NavButtons(
                    onBack: widget.onBack,
                    onNext: () {
                      widget.answers.accommodationStyles = _selected;
                      widget.onNext();
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}