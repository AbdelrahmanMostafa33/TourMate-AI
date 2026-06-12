import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../../core/network/service_locator.dart';
import '../../data/models/create_trip_request.dart';
import '../../data/repository/trips_repository.dart';
import '../../logic/trips_cubit.dart';
import '../../logic/trips_state.dart';

class CreateTripScreen extends StatelessWidget {
  const CreateTripScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => TripsCubit(locator<TripsRepository>()),
      child: const _CreateTripView(),
    );
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
  final _budgetController = TextEditingController();
  final _travelersController = TextEditingController();
  final _preferencesController = TextEditingController();

  DateTime? _startDate;
  DateTime? _endDate;

  @override
  void dispose() {
    _cityController.dispose();
    _countryController.dispose();
    _budgetController.dispose();
    _travelersController.dispose();
    _preferencesController.dispose();
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

  void _submit() {
    if (_cityController.text.trim().isEmpty ||
        _countryController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("City and country are required")),
      );
      return;
    }

    final request = CreateTripRequest(
      destinationCity: _cityController.text.trim(),
      destinationCountry: _countryController.text.trim(),
      startDate: _startDate?.toIso8601String(),
      endDate: _endDate?.toIso8601String(),
      budgetTotal: double.tryParse(_budgetController.text.trim()),
      travelerCount: int.tryParse(_travelersController.text.trim()),
      preferences: _preferencesController.text.trim().isEmpty
          ? null
          : _preferencesController.text.trim(),
    );

    context.read<TripsCubit>().createTrip(request);
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<TripsCubit, TripsState>(
      listener: (context, state) {
        state.when(
          initial: () {},
          loading: () {},
          creating: () {},
          created: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text("Trip created!")),
            );
            Navigator.pop(context);
          },
          loaded: (_) {},
          error: (msg) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(msg),
                backgroundColor: Colors.red,
              ),
            );
          },
        );
      },
      child: Scaffold(
        appBar: AppBar(
          leading: const BackButton(),
          title: null,
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 16, top: 8, bottom: 8),
              child: BlocBuilder<TripsCubit, TripsState>(
                builder: (context, state) {
                  final isLoading = state.maybeWhen(creating: () => true, orElse: () => false);
                  return ElevatedButton(
                    onPressed: isLoading ? null : _submit,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.black,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                    ),
                    child: isLoading
                        ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        color: Colors.white,
                        strokeWidth: 2,
                      ),
                    )
                        : const Text(
                      "Create Trip",
                      style: TextStyle(fontWeight: FontWeight.w500),
                    ),
                  );
                },
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
                    Row(
                      children: [
                        Expanded(
                          child: _field(
                            controller: _budgetController,
                            hint: "Budget (\$)",
                            keyboardType: TextInputType.number,
                            prefixIcon: Icons.attach_money,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _field(
                            controller: _travelersController,
                            hint: "#Travelers",
                            keyboardType: TextInputType.number,
                            prefixIcon: Icons.people_outline,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 24),

                    /// ── Preferences ──────────────────────────────
                    _sectionLabel("Preferences"),
                    const SizedBox(height: 10),
                    _field(
                      controller: _preferencesController,
                      hint: "e.g. beach, culture, food, adventure...",
                      maxLines: 4,
                    ),

                    const SizedBox(height: 32),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
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