import 'package:flutter/material.dart';
import '../utils/countries_cities.dart';

/// A two-step dropdown picker that first lets the user select a country,
/// then a city within that country.
///
/// Useful for "Home City" fields in sign-up and profile editing screens.
class CityPicker extends StatefulWidget {
  /// Initial value as "City, Country" or just "City".
  final String? initialValue;

  /// Called when the user selects a city (full string like "Cairo, Egypt").
  final ValueChanged<String> onCitySelected;

  const CityPicker({
    super.key,
    this.initialValue,
    required this.onCitySelected,
  });

  @override
  State<CityPicker> createState() => _CityPickerState();
}

class _CityPickerState extends State<CityPicker> {
  String? _selectedCountry;
  String? _selectedCity;
  final List<String> _countries = CountriesCities.countries;

  @override
  void initState() {
    super.initState();
    if (widget.initialValue != null && widget.initialValue!.isNotEmpty) {
      final (country, city) = CountriesCities.parse(widget.initialValue);
      if (country != null && city != null) {
        _selectedCountry = country;
        _selectedCity = city;
      } else {
        // Try to use the initial value as a city name
        _selectedCity = widget.initialValue;
      }
    }
  }

  void _onCountryChanged(String? country) {
    setState(() {
      _selectedCountry = country;
      _selectedCity = null;
    });
  }

  void _onCityChanged(String? city) {
    setState(() {
      _selectedCity = city;
    });
    if (_selectedCountry != null && city != null) {
      widget.onCitySelected('$city, $_selectedCountry');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Country Dropdown ──────────────────────────────
        _buildLabel('Country'),
        const SizedBox(height: 6),
        _buildCountryDropdown(),
        const SizedBox(height: 14),

        // ── City Dropdown (only shows after country is selected) ──
        if (_selectedCountry != null) ...[
          _buildLabel('City'),
          const SizedBox(height: 6),
          _buildCityDropdown(),
        ],
      ],
    );
  }

  Widget _buildLabel(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: Colors.black87,
      ),
    );
  }

  Widget _buildCountryDropdown() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedCountry,
          isExpanded: true,
          hint: Text(
            'Select your country',
            style: TextStyle(color: Colors.grey.shade400, fontSize: 14),
          ),
          icon: Icon(Icons.expand_more, color: Colors.grey.shade500),
          style: const TextStyle(
            fontSize: 14,
            color: Colors.black87,
            fontWeight: FontWeight.w500,
          ),
          items: _countries.map((country) {
            return DropdownMenuItem(
              value: country,
              child: Row(
                children: [
                  Icon(Icons.public_outlined,
                      size: 18, color: Colors.grey.shade500),
                  const SizedBox(width: 10),
                  Text(country),
                ],
              ),
            );
          }).toList(),
          onChanged: _onCountryChanged,
        ),
      ),
    );
  }

  Widget _buildCityDropdown() {
    final cities = CountriesCities.citiesFor(_selectedCountry!);
    return Container(
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.grey.shade300),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedCity,
          isExpanded: true,
          hint: Text(
            'Select your city',
            style: TextStyle(color: Colors.grey.shade400, fontSize: 14),
          ),
          icon: Icon(Icons.expand_more, color: Colors.grey.shade500),
          style: const TextStyle(
            fontSize: 14,
            color: Colors.black87,
            fontWeight: FontWeight.w500,
          ),
          items: cities.map((city) {
            return DropdownMenuItem(
              value: city,
              child: Row(
                children: [
                  Icon(Icons.location_city_outlined,
                      size: 18, color: Colors.grey.shade500),
                  const SizedBox(width: 10),
                  Text(city),
                ],
              ),
            );
          }).toList(),
          onChanged: _onCityChanged,
        ),
      ),
    );
  }
}
