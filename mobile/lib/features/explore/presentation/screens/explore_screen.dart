import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shimmer/shimmer.dart';

import '../../data/models/place_model.dart';
import '../../logic/explore_cubit.dart';
import '../../logic/explore_state.dart';

class ExploreScreen extends StatefulWidget {
  const ExploreScreen({super.key});

  @override
  State<ExploreScreen> createState() => _ExploreScreenState();
}

class _ExploreScreenState extends State<ExploreScreen> {
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();
  bool _isSearchActive = false;
  bool _isSearchFocused = false;

  @override
  void initState() {
    super.initState();
    final cubit = context.read<ExploreCubit>();
    Future.microtask(() => cubit.init());
    _searchFocusNode.addListener(() {
      if (mounted) {
        setState(() => _isSearchFocused = _searchFocusNode.hasFocus);
      }
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchFocusNode.dispose();
    super.dispose();
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
      body: Column(
        children: [
          // ── Search Bar ──────────────────────────────────
          _buildSearchBar(cubit),

          // ── Recent Search History Overlay ───────────────
          if (_isSearchFocused && !_isSearchActive && cubit.recentSearches.isNotEmpty)
            _RecentSearchOverlay(
              searches: cubit.recentSearches,
              onSearchTap: (query) {
                _searchController.text = query;
                setState(() => _isSearchActive = true);
                cubit.searchPlaces(query);
                _searchFocusNode.unfocus();
              },
              onRemove: (query) => cubit.removeRecentSearch(query),
              onClearAll: () => cubit.clearRecentSearches(),
            ),

          // ── Main Content ────────────────────────────────
          Expanded(
            child: BlocBuilder<ExploreCubit, ExploreState>(
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
                    isLoadingResults,
                    selectedCity,
                    selectedCategory,
                    savedPlaceIds,
                  ) {
                    return RefreshIndicator(
                      color: Colors.black,
                      onRefresh: () async {
                        if (_isSearchActive && _searchController.text.isNotEmpty) {
                          cubit.searchPlaces(_searchController.text);
                        } else {
                          await cubit.setCity(selectedCity);
                        }
                      },
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
                              child: Row(
                                children: [
                                  Text(
                                    total > 0
                                        ? '$total place${total > 1 ? 's' : ''} found'
                                        : 'No places found',
                                    style: TextStyle(
                                      fontSize: 13,
                                      color: Colors.grey[500],
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  if (_isSearchActive && _searchController.text.isNotEmpty) ...[
                                    const SizedBox(width: 8),
                                    Icon(Icons.auto_awesome, size: 14, color: Colors.indigo[400]),
                                    const SizedBox(width: 4),
                                    Text(
                                      'Semantic search',
                                      style: TextStyle(
                                        fontSize: 11,
                                        color: Colors.indigo[400],
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          ),

                          // ── Place cards ──────────────────────────
                          if (isLoadingResults)
                            // Show shimmer skeleton while searching
                            SliverPadding(
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                              sliver: SliverList(
                                delegate: SliverChildBuilderDelegate(
                                  (_, index) => const _ShimmerPlaceCard(),
                                  childCount: 4,
                                ),
                              ),
                            )
                          else if (places.isEmpty)
                            SliverFillRemaining(
                              child: _EmptyState(
                                isSearch: _isSearchActive && _searchController.text.isNotEmpty,
                                query: _searchController.text,
                                selectedCity: selectedCity,
                                selectedCategory: selectedCategory,
                                onClearSearch: () {
                                  _searchController.clear();
                                  _searchFocusNode.unfocus();
                                  setState(() => _isSearchActive = false);
                                  cubit.clearSearch();
                                },
                                onSuggestionTap: (suggestion) {
                                  // Handle filter reset suggestions as filter actions
                                  if (suggestion == 'Show all cities') {
                                    cubit.setCity(null);
                                    return;
                                  }
                                  if (suggestion == 'Try "All" categories') {
                                    cubit.setCategory(null);
                                    return;
                                  }
                                  // All other suggestions → semantic search
                                  _searchController.text = suggestion;
                                  setState(() => _isSearchActive = true);
                                  cubit.searchPlaces(suggestion);
                                },
                                onResetFilters: () {
                                  cubit.setCity(null);
                                },
                                onStartSearch: () {
                                  _searchController.text = 'Popular places in Cairo';
                                  setState(() => _isSearchActive = true);
                                  _searchFocusNode.requestFocus();
                                  cubit.searchPlaces('Popular places in Cairo');
                                },
                              ),
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
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar(ExploreCubit cubit) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Container(
        height: 48,
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _isSearchActive ? Colors.indigo.shade200 : Colors.grey.shade200,
          ),
        ),
        child: Row(
          children: [
            const SizedBox(width: 14),
            Icon(
              Icons.auto_awesome_outlined,
              size: 18,
              color: _isSearchActive ? Colors.indigo[400] : Colors.grey[400],
            ),
            const SizedBox(width: 10),
            Expanded(
              child: TextField(
                controller: _searchController,
                focusNode: _searchFocusNode,
                onChanged: (query) {
                  final isNotEmpty = query.trim().isNotEmpty;
                  if (isNotEmpty != _isSearchActive) {
                    setState(() => _isSearchActive = isNotEmpty);
                  }
                  cubit.searchPlaces(query);
                },
                style: const TextStyle(fontSize: 14),
                decoration: InputDecoration(
                  hintText: 'Search naturally... e.g. "romantic dinner with sea view"',
                  hintStyle: TextStyle(
                    fontSize: 13,
                    color: Colors.grey[400],
                  ),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: 12),
                ),
              ),
            ),
            if (_isSearchActive)
              GestureDetector(
                onTap: () {
                  _searchController.clear();
                  _searchFocusNode.unfocus();
                  setState(() => _isSearchActive = false);
                  cubit.clearSearch();
                },
                child: Container(
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade200,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.close, size: 16, color: Colors.grey[600]),
                ),
              ),
            const SizedBox(width: 12),
          ],
        ),
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

// ── Empty State ──────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final bool isSearch;
  final String query;
  final String? selectedCity;
  final String? selectedCategory;
  final VoidCallback onClearSearch;
  final ValueChanged<String> onSuggestionTap;
  final VoidCallback onResetFilters;
  final VoidCallback onStartSearch;

  const _EmptyState({
    required this.isSearch,
    required this.query,
    required this.selectedCity,
    required this.selectedCategory,
    required this.onClearSearch,
    required this.onSuggestionTap,
    required this.onResetFilters,
    required this.onStartSearch,
  });

  List<String> get _suggestions {
    if (isSearch) {
      return [
        'Best restaurants in Cairo',
        'Romantic dinner with sea view',
        'Family-friendly hotels',
        'Hidden gems near pyramids',
        'Affordable street food',
      ];
    }
    // Filter-only suggestions
    final suggestions = <String>[];
    if (selectedCategory != null) {
      suggestions.add('Try "All" categories');
    }
    if (selectedCity != null) {
      suggestions.add('Show all cities');
    }
    suggestions.addAll([
      'Try a semantic search instead',
      'Browse popular places',
    ]);
    return suggestions;
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Icon
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: isSearch ? Colors.indigo.shade50 : Colors.grey.shade50,
                shape: BoxShape.circle,
              ),
              child: Icon(
                isSearch ? Icons.search_off_rounded : Icons.filter_list_off_rounded,
                size: 36,
                color: isSearch ? Colors.indigo[300] : Colors.grey[400],
              ),
            ),
            const SizedBox(height: 20),

            // Title
            Text(
              isSearch ? 'No results found' : 'No places match',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Colors.black87,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),

            // Subtitle
            Text(
              isSearch
                  ?              'We couldn\'t find places for "${query.length > 40 ? '${query.substring(0, 37)}...' : query}"'
                  : 'Try broadening your filters or search for something else',
              style: TextStyle(
                fontSize: 13,
                color: Colors.grey[500],
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),

            // Action buttons
            if (isSearch)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  _actionChip(
                    icon: Icons.clear_all,
                    label: 'Clear search',
                    onTap: onClearSearch,
                    isPrimary: true,
                  ),
                ],
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                alignment: WrapAlignment.center,
                children: [
                  if (selectedCategory != null || selectedCity != null)
                    _actionChip(
                      icon: Icons.restart_alt,
                      label: 'Reset filters',
                      onTap: onResetFilters,
                      isPrimary: true,
                    ),
                  _actionChip(
                    icon: Icons.auto_awesome_outlined,
                    label: 'Try semantic search',
                    onTap: () {
                      onStartSearch();
                    },
                    isPrimary: false,
                  ),
                ],
              ),

            const SizedBox(height: 24),

            // Suggestion chips
            Text(
              isSearch ? 'Try searching for:' : 'Quick suggestions:',
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey[400],
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: _suggestions.map((s) => _suggestionChip(s)).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionChip({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    required bool isPrimary,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isPrimary ? Colors.black : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isPrimary ? Colors.black : Colors.grey.shade300,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: isPrimary ? Colors.white : Colors.grey[600]),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: isPrimary ? Colors.white : Colors.grey[700],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestionChip(String text) {
    return GestureDetector(
      onTap: () => onSuggestionTap(text),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: Colors.grey.shade50,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Text(
          text,
          style: TextStyle(
            fontSize: 12,
            color: Colors.grey[600],
          ),
        ),
      ),
    );
  }
}

// ── Recent Search Overlay ───────────────────────────────────────────────

class _RecentSearchOverlay extends StatelessWidget {
  final List<String> searches;
  final ValueChanged<String> onSearchTap;
  final ValueChanged<String> onRemove;
  final VoidCallback onClearAll;

  const _RecentSearchOverlay({
    required this.searches,
    required this.onSearchTap,
    required this.onRemove,
    required this.onClearAll,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header row
          Row(
            children: [
              Icon(Icons.history, size: 14, color: Colors.grey[400]),
              const SizedBox(width: 6),
              Text(
                'Recent searches',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey[500],
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: onClearAll,
                child: Text(
                  'Clear all',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.grey[400],
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Search chips
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: searches.map((query) {
              return GestureDetector(
                onTap: () => onSearchTap(query),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.access_time, size: 12, color: Colors.grey[400]),
                      const SizedBox(width: 6),
                      ConstrainedBox(
                        constraints: BoxConstraints(
                          maxWidth: MediaQuery.of(context).size.width * 0.6,
                        ),
                        child: Text(
                          query,
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 4),
                      GestureDetector(
                        onTap: () => onRemove(query),
                        child: Icon(Icons.close, size: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}

// ── Shimmer Skeleton Card ────────────────────────────────────────────────

class _ShimmerPlaceCard extends StatelessWidget {
  const _ShimmerPlaceCard();

  @override
  Widget build(BuildContext context) {
    return Shimmer.fromColors(
      baseColor: Colors.grey.shade200,
      highlightColor: Colors.grey.shade50,
      period: const Duration(milliseconds: 1500),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 16),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.grey.shade200),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Image skeleton ──────────────────────────
              Container(
                height: 180,
                width: double.infinity,
                color: Colors.white,
              ),
              // ── Text skeleton ──────────────────────────
              Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Category badge + rating row
                    Row(
                      children: [
                        Container(
                          width: 70,
                          height: 18,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                        const Spacer(),
                        Container(
                          width: 40,
                          height: 18,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(6),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    // Title
                    Container(
                      width: double.infinity,
                      height: 16,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 10),
                    // Description line 1
                    Container(
                      width: double.infinity,
                      height: 12,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 6),
                    // Description line 2
                    Container(
                      width: 200,
                      height: 12,
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Location
                    Row(
                      children: [
                        Container(
                          width: 14,
                          height: 14,
                          decoration: const BoxDecoration(
                            color: Colors.white,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Container(
                          width: 100,
                          height: 12,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(4),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
