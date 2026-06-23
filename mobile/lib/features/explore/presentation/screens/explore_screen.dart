import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../data/models/place_model.dart';
import '../../logic/explore_cubit.dart';
import '../../logic/explore_state.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key});

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  @override
  void initState() {
    super.initState();
    final cubit = context.read<ExploreCubit>();
    Future.microtask(() => cubit.init());
  }

  @override
  Widget build(BuildContext context) {
    final cubit = context.read<ExploreCubit>();

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text(
          'Explore',
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: Colors.black,
          ),
        ),
        centerTitle: false,
      ),
      body: BlocBuilder<ExploreCubit, ExploreState>(
        builder: (context, state) {
          return state.when(
            initial: () => const SizedBox(),
            loading: () => const Center(
              child: CircularProgressIndicator(color: Colors.black),
            ),
            loaded: (
              places,
              total,
              isLoadingMore,
              selectedCity,
              selectedCategory,
              savedPlaceIds,
            ) {
              return RefreshIndicator(
                color: Colors.black,
                onRefresh: () => cubit.setCity(selectedCity),
                child: CustomScrollView(
                  slivers: [
                    // ── Filter bar ────────────────────────────
                    SliverToBoxAdapter(child: _FilterBar(
                      cities: cubit.availableCities,
                      selectedCity: selectedCity,
                      selectedCategory: selectedCategory,
                      onCityChanged: (city) => cubit.setCity(city),
                      onCategoryChanged: (cat) => cubit.setCategory(cat),
                    )),

                    // ── Results count ─────────────────────────
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                        child: Text(
                          total > 0
                              ? '$total place${total > 1 ? 's' : ''} found'
                              : 'No places found',
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey[500],
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                    ),

                    // ── Place cards ──────────────────────────
                    if (places.isEmpty)
                      const SliverFillRemaining(
                        child: Center(child: Text('No places match your filters')),
                      )
                    else
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                        sliver: SliverList(
                          delegate: SliverChildBuilderDelegate(
                            (context, index) => _PlaceCard(
                              place: places[index],
                              isSaved: savedPlaceIds.contains(places[index].placeId),
                              onToggleSave: () => cubit.toggleSave(places[index].placeId),
                            ),
                            childCount: places.length,
                          ),
                        ),
                      ),
                  ],
                ),
              );
            },
            error: (message) => Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.cloud_off, size: 64, color: Colors.grey[300]),
                    const SizedBox(height: 16),
                    Text(
                      "Couldn't load places",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey[800],
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      message,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.grey[600], fontSize: 13),
                    ),
                    const SizedBox(height: 24),
                    ElevatedButton(
                      onPressed: () => cubit.init(),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.black,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 12,
                        ),
                      ),
                      child: const Text('Try Again'),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

// ── Filter Bar ─────────────────────────────────────────────────────────────

class _FilterBar extends StatelessWidget {
  final List<String> cities;
  final String? selectedCity;
  final String? selectedCategory;
  final ValueChanged<String?> onCityChanged;
  final ValueChanged<String?> onCategoryChanged;

  const _FilterBar({
    required this.cities,
    required this.selectedCity,
    required this.selectedCategory,
    required this.onCityChanged,
    required this.onCategoryChanged,
  });

  static const _categories = ['All', 'Attraction', 'Restaurant', 'Hotel'];

  String? _categoryToParam(String label) {
    switch (label.toLowerCase()) {
      case 'all':
        return null;
      case 'attraction':
        return 'attraction';
      case 'restaurant':
        return 'restaurant';
      case 'hotel':
        return 'hotel';
      default:
        return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── City dropdown ───────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            decoration: BoxDecoration(
              color: Colors.grey.shade50,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.grey.shade200),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String?>(
                value: selectedCity,
                isExpanded: true,
                hint: Text(
                  '📍  All cities',
                  style: TextStyle(color: Colors.grey[600], fontSize: 14),
                ),
                icon: Icon(Icons.expand_more, color: Colors.grey[600]),
                items: [
                  DropdownMenuItem<String?>(
                    value: null,
                    child: Text('📍  All cities',
                        style: TextStyle(color: Colors.grey[700], fontSize: 14)),
                  ),
                  ...cities.map((city) => DropdownMenuItem<String?>(
                        value: city,
                        child: Text('📍  $city',
                            style: const TextStyle(
                                color: Colors.black87, fontSize: 14)),
                      )),
                ],
                onChanged: onCityChanged,
              ),
            ),
          ),

          const SizedBox(height: 12),

