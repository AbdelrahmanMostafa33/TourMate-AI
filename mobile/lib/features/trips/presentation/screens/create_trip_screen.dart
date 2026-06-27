import 'package:flutter/material.dart';

class CreateTripScreen extends StatelessWidget {
  const CreateTripScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const _CreateTripView();
  }
}

class _CreateTripView extends StatefulWidget {
  const _CreateTripView();

  @override
  State<_CreateTripView> createState() => _CreateTripViewState();
}

class _CreateTripViewState extends State<_CreateTripView> {
  final _cityController = TextEditingController();
  final _countryController = TextEditingController();
  final _travelersController = TextEditingController();

  DateTime? _startDate;
  DateTime? _endDate;

  /// Canonical interest tags that the AI understands — sourced from
  /// the backend's INTEREST_SYNONYM_MAP in slot_normalizer.py.
  static const _allInterests = [
    "history",
    "architecture",
    "art",
    "museums",
    "food",
    "shopping",
    "nightlife",
    "entertainment",
    "nature",
    "parks",
    "beaches",
    "adventure",
    "sports",
    "water sports",
    "photography",
    "sightseeing",
    "local culture",
    "music",
    "festivals",
    "religion",
    "wine",
    "science",
    "technology",
    "wellness",
    "family",
  ];

  final _selectedInterests = <String>{};

  @override
  void dispose() {
    _cityController.dispose();
    _countryController.dispose();
    _travelersController.dispose();
    super.dispose();
  }

  Future<void> _pickDate({required bool isStart}) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? (_startDate ?? now) : (_endDate ?? now),
      firstDate: now,
      lastDate: DateTime(now.year + 3),
    );
    if (picked == null) return;
    setState(() {
      if (isStart) {
        _startDate = picked;
        if (_endDate != null && _endDate!.isBefore(picked)) _endDate = null;
      } else {
        _endDate = picked;
      }
    });
  }

  String _formatDate(DateTime? date) {
    if (date == null) return "Select date";
    return "${date.day}/${date.month}/${date.year}";
  }

  String _buildAutoMessage() {
    final city = _cityController.text.trim();
    final country = _countryController.text.trim();
    final destination = country.isNotEmpty ? "$city, $country" : city;

    final parts = <String>["I want to plan a trip to $destination."];

    if (_startDate != null && _endDate != null) {
      final start = "${_startDate!.day}/${_startDate!.month}/${_startDate!.year}";
      final end = "${_endDate!.day}/${_endDate!.month}/${_endDate!.year}";
      parts.add("I'll be there from $start to $end.");
    } else if (_startDate != null) {
      final start = "${_startDate!.day}/${_startDate!.month}/${_startDate!.year}";
      parts.add("I'll be arriving on $start.");
    }

    final travelers = int.tryParse(_travelersController.text.trim());
    if (travelers != null && travelers > 0) {
      parts.add("There will be $travelers of us.");
    }

    if (_selectedInterests.isNotEmpty) {
      final sorted = _selectedInterests.toList()..sort();
      parts.add("We're interested in ${sorted.join(', ')}.");
    }

    parts.add("Can you help me plan an itinerary?");
    return parts.join(" ");
  }

  void _submit() {
    final city = _cityController.text.trim();
    if (city.isEmpty) {
      _showSnackbar('City is required');
      return;
    }

    final autoMessage = _buildAutoMessage();

    Navigator.pop(context, autoMessage);
  }

  void _showSnackbar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          leading: const BackButton(),
          title: null,
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 16, top: 8, bottom: 8),
              child: ElevatedButton(
                onPressed: _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                ),
                child: const Text(
                  "Create Trip",
                  style: TextStyle(fontWeight: FontWeight.w500),
                ),
              ),
            ),
          ],
        ),
        body: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 4, 16, 16),
              child: Text(
                "New Trip",
                style: TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    /// ── Destination ──────────────────────────────
                    _sectionLabel("Destination"),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: _field(
                            controller: _cityController,
                            hint: "City",
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _field(
                            controller: _countryController,
                            hint: "Country",
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 24),

                    /// ── Dates ────────────────────────────────────
                    _sectionLabel("Dates"),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: _dateTile(
                            label: "Start",
                            value: _formatDate(_startDate),
                            onTap: () => _pickDate(isStart: true),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _dateTile(
                            label: "End",
                            value: _formatDate(_endDate),
                            onTap: () => _pickDate(isStart: false),
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 24),

                    /// ── Details ──────────────────────────────────
                    _sectionLabel("Details"),
                    const SizedBox(height: 10),
                    _field(
                      controller: _travelersController,
                      hint: "#Travelers",
                      keyboardType: TextInputType.number,
                      prefixIcon: Icons.people_outline,
                    ),
                    const SizedBox(height: 12),
                    _interestsSection(),

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ],
        ),
      );
  }

  Widget _interestsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionLabel("Interests"),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 6,
          children: _allInterests.map((interest) {
            final selected = _selectedInterests.contains(interest);
            return FilterChip(
              label: Text(
                interest,
                style: TextStyle(
                  fontSize: 13,
                  color: selected ? Colors.white : Colors.black87,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
              selected: selected,
              selectedColor: Colors.black,
              checkmarkColor: Colors.white,
              backgroundColor: Colors.grey.shade100,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(20),
                side: BorderSide(
                  color: selected ? Colors.black : Colors.grey.shade300,
                ),
              ),
              onSelected: (value) {
                setState(() {
                  if (value) {
                    _selectedInterests.add(interest);
                  } else {
                    _selectedInterests.remove(interest);
                  }
                });
              },
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _sectionLabel(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.bold,
        color: Colors.grey,
        letterSpacing: 0.8,
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String hint,
    TextInputType keyboardType = TextInputType.text,
    IconData? prefixIcon,
    int maxLines = 1,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      maxLines: maxLines,
      decoration: InputDecoration(
        hintText: hint,
        prefixIcon: prefixIcon != null ? Icon(prefixIcon, size: 20) : null,
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.grey.shade200),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.grey.shade200),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.black, width: 1.5),
        ),
      ),
    );
  }

  Widget _dateTile({
    required String label,
    required String value,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Row(
          children: [
            const Icon(Icons.calendar_today_outlined, size: 18),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontSize: 11,
                      color: Colors.grey,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    value,
                    style: TextStyle(
                      fontSize: 14,
                      color: value == "Select date"
                          ? Colors.grey
                          : Colors.black,
                      fontWeight: value == "Select date"
                          ? FontWeight.normal
                          : FontWeight.w500,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}