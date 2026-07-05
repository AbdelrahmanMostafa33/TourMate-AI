import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shimmer/shimmer.dart';

import '../../../../app/app_theme.dart';
import '../../../../core/network/service_locator.dart';
import '../../../../core/theme/design_tokens.dart';
import '../../../../core/widgets/premium_widgets.dart';
import '../../data/repository/explore_repository.dart';
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
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => ExploreCubit(locator<ExploreRepository>()),
      child: const _ExploreBody(),
    );
  }
}

class _ExploreBody extends StatefulWidget {
  const _ExploreBody();

  @override
  State<_ExploreBody> createState() => _ExploreBodyState();
}

class _ExploreBodyState extends State<_ExploreBody> {
  TourMateColors get tm => context.tm;

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
      backgroundColor: tm.nearWhite,
      appBar: AppBar(
        backgroundColor: tm.brandWhite,
        elevation: 0,
        scrolledUnderElevation: 0.5,
        title: Text(
          'Explore',
          style: GoogleFonts.inter(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: tm.textPrimary,
            letterSpacing: -0.3,
          ),
        ),
        centerTitle: false,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(
            color: tm.divider,
            height: 0.5,
          ),
        ),
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
                  loading: () => const TMLoadingIndicator(message: 'Loading places...'),
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
                      color: tm.textPrimary,
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
                              padding: const EdgeInsets.fromLTRB(Spacing.xl4, Spacing.md, Spacing.xl4, Spacing.xs),
                              child: Row(
                                children: [
                                  Text(
                                    total > 0
                                        ? '$total place${total > 1 ? 's' : ''} found'
                                        : 'No places found',
                                    style: GoogleFonts.inter(
                                      fontSize: 13,
                                      color: tm.textTertiary,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  if (_isSearchActive && _searchController.text.isNotEmpty) ...[
                                    const SizedBox(width: Spacing.md),
                                    TMBadge(
                                      label: 'AI Search',
                                      icon: Icons.auto_awesome,
                                      isAccented: true,
                                      fontSize: 10,
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
                              padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xs, Spacing.xl3, Spacing.xl5),
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
                              padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xs, Spacing.xl3, Spacing.xl5),
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
                  error: (message) => TMErrorState(
                    message: message,
                    onRetry: () => cubit.init(),
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
      padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.md, Spacing.xl3, Spacing.xl2),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        height: 50,
        decoration: BoxDecoration(
          color: tm.brandWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl2),
          border: Border.all(
            color: _isSearchFocused
                ? tm.deepRoyalBlue.withValues(alpha: 0.5)
                : tm.borderLight,
            width: _isSearchFocused ? 1.5 : 1.0,
          ),
          boxShadow: _isSearchFocused
              ? [
                  BoxShadow(
                    color: tm.deepRoyalBlue.withValues(alpha: 0.06),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ]
              : [
                  BoxShadow(
                    color: tm.deepNavy.withValues(alpha: 0.03),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
        ),
        child: Row(
          children: [
            const SizedBox(width: Spacing.xl3),
            Icon(
              Icons.auto_awesome_outlined,
              size: 18,
              color: _isSearchFocused ? tm.deepRoyalBlue : tm.textTertiary,
            ),
            const SizedBox(width: Spacing.lg),
            Expanded(
              child: TextField(
                controller: _searchController,
                focusNode: _searchFocusNode,
                onChanged: (_) {
                  // Just update UI state when text changes, don't search yet
                  setState(() => _isSearchActive = _searchController.text.trim().isNotEmpty);
                },
                onSubmitted: (query) {
                  final trimmed = query.trim();
                  if (trimmed.isNotEmpty) {
                    setState(() => _isSearchActive = true);
                    cubit.searchPlaces(trimmed);
                    _searchFocusNode.unfocus();
                  }
                },
                textInputAction: TextInputAction.search,
                style: GoogleFonts.inter(fontSize: 14, color: tm.textPrimary),
                decoration: InputDecoration(
                  hintText: 'Search naturally...',
                  hintStyle: GoogleFonts.inter(
                    fontSize: 13,
                    color: tm.textTertiary,
                  ),
                  border: InputBorder.none,
                  contentPadding: const EdgeInsets.symmetric(vertical: Spacing.xl),
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
                  margin: const EdgeInsets.only(right: Spacing.md),
                  padding: const EdgeInsets.all(Spacing.sm),
                  decoration: BoxDecoration(
                    color: tm.surface,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(Icons.close, size: 16, color: tm.textSecondary),
                ),
              ),
            // Search button — triggers the actual search
            GestureDetector(
              onTap: () {
                final query = _searchController.text.trim();
                if (query.isNotEmpty) {
                  setState(() => _isSearchActive = true);
                  cubit.searchPlaces(query);
                  _searchFocusNode.unfocus();
                }
              },
              child: Container(
                margin: const EdgeInsets.only(right: Spacing.md),
                padding: const EdgeInsets.all(Spacing.sm),
                decoration: BoxDecoration(
                  color: tm.deepRoyalBlue,
                  shape: BoxShape.circle,
                ),
                child: Icon(Icons.search, size: 16, color: tm.brandWhite),
              ),
            ),
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
      case 'all': return null;
      case 'attraction': return 'attraction';
      case 'restaurant': return 'restaurant';
      case 'hotel': return 'hotel';
      default: return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.xs, Spacing.xl3, Spacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── City dropdown — sapphire-accented ─────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2),
            decoration: BoxDecoration(
              color: tm.brandWhite,
              borderRadius: BorderRadius.circular(RadiusTokens.xl),
              border: Border.all(color: tm.borderLight),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String?>(
                value: selectedCity,
                isExpanded: true,
                hint: Text(
                  'All cities',
                  style: GoogleFonts.inter(color: tm.textTertiary, fontSize: 14),
                ),
                icon: Icon(Icons.expand_more, color: tm.textTertiary),
                style: GoogleFonts.inter(fontSize: 14, color: tm.textPrimary, fontWeight: FontWeight.w500),
                items: [
                  DropdownMenuItem<String?>(
                    value: null,
                    child: Row(
                      children: [
                        Icon(Icons.explore_outlined, size: 16, color: tm.sapphire),
                        const SizedBox(width: Spacing.md),
                        Text('All cities', style: GoogleFonts.inter(color: tm.textTertiary, fontSize: 14)),
                      ],
                    ),
                  ),
                  ...cities.map((city) => DropdownMenuItem<String?>(
                        value: city,
                        child: Row(
                          children: [
                            Icon(Icons.location_city_outlined, size: 16, color: tm.textTertiary),
                            const SizedBox(width: Spacing.md),
                            Text(city, style: GoogleFonts.inter(color: tm.textPrimary, fontSize: 14)),
                          ],
                        ),
                      )),
                ],
                onChanged: onCityChanged,
              ),
            ),
          ),

          const SizedBox(height: Spacing.xl2),

          // ── Category chips — sapphire accent when selected ────
          SizedBox(
            height: 38,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: _categories.map((label) {
                final param = _categoryToParam(label);
                final isSelected = selectedCategory == param;
                return Padding(
                  padding: const EdgeInsets.only(right: Spacing.md),
                  child: GestureDetector(
                    onTap: () => onCategoryChanged(param),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      curve: Curves.easeOutCubic,
                      padding: const EdgeInsets.symmetric(horizontal: Spacing.xl4, vertical: Spacing.md),
                      decoration: BoxDecoration(
                        color: isSelected ? tm.deepNavy : tm.surface,
                        borderRadius: BorderRadius.circular(RadiusTokens.full),
                        border: isSelected
                            ? Border.all(color: tm.sapphire.withValues(alpha: 0.3), width: 1)
                            : Border.all(color: tm.borderLight),
                      ),
                      alignment: Alignment.center,
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (isSelected)
                            Padding(
                              padding: const EdgeInsets.only(right: Spacing.sm),
                              child: Icon(Icons.auto_awesome, size: 12, color: tm.sapphireLight),
                            ),
                          Text(
                            label,
                            style: GoogleFonts.inter(
                              fontSize: 13,
                              fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                              color: isSelected ? tm.brandWhite : tm.textSecondary,
                            ),
                          ),
                        ],
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
      case 'hotel': return 'Hotel';
      case 'restaurant': return 'Restaurant';
      case 'attraction': return 'Attraction';
      default: return place.category.isEmpty ? 'Place' : place.category;
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
    if (place.country != null && place.country!.isNotEmpty) parts.add(place.country!);
    return parts.join(', ');
  }

  @override
  Widget build(BuildContext context) {
    final tm = context.tm;
    return Padding(
      padding: const EdgeInsets.only(bottom: Spacing.xl3),
      child: Material(
        color: tm.brandWhite,
        borderRadius: BorderRadius.circular(RadiusTokens.xl3),
        elevation: 0,
        child: InkWell(
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          onTap: () {
            if (place.placeId.isNotEmpty) {
              Navigator.pushNamed(context, '/place-detail', arguments: place.placeId);
            }
          },
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(RadiusTokens.xl3),
              border: Border.all(color: tm.borderLight),
              boxShadow: [
                BoxShadow(
                  color: tm.deepNavy.withValues(alpha: 0.04),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            clipBehavior: Clip.antiAlias,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Photo with sapphire-accented save button ──────
                if (place.hasPhoto)
                  Hero(
                    tag: 'place-photo-${place.placeId}',
                    child: SizedBox(
                      height: 190,
                      width: double.infinity,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          Image.network(
                            place.firstPhoto,
                            fit: BoxFit.cover,
                            loadingBuilder: (_, child, progress) {
                              if (progress == null) return child;
                              return Container(color: tm.surface, child: const Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black26)));
                            },
                            errorBuilder: (_, _, _) => Container(
                              color: tm.surface,
                              child: Icon(Icons.image, color: tm.textTertiary, size: 48),
                            ),
                          ),
                          // Gradient overlay at bottom
                          Positioned(
                            bottom: 0,
                            left: 0,
                            right: 0,
                            height: 60,
                            child: Container(
                              decoration: BoxDecoration(
                                gradient: LinearGradient(
                                  begin: Alignment.bottomCenter,
                                  end: Alignment.topCenter,
                                  colors: [
                                    tm.deepNavy.withValues(alpha: 0.4),
                                    Colors.transparent,
                                  ],
                                ),
                              ),
                            ),
                          ),
                          // Save button with sapphire accent
                          Positioned(
                            top: Spacing.lg,
                            right: Spacing.lg,
                            child: Material(
                              color: Colors.transparent,
                              child: InkWell(
                                borderRadius: BorderRadius.circular(RadiusTokens.xl4),
                                onTap: onToggleSave,
                                child: AnimatedContainer(
                                  duration: const Duration(milliseconds: 250),
                                  curve: Curves.easeOutCubic,
                                  padding: const EdgeInsets.all(Spacing.lg),
                                  decoration: BoxDecoration(
                                    color: tm.brandWhite.withValues(alpha: 0.9),
                                    shape: BoxShape.circle,
                                    border: isSaved
                                        ? Border.all(color: tm.deepRoyalBlue.withValues(alpha: 0.5), width: 1.5)
                                        : null,
                                  ),
                                  child: Icon(
                                    isSaved ? Icons.favorite : Icons.favorite_border,
                                    size: 20,
                                    color: isSaved ? tm.deepRoyalBlue : tm.textSecondary,
                                  ),
                                ),
                              ),
                            ),
                          ),
                          // Rating badge on photo
                          if (_ratingText.isNotEmpty)
                            Positioned(
                              bottom: Spacing.lg,
                              left: Spacing.lg,
                              child: TMRatingBadge(rating: place.rating, reviewCount: place.reviewCount > 0 ? place.reviewCount : null),
                            ),
                        ],
                      ),
                    ),
                  )
                else
                  Hero(
                    tag: 'place-photo-${place.placeId}',
                    child: Container(
                      height: 150,
                    width: double.infinity,
                    color: tm.surface,
                    child: Stack(
                      children: [
                        Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.image_outlined, size: 40, color: tm.borderLight),
                              const SizedBox(height: Spacing.md),
                              Text('No image available', style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary)),
                            ],
                          ),
                        ),
                        Positioned(
                          top: Spacing.lg,
                          right: Spacing.lg,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(RadiusTokens.xl4),
                              onTap: onToggleSave,
                              child: Container(
                                padding: const EdgeInsets.all(Spacing.lg),
                                decoration: BoxDecoration(
                                  color: tm.brandWhite.withValues(alpha: 0.9),
                                  shape: BoxShape.circle,
                                ),
                                child: Icon(
                                  isSaved ? Icons.favorite : Icons.favorite_border,
                                  size: 20,
                                  color: isSaved ? tm.deepRoyalBlue : tm.textSecondary,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  ),

                // ── Card content ─────────────────────────────
                Padding(
                  padding: const EdgeInsets.all(Spacing.xl3),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Category + rating row
                      Row(
                        children: [
                          TMBadge(label: _categoryLabel, icon: Icons.sell_outlined),
                          const Spacer(),
                          if (_ratingText.isNotEmpty && !place.hasPhoto)
                            TMRatingBadge(rating: place.rating),
                        ],
                      ),
                      const SizedBox(height: Spacing.sm),
                      // Name
                      Text(
                        place.name,
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: tm.textPrimary,
                          letterSpacing: -0.2,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      // Description
                      if (_descriptionSnippet.isNotEmpty) ...[
                        const SizedBox(height: Spacing.sm),
                        Text(
                          _descriptionSnippet,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            color: tm.textSecondary,
                            height: 1.35,
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                      // Location
                      if (_locationText.isNotEmpty) ...[
                        const SizedBox(height: Spacing.sm),
                        Row(
                          children: [
                            Icon(Icons.location_on_outlined, size: 14, color: tm.textTertiary),
                          const SizedBox(width: Spacing.xs),
                          Expanded(
                            child: Text(
                              _locationText,
                                style: GoogleFonts.inter(fontSize: 12, color: tm.textTertiary),
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
    final tm = context.tm;
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl7),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Icon with sapphire gradient
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    tm.sapphire.withValues(alpha: 0.08),
                    tm.sapphire.withValues(alpha: 0.02),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                shape: BoxShape.circle,
                border: Border.all(color: tm.sapphire.withValues(alpha: 0.12)),
              ),
              child: Icon(
                isSearch ? Icons.search_off_rounded : Icons.filter_list_off_rounded,
                size: 36,
                color: tm.sapphire.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: Spacing.xl4),

            // Title
            Text(
              isSearch ? 'No results found' : 'No places match',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: tm.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: Spacing.md),

            // Subtitle
            Text(
              isSearch
                  ? 'We couldn\'t find places for "${query.length > 40 ? '${query.substring(0, 37)}...' : query}"'
                  : 'Try broadening your filters or search for something else',
              style: GoogleFonts.inter(
                fontSize: 13,
                color: tm.textTertiary,
                height: 1.4,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: Spacing.xl4),

            // Action buttons
            if (isSearch)
              Wrap(
                spacing: Spacing.md,
                runSpacing: Spacing.md,
                alignment: WrapAlignment.center,
                children: [
                  _actionChip(tm,
                    icon: Icons.clear_all,
                    label: 'Clear search',
                    onTap: onClearSearch,
                    isPrimary: true,
                  ),
                ],
              )
            else
              Wrap(
                spacing: Spacing.md,
                runSpacing: Spacing.md,
                alignment: WrapAlignment.center,
                children: [
                  if (selectedCategory != null || selectedCity != null)
                    _actionChip(tm,
                      icon: Icons.restart_alt,
                      label: 'Reset filters',
                      onTap: onResetFilters,
                      isPrimary: true,
                    ),
                  _actionChip(tm,
                    icon: Icons.auto_awesome_outlined,
                    label: 'Try semantic search',
                    onTap: () {
                      onStartSearch();
                    },
                    isPrimary: false,
                  ),
                ],
              ),

            const SizedBox(height: Spacing.xl5),

            // Suggestion chips header
            Text(
              isSearch ? 'Try searching for:' : 'Quick suggestions:',
              style: GoogleFonts.inter(
                fontSize: 12,
                color: tm.textTertiary,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: Spacing.lg),
            Wrap(
              spacing: Spacing.md,
              runSpacing: Spacing.md,
              alignment: WrapAlignment.center,
              children: _suggestions.map((s) => _suggestionChip(tm, s)).toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionChip(TourMateColors tm, {
    required IconData icon,
    required String label,
    required VoidCallback onTap,
    required bool isPrimary,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl2, vertical: Spacing.md),
        decoration: BoxDecoration(
          color: isPrimary ? tm.deepNavy : tm.brandWhite,
          borderRadius: BorderRadius.circular(RadiusTokens.xl4),
          border: Border.all(
            color: isPrimary ? tm.deepNavy : tm.borderLight,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14,            color: isPrimary ? tm.brandWhite : tm.sapphire),
            const SizedBox(width: Spacing.sm),
            Text(
              label,
              style: GoogleFonts.inter(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: isPrimary ? tm.brandWhite : tm.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _suggestionChip(TourMateColors tm, String text) {
    return GestureDetector(
      onTap: () => onSuggestionTap(text),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Spacing.xl, vertical: Spacing.sm),
        decoration: BoxDecoration(
          color: tm.surface,
          borderRadius: BorderRadius.circular(RadiusTokens.xl3),
          border: Border.all(color: tm.borderLight),
        ),
        child: Text(
          text,
          style: GoogleFonts.inter(
            fontSize: 12,
            color: tm.textSecondary,
            fontWeight: FontWeight.w500,
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
    final tm = context.tm;
    return Container(
      padding: const EdgeInsets.fromLTRB(Spacing.xl3, Spacing.sm, Spacing.xl3, Spacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header row
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(Spacing.sm),
                decoration: BoxDecoration(
                  color: tm.sapphire.withValues(alpha: 0.06),
                  borderRadius: BorderRadius.circular(RadiusTokens.sm),
                ),
                child: Icon(Icons.history, size: 13, color: tm.sapphire),
              ),
              const SizedBox(width: Spacing.md),
              Text(
                'Recent searches',
                style: GoogleFonts.inter(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: tm.textTertiary,
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: onClearAll,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.lg, vertical: Spacing.xs),
                  decoration: BoxDecoration(
                    color: tm.sapphire.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(RadiusTokens.md),
                  ),
                  child: Text(
                    'Clear all',
                    style: GoogleFonts.inter(
                      fontSize: 11,
                      color: tm.sapphire,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: Spacing.sm),
          // Search chips with sapphire accent
          Wrap(
            spacing: Spacing.md,
            runSpacing: Spacing.md,
            children: searches.map((query) {
              return GestureDetector(
                onTap: () => onSearchTap(query),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: Spacing.xl, vertical: Spacing.sm),
                  decoration: BoxDecoration(
                    color: tm.brandWhite,
                    borderRadius: BorderRadius.circular(RadiusTokens.xl3),
                    border: Border.all(color: tm.borderLight),
                    boxShadow: [
                      BoxShadow(
                        color: tm.deepNavy.withValues(alpha: 0.03),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.access_time, size: 12, color: tm.sapphire.withValues(alpha: 0.6)),
                      const SizedBox(width: Spacing.sm),
                      ConstrainedBox(
                        constraints: BoxConstraints(
                          maxWidth: MediaQuery.of(context).size.width * 0.55,
                        ),
                        child: Text(
                          query,
                          style: GoogleFonts.inter(
                            fontSize: 12,
                            color: tm.textSecondary,
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: Spacing.xs),
                      GestureDetector(
                        onTap: () => onRemove(query),
                        child: Container(
                          padding: const EdgeInsets.all(Spacing.xxs),
                          decoration: BoxDecoration(
                            color: tm.sapphire.withValues(alpha: 0.06),
                            borderRadius: BorderRadius.circular(RadiusTokens.xs),
                          ),
                          child: Icon(Icons.close, size: 11, color: tm.sapphire.withValues(alpha: 0.6)),
                        ),
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
    final tm = context.tm;
    return Shimmer.fromColors(
      baseColor: tm.border,
      highlightColor: tm.sapphireSurface,
      period: const Duration(milliseconds: 1500),
      child: Padding(
        padding: const EdgeInsets.only(bottom: Spacing.xl3),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(RadiusTokens.xl3),
            border: Border.all(color: tm.borderLight),
          ),
          clipBehavior: Clip.antiAlias,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(height: 190, width: double.infinity, color: Colors.white),
              Padding(
                padding: const EdgeInsets.all(Spacing.xl3),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(width: 70, height: 18, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(RadiusTokens.sm))),
                        const Spacer(),
                        Container(width: 50, height: 18, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(RadiusTokens.sm))),
                      ],
                    ),
                    const SizedBox(height: Spacing.lg),
                    Container(width: double.infinity, height: 16, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(RadiusTokens.xs))),
                    const SizedBox(height: Spacing.lg),
                    Container(width: double.infinity, height: 12, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(4))),
                    const SizedBox(height: Spacing.sm),
                    Container(width: 200, height: 12, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(RadiusTokens.xs))),
                    const SizedBox(height: Spacing.md),
                    Row(children: [
                      Container(width: 14, height: 14, decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle)),
                      const SizedBox(width: Spacing.xs),
                      Container(width: 100, height: 12, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(RadiusTokens.xs))),
                    ]),
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