          // ── Category chips ────────────────────────────────
          SizedBox(
            height: 36,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: _categories.map((label) {
                final param = _categoryToParam(label);
                final isSelected = selectedCategory == param;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: GestureDetector(
                    onTap: () => onCategoryChanged(param),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      decoration: BoxDecoration(
                        color: isSelected ? Colors.black : Colors.grey.shade100,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        label,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight:
                              isSelected ? FontWeight.w600 : FontWeight.w500,
                          color:
                              isSelected ? Colors.white : Colors.grey[700],
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Place Card ────────────────────────────────────────────────────────────

class _PlaceCard extends StatelessWidget {
  final PlaceModel place;
  final bool isSaved;
  final VoidCallback onToggleSave;

  const _PlaceCard({
    required this.place,
    required this.isSaved,
    required this.onToggleSave,
  });

  String get _categoryLabel {
    switch (place.category.toLowerCase()) {
      case 'hotel':
        return 'Hotel';
      case 'restaurant':
        return 'Restaurant';
      case 'attraction':
        return 'Attraction';
      default:
        return place.category.isEmpty ? 'Place' : place.category;
    }
  }

  Color get _categoryColor {
    switch (place.category.toLowerCase()) {
      case 'hotel':
        return const Color(0xFF2D3436);
      case 'restaurant':
        return const Color(0xFF636E72);
      case 'attraction':
        return const Color(0xFF0984E3);
      default:
        return Colors.grey;
    }
  }

  String get _ratingText {
    if (place.rating == 0) return '';
    return place.rating.toStringAsFixed(1);
  }

  String get _descriptionSnippet {
    final desc = place.description;
    if (desc == null || desc.isEmpty) return '';
    if (desc.length <= 120) return desc;
    return '${desc.substring(0, 117)}...';
  }

  String get _locationText {
    final parts = <String>[];
    if (place.city != null && place.city!.isNotEmpty) parts.add(place.city!);
    if (place.country != null && place.country!.isNotEmpty) {
      parts.add(place.country!);
    }
    return parts.join(', ');
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        elevation: 0,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () {
            if (place.placeId.isNotEmpty) {
              Navigator.pushNamed(
                context,
                '/place-detail',
                arguments: place.placeId,
              );
            }
          },
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.grey.shade200),
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Photo with heart overlay ──────────────────
                if (place.hasPhoto)
                  SizedBox(
                    height: 180,
                    width: double.infinity,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        Image.network(
                          place.firstPhoto,
                          fit: BoxFit.cover,
                          loadingBuilder: (_, child, progress) {
                            if (progress == null) return child;
                            return Container(
                              color: Colors.grey[100],
                              child: const Center(
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: Colors.black26,
                                ),
                              ),
                            );
                          },
                          errorBuilder: (_, _, _) => Container(
                            color: Colors.grey[100],
                            child: Icon(Icons.image,
                                color: Colors.grey[300], size: 48),
                          ),
                        ),
                        // Heart overlay
                        Positioned(
                          top: 8,
                          right: 8,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(20),
                              onTap: onToggleSave,
                              child: AnimatedContainer(
                                duration: const Duration(milliseconds: 200),
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.85),
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  isSaved
                                      ? Icons.favorite
                                      : Icons.favorite_border,
                                  size: 22,
                                  color: isSaved
                                      ? Colors.red[400]
                                      : Colors.grey[600],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  )
                else
                  Container(
                    height: 140,
                    width: double.infinity,
                    color: Colors.grey[50],
                    child: Stack(
                      children: [
                        Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.image_outlined,
                                  size: 40, color: Colors.grey[300]),
                              const SizedBox(height: 8),
                              Text(
                                'No image available',
                                style: TextStyle(
                                    fontSize: 12, color: Colors.grey[400]),
                              ),
                            ],
                          ),
                        ),
                        // Heart overlay (also on no-image placeholder)
                        Positioned(
                          top: 8,
                          right: 8,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(20),
                              onTap: onToggleSave,
                              child: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: Colors.white.withValues(alpha: 0.85),
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  isSaved
                                      ? Icons.favorite
                                      : Icons.favorite_border,
                                  size: 22,
                                  color: isSaved
                                      ? Colors.red[400]
                                      : Colors.grey[600],
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: _categoryColor.withValues(alpha: 0.1),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              _categoryLabel,
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: _categoryColor,
                              ),
                            ),
                          ),
                          const Spacer(),
                          if (_ratingText.isNotEmpty)
                            Row(
                              children: [
                                Icon(Icons.star_rounded,
                                    size: 16, color: Colors.amber[700]),
                                const SizedBox(width: 3),
                                Text(
                                  _ratingText,
                                  style: const TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        place.name,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.black87,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (_descriptionSnippet.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Text(
                          _descriptionSnippet,
                          style: TextStyle(
                            fontSize: 13,
                            color: Colors.grey[600],
                            height: 1.3,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                      if (_locationText.isNotEmpty) ...[
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.location_on_outlined,
                                size: 14, color: Colors.grey[400]),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Text(
                                _locationText,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[500],
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
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
