import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../../app/app_theme.dart';
import '../../../../core/theme/design_tokens.dart';

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
  TourMateColors get _tm => context.tm;
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
      backgroundColor: _tm.nearWhite,
      appBar: AppBar(
        backgroundColor: _tm.brandWhite,
        surfaceTintColor: _tm.brandWhite,
        leading: IconButton(
          icon: Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: _tm.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: _tm.borderLight),
            ),
            child: Icon(Icons.arrow_back_rounded, color: _tm.textPrimary, size: 18),
          ),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'New Trip',
          style: GoogleFonts.inter(fontSize: 18, fontWeight: FontWeight.w700, color: _tm.textPrimary, letterSpacing: -0.3),
        ),
        centerTitle: true,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(color: _tm.divider, height: 0.5),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: Spacing.xl3, top: 8, bottom: 8),
            child: SizedBox(
              height: 38,
              child: ElevatedButton.icon(
                onPressed: _submit,
                icon: Icon(Icons.auto_awesome, size: 14, color: _tm.sapphireLight),
                label: Text(
                  'Create Trip',
                  style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: _tm.brandWhite),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _tm.deepNavy,
                  foregroundColor: _tm.brandWhite,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(RadiusTokens.lg),
                    side: BorderSide(color: _tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                  ),
                  shadowColor: Colors.transparent,
                ),
              ),
            ),
          ),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xl3, Spacing.xl3, Spacing.xl5),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  /// ── Destination ──────────────────────────────
                  _sectionLabel("Destination"),
                  const SizedBox(height: Spacing.lg),
                  Row(
                    children: [
                      Expanded(
                        child: _field(
                          controller: _cityController,
                          hint: "City",
                          prefixIcon: Icons.location_city_outlined,
                        ),
                      ),
                      const SizedBox(width: Spacing.xl),
                      Expanded(
                        child: _field(
                          controller: _countryController,
                          hint: "Country",
                          prefixIcon: Icons.public_outlined,
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: Spacing.xl5),

                  /// ── Dates ────────────────────────────────────
                  _sectionLabel("Dates"),
                  const SizedBox(height: Spacing.lg),
                  Row(
                    children: [
                      Expanded(
                        child: _dateTile(
                          label: "Start",
                          value: _formatDate(_startDate),
                          onTap: () => _pickDate(isStart: true),
                        ),
                      ),
                      const SizedBox(width: Spacing.xl),
                      Expanded(
                        child: _dateTile(
                          label: "End",
                          value: _formatDate(_endDate),
                          onTap: () => _pickDate(isStart: false),
                        ),
                      ),
                    ],
                  ),

                  const SizedBox(height: Spacing.xl5),

                  /// ── Details ──────────────────────────────────
                  _sectionLabel("Details"),
                  const SizedBox(height: Spacing.lg),
                  _field(
                    controller: _travelersController,
                    hint: "Number of travelers",
                    keyboardType: TextInputType.number,
                    prefixIcon: Icons.people_outline,
                  ),
                  const SizedBox(height: Spacing.xl3),
                  _interestsSection(),

                  const SizedBox(height: Spacing.xl7),

                  // Submit button
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      onPressed: _submit,
                      icon: Icon(Icons.auto_awesome, size: 18, color: _tm.sapphireLight),
                      label: Text(
                        'Start Planning',
                        style: GoogleFonts.inter(fontSize: 15, fontWeight: FontWeight.w600, color: _tm.brandWhite),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _tm.deepNavy,
                        foregroundColor: _tm.brandWhite,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
                          side: BorderSide(color: _tm.sapphire.withValues(alpha: 0.3), width: 0.5),
                        ),
                        shadowColor: Colors.transparent,
                      ),
                    ),
                  ),
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
        const SizedBox(height: Spacing.lg),
        Wrap(
          spacing: Spacing.md,
          runSpacing: Spacing.sm,
          children: _allInterests.map((interest) {
            final selected = _selectedInterests.contains(interest);
            return FilterChip(
              label: Text(
                interest,
                style: TextStyle(
                  fontSize: 13,
                  color: selected ? _tm.brandWhite : _tm.textPrimary,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
              selected: selected,
              selectedColor: _tm.deepNavy,
              checkmarkColor: _tm.brandWhite,
              backgroundColor: _tm.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(RadiusTokens.full),
                side: BorderSide(
                  color: selected ? _tm.sapphire.withValues(alpha: 0.3) : _tm.border,
                  width: selected ? 1.5 : 1.0,
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
    return Row(
      children: [
        Container(
          width: 3,
          height: 14,
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF2563EB), Color(0xFFDBEAFE)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
            borderRadius: BorderRadius.circular(RadiusTokens.xxs),
          ),
        ),
        const SizedBox(width: Spacing.md),
        Text(
          text.toUpperCase(),
          style: GoogleFonts.inter(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
            color: _tm.textTertiary,
          ),
        ),
      ],
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
        prefixIcon: prefixIcon != null
            ? Container(
                margin: const EdgeInsets.only(left: 12, right: 8),
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: _tm.sapphire.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(RadiusTokens.md),
                ),
                child: Icon(prefixIcon, size: 18, color: _tm.sapphire),
              )
            : null,
        filled: true,
        fillColor: _tm.brandWhite,
        contentPadding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          borderSide: BorderSide(color: _tm.borderLight),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          borderSide: BorderSide(color: _tm.borderLight),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          borderSide: BorderSide(color: _tm.deepNavy, width: 1.5),
        ),
      ),
      style: GoogleFonts.inter(fontSize: 15, color: _tm.textPrimary),
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
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl3, vertical: Spacing.xl2),
        decoration: BoxDecoration(
          color: _tm.brandWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl),
          border: Border.all(color: _tm.borderLight),
          boxShadow: [
            BoxShadow(
              color: _tm.deepNavy.withValues(alpha: 0.03),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: _tm.sapphire.withValues(alpha: 0.06),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(Icons.calendar_today_outlined, size: 16, color: _tm.sapphire),
            ),
            const SizedBox(width: Spacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: GoogleFonts.inter(
                      fontSize: 10,
                      color: _tm.textTertiary,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(height: Spacing.xxs),
                  Text(
                    value,
                    style: GoogleFonts.inter(
                      fontSize: 14,
                      color: value == "Select date"
                          ? _tm.textTertiary
                          : _tm.textPrimary,
                      fontWeight: value == "Select date"
                          ? FontWeight.w400
                          : FontWeight.w600,
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